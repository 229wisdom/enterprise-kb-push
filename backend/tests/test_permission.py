"""权限规则单元测试（红线①的业务侧）。"""
from app.models.tables import User
from app.services.permission import effective_clearance, visible_dept_ids


def _user(role: str, clearance: int, dept: int = 1) -> User:
    return User(id=1, username="t", password_hash="x", department_id=dept,
                clearance_level=clearance, role=role)


def test_employee_sees_only_own_dept() -> None:
    """普通员工可见部门 = 仅本部门。"""
    assert visible_dept_ids(_user("employee", 1, dept=2)) == [2]


def test_boss_clearance_always_max() -> None:
    """老板密级视为 3（跨部门+最高密级）。"""
    assert effective_clearance(_user("boss", 1)) == 3


def test_employee_clearance_own() -> None:
    """普通员工密级取自身值。"""
    assert effective_clearance(_user("employee", 2)) == 2
