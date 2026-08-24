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

    # 向量路（权限在 Chroma where 里过滤）
    q_vec = embed_texts([question])[0]
    vec_hits = vector_store.search(q_vec, _dept_scope(db, user), clearance, top_k)
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

    top_ids = sorted(scores, key=scores.get, reverse=True)[: settings.final_top_n]
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
    return results
