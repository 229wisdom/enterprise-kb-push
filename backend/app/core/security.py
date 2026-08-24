"""鉴权：密码哈希、JWT 签发与校验、当前用户依赖。"""
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.database import get_db
from app.models.tables import User

_bearer = HTTPBearer()


def hash_password(plain: str) -> str:
    """生成密码哈希（只存哈希，不存明文）。"""
    return bcrypt.hashpw(plain.encode()[:72], bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """校验密码。"""
    return bcrypt.checkpw(plain.encode()[:72], hashed.encode())


def create_token(user_id: int) -> str:
    """签发 JWT（身份令牌）。"""
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def get_current_user(
    cred: HTTPAuthorizationCredentials = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """FastAPI 依赖：从请求头解出当前登录用户，未登录抛 401。"""
    try:
        payload = jwt.decode(cred.credentials, settings.jwt_secret, algorithms=["HS256"])
        user = db.get(User, int(payload["sub"]))
    except Exception:
        user = None
    if user is None:
        raise HTTPException(status_code=401, detail="未登录或登录已过期")
    return user
