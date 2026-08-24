"""运行时系统设置：DB 覆盖 .env（RAGFlow 同款设计）。

读取顺序：app_settings 表有值 → 用 DB；否则 → .env 默认。
密钥类设置（llm_api_key）对外接口必须打码返回。
"""
from sqlalchemy.orm import Session

from app.core.config import settings as env_settings
from app.models.tables import AppSetting

# 允许在界面配置的键 → 对应的 .env 默认值
EDITABLE = {
    "llm_api_key": lambda: env_settings.openai_api_key,
    "llm_base_url": lambda: env_settings.openai_base_url,
    "chat_model": lambda: env_settings.chat_model,
}


def get(db: Session, key: str) -> str:
    """读设置：DB 优先，回落 .env。"""
    row = db.get(AppSetting, key)
    if row and row.value:
        return row.value
    return EDITABLE[key]()


def set_value(db: Session, key: str, value: str) -> None:
    """写设置（仅允许 EDITABLE 白名单内的键）。"""
    if key not in EDITABLE:
        raise ValueError(f"不允许配置的键: {key}")
    row = db.get(AppSetting, key) or AppSetting(key=key)
    row.value = value
    db.add(row)
    db.commit()


def masked(key: str, value: str) -> str:
    """密钥打码：只露前 6 位（接口返回用）。"""
    if "key" in key and value:
        return value[:6] + "***"
    return value
