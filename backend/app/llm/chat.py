"""LLM 对话客户端（OpenAI 兼容接口，配置走运行时设置）。"""
import httpx


class ChatError(Exception):
    """生成失败（网络/key/限流等）。"""


def chat(db, system_prompt: str, user_prompt: str) -> str:
    """调 LLM 生成回答（配置走运行时设置，界面可改）。

    参数: db 数据库会话（读设置用）；system_prompt 规则；user_prompt 资料+问题
    返回: 模型生成的文本
    """
    from app.services import settings_svc
    api_key = settings_svc.get(db, "llm_api_key")
    base_url = settings_svc.get(db, "llm_base_url")
    model = settings_svc.get(db, "chat_model")
    if not api_key:
        raise ChatError("未配置模型 API Key（请到 设置 页配置）")
    try:
        resp = httpx.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.1,  # 低温度=少发挥，防幻觉
            },
            timeout=120,
        )
        resp.raise_for_status()
    except Exception as e:
        raise ChatError(f"LLM 调用失败: {e}") from e
    return resp.json()["choices"][0]["message"]["content"]
