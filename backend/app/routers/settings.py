"""系统设置接口：仅老板可读写；密钥类打码返回。"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.models.database import get_db
from app.models.tables import User
from app.services import audit, settings_svc

router = APIRouter(prefix="/settings", tags=["设置"])

# 厂商目录：国内直连优先（用户偏好），每个厂商给出默认 base_url 和推荐模型
PROVIDERS = [
    {"id": "deepseek", "name": "DeepSeek 深度求索", "base_url": "https://api.deepseek.com",
     "models": ["deepseek-chat", "deepseek-reasoner"], "note": "国内直连·性价比最高"},
    {"id": "moonshot", "name": "Moonshot Kimi 月之暗面", "base_url": "https://api.moonshot.cn/v1",
     "models": ["kimi-latest", "kimi-k2-0905-preview"], "note": "国内直连·长文本强"},
    {"id": "zhipu", "name": "智谱 GLM", "base_url": "https://open.bigmodel.cn/api/paas/v4",
     "models": ["glm-4.5-flash", "glm-4.5"], "note": "国内直连·有免费档"},
    {"id": "qwen", "name": "通义千问 阿里云", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
     "models": ["qwen-plus", "qwen-max"], "note": "国内直连·阿里生态"},
    {"id": "ollama", "name": "Ollama 本地模型（免费离线）", "base_url": "http://localhost:11434/v1",
     "models": ["qwen3:8b", "llama3.1:8b"], "note": "完全本地·零成本·无需 key"},
    {"id": "openai", "name": "OpenAI", "base_url": "https://api.openai.com/v1",
     "models": ["gpt-4o-mini", "gpt-4o"], "note": "⚠️ 需要海外网络"},
    {"id": "custom", "name": "自定义（OpenAI 兼容）", "base_url": "",
     "models": [], "note": "任何兼容 /chat/completions 的接口"},
]


@router.get("/providers")
def list_providers(user: User = Depends(get_current_user)) -> list[dict]:
    """可选模型厂商目录（所有登录用户可读，用于设置页下拉）。"""
    return PROVIDERS


def _require_boss(user: User) -> None:
    """系统设置仅老板可操作。"""
    if user.role != "boss":
        raise HTTPException(403, "权限不足：仅管理员可修改系统设置")


@router.get("")
def get_settings(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    """读设置（密钥打码）。所有登录用户可读（展示用），仅老板可改。"""
    return {key: settings_svc.masked(key, settings_svc.get(db, key)) for key in settings_svc.EDITABLE}


class SettingsIn(BaseModel):
    """设置修改请求。"""

    llm_api_key: str | None = None    # 留空 = 不改
    llm_base_url: str | None = None
    chat_model: str | None = None


@router.put("")
def update_settings(body: SettingsIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    """改设置（仅老板）；留空的字段不动。变更记审计。"""
    _require_boss(user)
    changed = []
    for key in ("llm_api_key", "llm_base_url", "chat_model"):
        value = getattr(body, key)
        if value:
            settings_svc.set_value(db, key, value)
            changed.append(key)
    if changed:
        audit.log(db, user.id, "perm_change", "settings", f"修改系统设置: {','.join(changed)}")
    return {"updated": changed}
