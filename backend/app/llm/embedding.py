"""Ollama bge-m3 向量化客户端（本机调用，数据不出网）。"""
import httpx

from app.core.config import settings


class EmbeddingError(Exception):
    """向量化失败（Ollama 未启动/模型缺失等）。"""


def embed_texts(texts: list[str]) -> list[list[float]]:
    """把一组文本转成向量。

    参数: texts 待向量化的文本列表
    返回: 与 texts 等长的向量列表（bge-m3 为 1024 维）
    """
    try:
        resp = httpx.post(
            f"{settings.ollama_base_url}/api/embed",
            json={"model": settings.embed_model, "input": texts},
            timeout=120,
        )
        resp.raise_for_status()
    except Exception as e:
        raise EmbeddingError(f"Ollama 向量化失败，请确认 Ollama 已启动且装有 {settings.embed_model}: {e}") from e
    return resp.json()["embeddings"]
