"""六张表的 SQLAlchemy 模型（对应 docs/02-架构.md §4）。"""
from datetime import datetime, timezone

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database import Base


class Department(Base):
    """部门。"""

    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)


class User(Base):
    """用户：role = employee|manager|boss；clearance_level 1普通/2内部/3机密。"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"))
    clearance_level: Mapped[int] = mapped_column(default=1)
    role: Mapped[str] = mapped_column(String(20), default="employee")

    department: Mapped[Department] = relationship()


class Document(Base):
    """文档：status = parsing|ok|failed。"""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    filename: Mapped[str] = mapped_column(String(300))
    uploader_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    clearance_level: Mapped[int] = mapped_column(default=1)
    status: Mapped[str] = mapped_column(String(20), default="parsing")
    fail_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))


class DocumentDepartment(Base):
    """文档-部门多对多（支持跨部门文档）。"""

    __tablename__ = "document_departments"

    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), primary_key=True)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), primary_key=True)


class Chunk(Base):
    """切片：chroma_id 指向向量库中的向量。"""

    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))
    chunk_index: Mapped[int] = mapped_column()
    content: Mapped[str] = mapped_column(Text)
    chroma_id: Mapped[str] = mapped_column(String(64))


class AuditLog(Base):
    """审计日志：action = upload|query|denied|perm_change。"""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(20))
    target: Mapped[str] = mapped_column(String(300), default="")
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))


class AppSetting(Base):
    """运行时系统设置（如 LLM 配置）；值覆盖 .env 默认值。"""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
