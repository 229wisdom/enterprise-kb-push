"""关键词检索（BM25，rank_bm25 库）。

权限规则（红线①）：只在【权限内切片】上建索引——
越权内容根本不进入候选集，而不是搜完再删。
MVP 简化：每次查询现场建索引（数据量小可行；量大后改常驻索引）。
"""
import re

from rank_bm25 import BM25Okapi
from sqlalchemy.orm import Session

from app.models.tables import Chunk, Document, DocumentDepartment, User

_TOKEN = re.compile(r"[a-zA-Z0-9]+|[一-鿿]")


def tokenize(text: str) -> list[str]:
    """简版分词：英文数字按词、中文按字（MVP 够用；jieba 留作优化项）。"""
    return _TOKEN.findall(text.lower())


def permitted_chunks(db: Session, user: User) -> list[Chunk]:
    """查出用户权限内的全部切片（部门匹配 AND 密级足够）。"""
    query = (
        db.query(Chunk)
        .join(Document, Document.id == Chunk.document_id)
        .join(DocumentDepartment, DocumentDepartment.document_id == Document.id)
        .filter(Document.status == "ok", Document.clearance_level <= user.clearance_level)
    )
    if user.role != "boss":
        query = query.filter(DocumentDepartment.department_id == user.department_id)
    return query.distinct().all()


def keyword_search(db: Session, user: User, question: str, top_k: int) -> list[dict]:
    """BM25 关键词检索，返回 [{"chunk_id", "rank"}...] 按相关度排序。"""
    chunks = permitted_chunks(db, user)
    if not chunks:
        return []
    bm25 = BM25Okapi([tokenize(c.content) for c in chunks])
    scores = bm25.get_scores(tokenize(question))
    ranked = sorted(zip(chunks, scores), key=lambda x: x[1], reverse=True)
    return [
        {"chunk_id": c.id, "rank": i + 1, "bm25": float(s)}
        for i, (c, s) in enumerate(ranked[:top_k]) if s > 0
    ]
