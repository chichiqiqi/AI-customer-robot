"""应用配置定义。"""

from pycore.core import BaseSettings


class LLMSettings(BaseSettings):
    """LLM 模型配置。"""
    provider: str = "deepseek"
    model: str = "deepseek-chat"
    api_key: str = ""
    base_url: str = "https://api.deepseek.com/v1"
    temperature: float = 0.7
    max_tokens: int = 2048


class EmbeddingSettings(BaseSettings):
    """向量化模型配置。"""
    provider: str = "qwen"
    model: str = "text-embedding-v4"
    api_key: str = ""
    base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    dimension: int = 1536


class RetrievalSettings(BaseSettings):
    """检索配置。"""
    qa_threshold: float = 0.85
    vector_top_k: int = 3
    chunk_size: int = 500
    chunk_overlap: int = 50


class AppSettings(BaseSettings):
    """应用主配置，映射 app.toml 中的 [app] 段。"""
    debug: bool = False
    secret_key: str = "change-me"
    database_url: str = "sqlite+aiosqlite:///./data/app.db"
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = ["http://localhost:5173"]

    # 嵌套配置（由 ConfigManager 的 raw config 手动加载）
    llm: LLMSettings = LLMSettings()
    embedding: EmbeddingSettings = EmbeddingSettings()
    retrieval: RetrievalSettings = RetrievalSettings()
