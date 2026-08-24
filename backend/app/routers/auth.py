"""登录接口。"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.security import create_token, verify_password
from app.models.database import get_db
from app.models.tables import User

router = APIRouter(prefix="/auth", tags=["认证"])


class LoginIn(BaseModel):
    """登录请求。"""

    username: str
    password: str


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)) -> dict:
    """账号密码登录，返回 JWT。账号由管理员预置（MVP 不开放注册）。"""
    user = db.query(User).filter_by(username=body.username).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return {
        "token": create_token(user.id),
        "user": {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "department_id": user.department_id,
            "clearance_level": user.clearance_level,
        },
    }
