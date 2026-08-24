"""管理接口（仅老板）：部门与用户的增改。全部记审计。"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.security import get_current_user, hash_password
from app.models.database import get_db
from app.models.tables import Department, User
from app.services import audit

router = APIRouter(prefix="/admin", tags=["管理"])


def _boss_only(user: User) -> None:
    """管理操作仅老板可用。"""
    if user.role != "boss":
        raise HTTPException(403, "权限不足：仅管理员可访问")


# ---------- 部门 ----------

@router.get("/departments")
def list_departments(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[dict]:
    """部门列表（登录即可读，上传文档时要用）。"""
    return [{"id": d.id, "name": d.name} for d in db.query(Department).all()]


class DeptIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)


@router.post("/departments")
def create_department(body: DeptIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    """新建部门（仅老板）。"""
    _boss_only(user)
    if db.query(Department).filter_by(name=body.name).first():
        raise HTTPException(400, "部门已存在")
    dept = Department(name=body.name)
    db.add(dept)
    db.commit()
    audit.log(db, user.id, "perm_change", f"dept:{dept.id}", f"新建部门《{dept.name}》")
    return {"id": dept.id, "name": dept.name}


# ---------- 用户 ----------

@router.get("/users")
def list_users(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[dict]:
    """用户列表（仅老板）。"""
    _boss_only(user)
    return [
        {"id": u.id, "username": u.username, "role": u.role,
         "clearance_level": u.clearance_level, "department_id": u.department_id,
         "department": u.department.name if u.department else ""}
        for u in db.query(User).all()
    ]


class UserIn(BaseModel):
    username: str = Field(min_length=2, max_length=50)
    password: str = Field(min_length=6)
    department_id: int
    clearance_level: int = Field(ge=1, le=3)
    role: str = Field(pattern="^(employee|manager|boss)$")


@router.post("/users")
def create_user(body: UserIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    """新建用户（仅老板；MVP 不开放自助注册）。"""
    _boss_only(user)
    if db.query(User).filter_by(username=body.username).first():
        raise HTTPException(400, "用户名已存在")
    if not db.get(Department, body.department_id):
        raise HTTPException(400, "部门不存在")
    u = User(username=body.username, password_hash=hash_password(body.password),
             department_id=body.department_id, clearance_level=body.clearance_level, role=body.role)
    db.add(u)
    db.commit()
    audit.log(db, user.id, "perm_change", f"user:{u.id}", f"新建用户 {u.username}（{u.role}/密级{u.clearance_level}）")
    return {"id": u.id, "username": u.username}


class UserUpdate(BaseModel):
    department_id: int | None = None
    clearance_level: int | None = Field(default=None, ge=1, le=3)
    role: str | None = Field(default=None, pattern="^(employee|manager|boss)$")


@router.put("/users/{user_id}")
def update_user(user_id: int, body: UserUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    """修改用户部门/密级/角色（仅老板；立即生效——权限不走缓存）。"""
    _boss_only(user)
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(404, "用户不存在")
    changes = []
    if body.department_id is not None:
        if not db.get(Department, body.department_id):
            raise HTTPException(400, "部门不存在")
        target.department_id = body.department_id
        changes.append("部门")
    if body.clearance_level is not None:
        target.clearance_level = body.clearance_level
        changes.append(f"密级→{body.clearance_level}")
    if body.role is not None:
        target.role = body.role
        changes.append(f"角色→{body.role}")
    db.commit()
    if changes:
        audit.log(db, user.id, "perm_change", f"user:{user_id}", f"调整 {target.username}: {','.join(changes)}")
    return {"id": user_id, "updated": changes}
