"""全局配置：从 .env 读取（pydantic-settings）。
所有配置集中在此，其他模块禁止直接读环境变量。
"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录（enterprise-kb/），data/ 与 .env 都在这里
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent


class Settings(BaseSettings):
    """应用配置。"""

    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    # LLM（生成）
    openai_api_key: str = ""                          # DeepSeek key
    openai_base_url: str = "https://api.deepseek.com"
    chat_model: str = "deepseek-chat"

    # Embedding（本机 Ollama）
    ollama_base_url: str = "http://localhost:11434"
    embed_model: str = "bge-m3"

    # 存储路径
    data_dir: Path = BASE_DIR / "data"
    sqlite_path: str = str(BASE_DIR / "data" / "app.db")

    # 检索参数
    chunk_token_budget: int = 512     # 每块 token 预算
    retrieve_top_k: int = 8           # 粗召回数量
    final_top_n: int = 3              # 最终送入生成的切片数
    vector_distance_threshold: float = 0.62  # 余弦距离阈值（>此值视为不相关，丢弃）
    rerank_enabled: bool = True       # 粗排后 LLM 精排（Rerank）

    # JWT 鉴权
    jwt_secret: str = "change-me-in-.env"
    jwt_expire_minutes: int = 720


settings = Settings()
