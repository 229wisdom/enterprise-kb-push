"""种子数据：创建演示用的部门和账号（账号由管理员预置，不开放注册）。

用法: python -m scripts.seed
"""
from app.core.security import hash_password
from app.models.database import Base, SessionLocal, engine
from app.models.tables import Department, User

SEED = [
    # (部门, [(用户名, 密码, 密级, 角色)])
    ("技术部", [("tech_emp", "tech123", 1, "employee"), ("tech_mgr", "techmgr123", 2, "manager")]),
    ("财务部", [("fin_emp", "fin123", 1, "employee")]),
    ("总裁办", [("boss", "boss123", 3, "boss")]),
]


def main() -> None:
    """建表并写入种子数据（已存在则跳过）。"""
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        for dept_name, users in SEED:
            dept = db.query(Department).filter_by(name=dept_name).first() or Department(name=dept_name)
            db.add(dept)
            db.flush()
            for username, password, clearance, role in users:
                if db.query(User).filter_by(username=username).first():
                    continue
                db.add(User(
                    username=username, password_hash=hash_password(password),
                    department_id=dept.id, clearance_level=clearance, role=role,
                ))
        db.commit()
        print("种子数据就绪：")
        for dept_name, users in SEED:
            for username, _, clearance, role in users:
                print(f"  {dept_name} | {username} | 密级{clearance} | {role}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
