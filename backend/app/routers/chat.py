"""问答接口（F3）：混合检索 → 防幻觉 prompt → DeepSeek 生成 → 带引用回答。"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.llm.chat import ChatError, chat
from app.models.database import get_db
from app.models.tables import User
from app.services import audit, retrieval

router = APIRouter(prefix="/chat", tags=["问答"])

_SYSTEM_PROMPT = """你是企业内部知识库助手。规则：
1. 只能依据【资料】回答，资料没有的信息必须明确说"根据现有资料无法回答"
2. 引用格式：句末标注来源编号，如 [1]、[2]
3. 不要编造资料中不存在的数字、型号、日期
4. 回答简洁，中文"""

_NO_HIT = "未查到：你权限范围内的知识库中没有相关内容。如需访问其他部门资料，请联系管理员。"


class ChatIn(BaseModel):
    """提问请求。"""

    question: str


@router.post("")
def ask(body: ChatIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    """对话问答。只检索用户权限内的切片（红线①）。"""
    hits = retrieval.hybrid_search(db, user, body.question)

    if not hits:
        audit.log(db, user.id, "query", body.question[:100], "未命中")
        return {"answer": _NO_HIT, "citations": []}

    sources = "\n\n".join(
        f"【资料{i+1}】（来自《{h['doc_title']}》）\n{h['content']}" for i, h in enumerate(hits)
    )
    try:
        answer = chat(db, _SYSTEM_PROMPT, f"【资料】\n{sources}\n\n【问题】{body.question}")
    except ChatError as e:
        answer = f"生成失败（检索已命中 {len(hits)} 条资料，可稍后重试）：{e}"

    audit.log(db, user.id, "query", body.question[:100], f"命中 {len(hits)} 条")
    return {
        "answer": answer,
        "citations": [
            {"ref": i + 1, "doc_title": h["doc_title"], "chunk_index": h["chunk_index"], "rrf": h["rrf"]}
            for i, h in enumerate(hits)
        ],
    }
