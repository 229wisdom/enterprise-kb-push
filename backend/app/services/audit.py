"""审计日志：所有敏感操作统一留痕（红线⑤）。"""
from sqlalchemy.orm import Session

from app.models.tables import AuditLog


def log(db: Session, user_id: int, action: str, target: str = "", detail: str = "") -> None:
    """写一条审计日志。

    参数: action = upload|query|denied|perm_change
    """
    db.add(AuditLog(user_id=user_id, action=action, target=target, detail=detail))
    db.commit()
