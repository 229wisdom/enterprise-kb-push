"""权限服务：可见性判断的唯一入口（红线①的业务侧）。"""
from app.models.tables import User


def visible_dept_ids(user: User) -> list[int]:
    """用户可见的部门 id 列表。老板 = 全部（由调用方传全表）；员工/主管 = 本部门。"""
    return [user.department_id]


def effective_clearance(user: User) -> int:
    """用户密级（老板固定 3，其余取自身）。"""
    return 3 if user.role == "boss" else user.clearance_level
