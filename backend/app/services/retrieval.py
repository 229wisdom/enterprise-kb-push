"""混合检索服务：向量路 + 关键词路 → RRF 融合（免调权重）。

权限过滤在两路的源头各自执行（红线①）：
- 向量路：Chroma where 元数据过滤（vector_store.search）
- 关键词路：候选集本身就是权限内切片（keyword_store.permitted_chunks）
"""
from sqlalchemy.orm import Session

from app.core.config import settings
from app.llm.embedding import embed_texts
from app.models.tables import Chunk, Department, User
from app.storage import keyword_store, vector_store

_RRF_K = 60  # RRF 平滑常数（业界惯例）


def _dept_scope(db: Session, user: User) -> list[int]:
    """用户可见部门 id：老板=全部部门；其余=本部门。"""
    if user.role == "boss":
        return [d.id for d in db.query(Department).all()]
    return [user.department_id]


def hybrid_search(db: Session, user: User, question: str) -> list[dict]:
    """混合检索：返回 [{"chunk", "doc_title", "rrf"}...] 按融合名次排序。"""
    top_k = settings.retrieve_top_k
    clearance = 3 if user.role == "boss" else user.clearance_level

    # 向量路（权限在 Chroma where 里过滤；距离阈值过滤不相关内容——踩坑教训落地）
    q_vec = embed_texts([question])[0]
    vec_hits = [
        h for h in vector_store.search(q_vec, _dept_scope(db, user), clearance, top_k)
        if h["distance"] <= settings.vector_distance_threshold
    ]
    vec_rank = {}  # (doc_id, chunk_index) -> rank
    for rank, hit in enumerate(vec_hits, start=1):
        # chroma_id 形如 "doc-chunk-d1"，取前两段还原切片位置
        parts = hit["chroma_id"].rsplit("-d", 1)[0].split("-")
        vec_rank[(int(parts[0]), int(parts[1]))] = rank

    # 关键词路（候选集已按权限过滤）
    kw_hits = keyword_store.keyword_search(db, user, question, top_k)
    kw_rank = {h["chunk_id"]: h["rank"] for h in kw_hits}

    # RRF 融合：score = Σ 1/(k+rank)
    scores: dict[int, float] = {}
    for chunk in db.query(Chunk).all():
        rrf = 0.0
        vr = vec_rank.get((chunk.document_id, chunk.chunk_index))
        if vr:
            rrf += 1 / (_RRF_K + vr)
        kr = kw_rank.get(chunk.id)
        if kr:
            rrf += 1 / (_RRF_K + kr)
        if rrf:
            scores[chunk.id] = rrf

    # 粗排取候选池（top_k），再精排取最终 top_n（两阶段：粗排求快、精排求准）
    top_ids = sorted(scores, key=scores.get, reverse=True)[: settings.retrieve_top_k]
    from app.models.tables import Document
    results = []
    for chunk_id in top_ids:
        chunk = db.get(Chunk, chunk_id)
        doc = db.get(Document, chunk.document_id)
        results.append({
            "chunk_id": chunk.id,
            "doc_id": chunk.document_id,
            "doc_title": doc.title if doc else "",
            "chunk_index": chunk.chunk_index,
            "content": chunk.content,
            "rrf": round(scores[chunk_id], 5),
        })
    if settings.rerank_enabled:
        results = rerank(db, question, results)
    return results[: settings.final_top_n]


def rewrite_question(db: Session, history: list[dict], question: str) -> str:
    """多轮改写：把依赖上文的追问（"那它呢？"）补全成独立问题再检索。

    例：上文聊 HP-800 → 追问"那库存呢" → 改写为"HP-800 的库存是多少"
    失败时回退原问题（不影响主链路）。
    """
    if not history:
        return question
    lines = "\n".join(f"问：{h.get('question','')}\n答：{h.get('answer','')[:150]}" for h in history[-4:])
    prompt = (
        f"对话历史：\n{lines}\n\n用户最新问题：{question}\n\n"
        "请把最新问题改写成不依赖上文的完整独立问题（只输出改写后的问题，不要解释）。"
        "如果问题本身已经完整，原样输出。"
    )
    try:
        from app.llm.chat import chat
        rewritten = chat(db, "你是查询改写器，只输出改写后的问题。", prompt).strip().strip('"')
        return rewritten if 2 <= len(rewritten) <= 200 else question
    except Exception:
        return question


def rerank(db: Session, question: str, candidates: list[dict]) -> list[dict]:
    """LLM 精排（Rerank）：让模型给候选切片按相关性重排序。

    策略：一次调用让 LLM 输出编号序列（如 "2,1,3"），失败/异常时回退 RRF 原序。
    用 LLM 而非专用 reranker 模型：零新增依赖（专用 cross-encoder 需装 torch）。
    """
    if len(candidates) <= 1:
        return candidates
    listing = "\n\n".join(f"[{i+1}] {c['content'][:200]}" for i, c in enumerate(candidates))
    prompt = (
        f"问题：{question}\n\n以下是若干资料片段，请按它们对回答该问题的相关程度，"
        f"从高到低输出编号（只输出数字，用逗号分隔，如 2,1,3）：\n\n{listing}"
    )
    try:
        from app.llm.chat import chat
        raw = chat(db, "你是检索相关性排序器，只输出编号序列。", prompt)
        order = [int(x.strip()) - 1 for x in raw.strip().split(",")]
        # 校验：编号合法且去重后补齐遗漏，再追加未提及的候选
        seen = [i for i in order if 0 <= i < len(candidates)]
        seen = list(dict.fromkeys(seen)) + [i for i in range(len(candidates)) if i not in seen]
        return [candidates[i] for i in seen]
    except Exception:
        return candidates  # 回退：保持 RRF 原序
