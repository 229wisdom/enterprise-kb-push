"""检索定位接口（F4）：只检索不生成——告诉用户"数据在哪个文件里"。"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.models.database import get_db
from app.models.tables import User
from app.services import audit, retrieval

router = APIRouter(prefix="/search", tags=["检索"])


class SearchIn(BaseModel):
    """检索请求。"""

    question: str


@router.post("")
def search(body: SearchIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    """纯检索：返回命中的切片和所在文档（不调 LLM，零生成成本）。"""
    hits = retrieval.hybrid_search(db, user, body.question)
    audit.log(db, user.id, "query", body.question[:100], f"检索命中 {len(hits)} 条")
    return {
        "total": len(hits),
        "hits": [
            {"doc_title": h["doc_title"], "chunk_index": h["chunk_index"],
             "content": h["content"][:300], "rrf": h["rrf"]}
            for h in hits
        ],
    }
