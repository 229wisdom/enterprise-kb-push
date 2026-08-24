"""文档接口：上传（F1）、列表。业务逻辑全在 services，这里只接参调服务。"""
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_current_user
from app.models.database import get_db
from app.models.tables import Document, DocumentDepartment, User
from app.services import audit, ingestion

router = APIRouter(prefix="/documents", tags=["文档"])


@router.post("")
def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile,
    clearance_level: int = Form(1),
    department_ids: str = Form(...),  # 逗号分隔，如 "1,2"
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """上传文档：立即返回，解析在后台异步执行（对照 RAGFlow 的任务队列设计）。

    权限规则：员工只能挂到自己部门，密级不能超过自身密级；越权尝试记审计。
    """
    dept_ids = [int(x) for x in department_ids.split(",") if x.strip()]
    if not dept_ids:
        raise HTTPException(400, "必须至少选择一个部门")
    if user.role != "boss" and (set(dept_ids) - {user.department_id} or clearance_level > user.clearance_level):
        audit.log(db, user.id, "denied", file.filename, "上传越权：跨部门或密级超限")
        raise HTTPException(403, "权限不足：只能上传本部门且不高于自身密级的文档")

    save_path = settings.data_dir / "files" / f"{uuid.uuid4().hex}_{file.filename}"
    save_path.parent.mkdir(parents=True, exist_ok=True)
    with save_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    doc = Document(
        title=file.filename, filename=str(save_path),
        uploader_id=user.id, clearance_level=clearance_level, status="parsing",
    )
    db.add(doc)
    db.flush()
    for dept_id in dept_ids:
        db.add(DocumentDepartment(document_id=doc.id, department_id=dept_id))
    db.commit()

    background_tasks.add_task(ingestion.ingest_document_async, doc.id)  # 异步解析
    return {"id": doc.id, "title": doc.title, "status": doc.status, "fail_reason": doc.fail_reason}


@router.get("")
def list_documents(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[dict]:
    """列出【我权限内可见】的文档。"""
    query = (
        db.query(Document)
        .join(DocumentDepartment, DocumentDepartment.document_id == Document.id)
        .filter(Document.clearance_level <= user.clearance_level)
    )
    if user.role != "boss":
        query = query.filter(DocumentDepartment.department_id == user.department_id)
    docs = query.distinct().all()
    return [
        {"id": d.id, "title": d.title, "status": d.status,
         "clearance_level": d.clearance_level, "fail_reason": d.fail_reason}
        for d in docs
    ]


@router.get("/{doc_id}/file")
def open_document_file(doc_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """打开/下载文档原件（带权限校验，越权记审计）。

    校验规则与检索一致：部门匹配（或老板）AND 人密级 ≥ 文档密级。
    """
    doc = db.get(Document, doc_id)
    if doc is None:
        raise HTTPException(404, "文档不存在")
    dept_ids = {d.department_id for d in db.query(DocumentDepartment).filter_by(document_id=doc.id)}
    allowed = (user.role == "boss") or (user.department_id in dept_ids and user.clearance_level >= doc.clearance_level)
    if not allowed:
        audit.log(db, user.id, "denied", f"doc:{doc_id}", "尝试打开无权限文档")
        raise HTTPException(403, "权限不足：该文档不在你的可见范围内")
    path = Path(doc.filename)
    if not path.exists():
        raise HTTPException(404, "原件文件已丢失")
    return FileResponse(path, filename=doc.title)


def _can_manage(db: Session, user: User, doc: Document) -> bool:
    """管理权限：上传者本人、同部门主管、老板。"""
    if user.role == "boss" or doc.uploader_id == user.id:
        return True
    return user.role == "manager" and user.department_id in {
        d.department_id for d in db.query(DocumentDepartment).filter_by(document_id=doc.id)
    }


@router.delete("/{doc_id}")
def delete_document(doc_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    """删除文档：原件 + 切片 + 向量 + 关联关系全清，记审计。"""
    doc = db.get(Document, doc_id)
    if doc is None:
        raise HTTPException(404, "文档不存在")
    if not _can_manage(db, user, doc):
        audit.log(db, user.id, "denied", f"doc:{doc_id}", "尝试删除无权限文档")
        raise HTTPException(403, "权限不足：只有上传者/本部门主管/老板可删除")

    from app.models.tables import Chunk
    from app.storage import vector_store
    vector_store.delete_by_doc(doc_id)                                    # 向量
    db.query(Chunk).filter_by(document_id=doc_id).delete()                # 切片
    db.query(DocumentDepartment).filter_by(document_id=doc_id).delete()   # 部门关联
    path = Path(doc.filename)
    if path.exists():
        path.unlink()                                                     # 原件
    title = doc.title
    db.delete(doc)
    db.commit()
    audit.log(db, user.id, "perm_change", f"doc:{doc_id}", f"删除文档《{title}》")
    return {"deleted": doc_id, "title": title}


@router.post("/{doc_id}/retry")
def retry_document(doc_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    """重试解析失败的文档（仅限 failed 状态；异步执行）。"""
    doc = db.get(Document, doc_id)
    if doc is None:
        raise HTTPException(404, "文档不存在")
    if not _can_manage(db, user, doc):
        raise HTTPException(403, "权限不足")
    if doc.status != "failed":
        raise HTTPException(400, "只有解析失败的文档需要重试")
    doc.status = "parsing"
    db.commit()
    background_tasks.add_task(ingestion.ingest_document_async, doc.id)
    return {"id": doc.id, "status": "parsing"}
