from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_env: str = "development"
    app_name: str = "Industrial Park Agent API"

    # Database
    database_url: str = "postgresql+asyncpg://user:pass@localhost:5432/industrial_park"
    database_enabled: bool = False
    redis_url: str = "redis://localhost:6379"

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    # DeepSeek (国内可用，OpenAI 兼容接口)
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"

    # Embedding
    embedding_model: str = "text-embedding-3-small"

    # Auth
    jwt_secret: str = "change-this"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440
    auth_enabled: bool = False
    admin_username: str = "admin"
    admin_password: str = "admin"

    # Enterprise Data (P0)
    enterprise_data_source: str = "mock"
    tianyancha_api_key: str = ""
    tianyancha_base_url: str = "https://api.tianyancha.com"
    qichacha_app_key: str = ""
    qichacha_secret_key: str = ""
    enterprise_cache_ttl: int = 3600

    # Policy RAG (P1)
    policy_rag_mode: str = "mock"
    policy_embedding_provider: str = "deepseek"
    policy_embedding_model: str = "text-embedding-3-small"
    policy_embedding_dimensions: int = 1536

    # Streaming (P3)
    streaming_enabled: bool = False       # 默认关闭，保持 v1.2 兼容
    streaming_heartbeat_seconds: int = 15  # SSE 心跳间隔

    # App
    log_level: str = "INFO"
    cors_origins: list[str] = ["http://localhost:3000"]
    llm_warmup_enabled: bool = True

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value):
        if isinstance(value, str) and not value.lstrip().startswith("["):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @model_validator(mode="after")
    def validate_production_secrets(self):
        if self.app_env.lower() == "production":
            if self.jwt_secret == "change-this" or len(self.jwt_secret) < 32:
                raise ValueError("JWT_SECRET must be at least 32 characters in production")
            if self.auth_enabled and self.admin_password == "admin":
                raise ValueError("ADMIN_PASSWORD must be changed in production")
        return self

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
