"""审计日志查询接口（F5）：主管查本部门、老板查全部。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.models.database import get_db
from app.models.tables import AuditLog, User

router = APIRouter(prefix="/audit-logs", tags=["审计"])


@router.get("")
def list_audit_logs(
    limit: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """查询审计日志（按角色限定范围）。

    - 老板：全部日志
    - 主管：本部门成员（含自己）的日志
    - 普通员工：仅自己的日志
    """
    query = db.query(AuditLog).order_by(AuditLog.id.desc())
    if user.role == "manager":
        member_ids = [u.id for u in db.query(User).filter_by(department_id=user.department_id)]
        query = query.filter(AuditLog.user_id.in_(member_ids))
    elif user.role != "boss":
        query = query.filter(AuditLog.user_id == user.id)
    logs = query.limit(limit).all()
    return [
        {"id": l.id, "user_id": l.user_id, "action": l.action,
         "target": l.target, "detail": l.detail, "created_at": str(l.created_at)}
        for l in logs
    ]
