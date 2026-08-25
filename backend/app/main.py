"""应用入口：装配路由与中间件。"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.models.database import Base, engine
from app.models import tables  # noqa: F401  导入即注册全部表模型

app = FastAPI(
    title="企业级分级知识库",
    description="部门隔离 × 密级分级的 RAG 知识库 MVP",
    version="0.1.0",
)


@app.on_event("startup")
def init_db() -> None:
    """启动时自动建表 + 恢复中断的解析任务（parsing → failed 可重试）。"""
    Base.metadata.create_all(engine)
    from app.models.database import SessionLocal
    from app.models.tables import Document
    db = SessionLocal()
    try:
        orphaned = db.query(Document).filter_by(status="parsing").all()
        for doc in orphaned:
            doc.status = "failed"
            doc.fail_reason = "任务中断（服务重启），请点击重试"
        if orphaned:
            db.commit()
    finally:
        db.close()


from app.routers import admin, audit, auth, chat, documents, search, settings  # noqa: E402

app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(chat.router)
app.include_router(audit.router)
app.include_router(search.router)
app.include_router(settings.router)
app.include_router(admin.router)


@app.get("/health")
def health() -> dict:
    """健康检查。"""
    return {"status": "ok", "service": "enterprise-kb", "version": "0.1.0"}


_STATIC = Path(__file__).parent / "static"  # 跟随代码位置，容器内外都正确


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    """前端页面（极简单页应用）。"""
    return FileResponse(_STATIC / "index.html")
