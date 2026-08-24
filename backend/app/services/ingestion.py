"""入库管线：解析 → 切分 → 向量化 → 存库（F1 的核心业务）。

红线②：解析失败零切片——任何一步失败都先标记 failed，不产生半个切片。
"""
import re
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.llm.embedding import embed_texts
from app.models.tables import Document, DocumentDepartment
from app.parser import parse_file
from app.services import audit
from app.storage import vector_store

# 句边界（对照 RAGFlow naive.py 的 delimiter）
_SENTENCE_END = re.compile(r"(?<=[。！？!?；;\n])")


def estimate_tokens(text: str) -> int:
    """粗略 token 估算：中英混合约 1 token ≈ 1.5 字符（避免引入 tokenizer 依赖）。"""
    return max(1, int(len(text) / 1.5))


def chunk_text(text: str, budget: int | None = None) -> list[str]:
    """按句边界切分，按 token 预算封顶（保语义完整、控块大小）。

    参数: budget 每块 token 预算，默认取配置 512
    返回: 切片文本列表
    """
    budget = budget or settings.chunk_token_budget
    sentences = [s for s in _SENTENCE_END.split(text) if s.strip()]
    chunks: list[str] = []
    current = ""
    for sent in sentences:
        if current and estimate_tokens(current + sent) > budget:
            chunks.append(current.strip())
            current = sent
        else:
            current += sent
    if current.strip():
        chunks.append(current.strip())
    return chunks


def ingest_document(db: Session, doc: Document) -> None:
    """把一份文档走完入库全流程，更新其 status。

    成功: status=ok，产生切片与向量；失败: status=failed+原因，零切片（红线②）。
    """
    dept_ids = [d.department_id for d in db.query(DocumentDepartment).filter_by(document_id=doc.id)]
    try:
        text = parse_file(Path(doc.filename))
        chunks = chunk_text(text)
        vectors = embed_texts(chunks)

        # 多部门文档：每个部门存一份向量条目（MVP 简化，见 02-架构 §6 补充）
        ids, metas = [], []
        for idx, _chunk in enumerate(chunks):
            for dept_id in dept_ids:
                ids.append(f"{doc.id}-{idx}-d{dept_id}")
                metas.append({
                    "doc_id": doc.id,
                    "chunk_index": idx,
                    "dept_id": dept_id,
                    "clearance": doc.clearance_level,
                })
        vector_store.add_chunks(ids=ids, embeddings=[v for v in vectors for _ in dept_ids], metadatas=metas)

        from app.models.tables import Chunk
        for idx, chunk in enumerate(chunks):
            db.add(Chunk(document_id=doc.id, chunk_index=idx, content=chunk, chroma_id=f"{doc.id}-{idx}"))

        doc.status = "ok"
        doc.fail_reason = None
        db.commit()
        audit.log(db, doc.uploader_id, "upload", f"doc:{doc.id}", f"解析成功，{len(chunks)} 切片")
    except Exception as e:
        doc.status = "failed"
        doc.fail_reason = str(e)[:500]
        db.commit()
        audit.log(db, doc.uploader_id, "upload", f"doc:{doc.id}", f"解析失败: {doc.fail_reason}")
