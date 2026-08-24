"""问答接口（F3）：混合检索 → 防幻觉 prompt → LLM 生成 → 带引用回答。"""
import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.llm.chat import ChatError, chat_stream
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
    """提问请求。history 为多轮对话历史 [{"question","answer"}...]（前端维护）。"""

    question: str
    history: list[dict] = []


@router.post("/stream")
def ask_stream(body: ChatIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """流式问答（SSE）：先推引用，再逐段推回答文本。

    事件格式: data: {"type":"citations"|"token"|"done"|"error", ...}
    """
    query = retrieval.rewrite_question(db, body.history, body.question)  # 多轮改写
    hits = retrieval.hybrid_search(db, user, query)

    if not hits:
        audit.log(db, user.id, "query", body.question[:100], "未命中")

        def empty():
            yield f"data: {json.dumps({'type': 'token', 'text': _NO_HIT}, ensure_ascii=False)}\n\n"
            yield 'data: {"type":"done"}\n\n'
        return StreamingResponse(empty(), media_type="text/event-stream")

    sources = "\n\n".join(
        f"【资料{i+1}】（来自《{h['doc_title']}》）\n{h['content']}" for i, h in enumerate(hits)
    )
    citations = [
        {"ref": i + 1, "doc_title": h["doc_title"], "chunk_index": h["chunk_index"], "rrf": h["rrf"]}
        for i, h in enumerate(hits)
    ]

    def gen():
        yield f"data: {json.dumps({'type': 'citations', 'items': citations}, ensure_ascii=False)}\n\n"
        full = []
        try:
            for delta in chat_stream(db, _SYSTEM_PROMPT, f"【资料】\n{sources}\n\n【问题】{query}"):
                full.append(delta)
                yield f"data: {json.dumps({'type': 'token', 'text': delta}, ensure_ascii=False)}\n\n"
        except ChatError as e:
            yield f"data: {json.dumps({'type': 'error', 'text': f'生成失败（检索已命中 {len(hits)} 条，可重试）：{e}'}, ensure_ascii=False)}\n\n"
        # 流结束后写审计（拿不到真实 db 提交时机问题：此处 db 仍在请求生命周期内）
        audit.log(db, user.id, "query", body.question[:100], f"命中 {len(hits)} 条（流式）")
        yield 'data: {"type":"done"}\n\n'

    return StreamingResponse(gen(), media_type="text/event-stream")
