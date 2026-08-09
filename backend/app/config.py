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
    deepseek_model: str = "deepseek-v4-pro"
    llm_validate_models_on_startup: bool = True

    # Alibaba Cloud Model Studio / DashScope embeddings
    dashscope_api_key: str = ""
    dashscope_base_url: str = (
        "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )

    # Embedding
    embedding_model: str = "text-embedding-3-small"

    # Auth
    # Long enough to avoid weak-HMAC defaults during local development. The
    # production validator still rejects the ``change-`` placeholder.
    jwt_secret: str = "change-this-development-only-secret"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440
    auth_enabled: bool = False
    admin_username: str = "admin"
    admin_password: str = "admin"

    # Enterprise Data (P0)
    enterprise_data_source: str = "local_json"
    enterprise_local_json_path: str = "data/enterprises/enterprise_import_enriched.json"
    tianyancha_api_key: str = ""
    tianyancha_base_url: str = "https://api.tianyancha.com"
    qichacha_app_key: str = ""
    qichacha_secret_key: str = ""
    enterprise_cache_ttl: int = 3600

    # Policy RAG (P1)
    policy_rag_mode: str = "crawl4ai"
    policy_crawl_data_dir: str = "data/policy_snapshots"
    policy_crawler_source_config: str = "app/data/guangzhou_policy_sources.json"
    policy_crawler_api_url: str = "http://localhost:11235"
    policy_crawler_api_token: str = ""
    policy_crawler_refresh_days: int = 7
    policy_embedding_provider: str = "dashscope"
    policy_embedding_model: str = "text-embedding-v4"
    policy_embedding_dimensions: int = 1536

    # Supervisor graph checkpointer (P2 deployment optimization)
    #   postgres = persistent PostgreSQL (default; heavy for 2GB RAM)
    #   memory   = in-memory (lightest; no restart persistence, grows with sessions)
    #   sqlite   = on-disk SQLite (lightweight + restart-safe; recommended for 2GB)
    supervisor_checkpointer: str = "postgres"

    # Streaming (P3)
    streaming_enabled: bool = False       # 默认关闭，保持 v1.2 兼容
    streaming_heartbeat_seconds: int = 15  # SSE 心跳间隔

    # App
    log_level: str = "INFO"
    # Include ``str`` in the input type so older pydantic-settings versions do
    # not force JSON decoding before the comma-separated validator can run.
    cors_origins: str | list[str] = ["http://localhost:3000"]
    llm_warmup_enabled: bool = True

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value):
        if isinstance(value, str) and not value.lstrip().startswith("["):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("policy_rag_mode")
    @classmethod
    def validate_policy_rag_mode(cls, value: str):
        normalized = value.strip().lower()
        if normalized not in {"mock", "crawl4ai", "pgvector"}:
            raise ValueError("POLICY_RAG_MODE must be mock, crawl4ai, or pgvector")
        return normalized

    @field_validator("enterprise_data_source")
    @classmethod
    def validate_enterprise_data_source(cls, value: str):
        normalized = value.strip().lower()
        if normalized not in {
            "local_json", "mock", "tianyancha", "qichacha", "government"
        }:
            raise ValueError(
                "ENTERPRISE_DATA_SOURCE must be local_json, mock, "
                "tianyancha, qichacha, or government"
            )
        return normalized

    @field_validator("policy_embedding_provider")
    @classmethod
    def validate_policy_embedding_provider(cls, value: str):
        normalized = value.strip().lower()
        if normalized not in {"mock", "openai", "dashscope"}:
            raise ValueError(
                "POLICY_EMBEDDING_PROVIDER must be mock, openai, or dashscope"
            )
        return normalized

    @field_validator("policy_embedding_dimensions")
    @classmethod
    def validate_policy_embedding_dimensions(cls, value: int):
        if value != 1536:
            raise ValueError(
                "POLICY_EMBEDDING_DIMENSIONS must be 1536 to match the database schema"
            )
        return value

    @field_validator("jwt_algorithm")
    @classmethod
    def validate_jwt_algorithm(cls, value: str):
        normalized = value.strip().upper()
        if normalized not in {"HS256", "HS384", "HS512"}:
            raise ValueError("JWT_ALGORITHM must be HS256, HS384, or HS512")
        return normalized

    @field_validator("supervisor_checkpointer")
    @classmethod
    def validate_supervisor_checkpointer(cls, value: str):
        normalized = value.strip().lower()
        if normalized not in {"postgres", "memory", "sqlite"}:
            raise ValueError(
                "SUPERVISOR_CHECKPOINTER must be postgres, memory, or sqlite"
            )
        return normalized

    @model_validator(mode="after")
    def validate_production_secrets(self):
        if self.app_env.lower() == "production":
            def is_placeholder(value: str) -> bool:
                normalized = value.strip().lower()
                return (
                    not normalized
                    or normalized == "***"
                    or normalized.startswith(("change-", "replace-with-", "local-dev-"))
                )

            if is_placeholder(self.jwt_secret) or len(self.jwt_secret) < 32:
                raise ValueError("JWT_SECRET must be at least 32 characters in production")
            if "*" in self.cors_origins or "null" in self.cors_origins:
                raise ValueError(
                    "CORS_ORIGINS must list explicit origins in production"
                )
            if not self.database_enabled:
                raise ValueError("DATABASE_ENABLED must be true in production")
            if not self.auth_enabled:
                raise ValueError("AUTH_ENABLED must be true in production")
            if self.auth_enabled and (
                self.admin_password == "admin" or is_placeholder(self.admin_password)
            ):
                raise ValueError("ADMIN_PASSWORD must be changed in production")
            if self.database_enabled and (
                "industrial:industrial@" in self.database_url
                or "replace-with-" in self.database_url
                or "local-dev-" in self.database_url
            ):
                raise ValueError("DATABASE_URL must use a non-placeholder password in production")
            for name, value in (
                ("OPENAI_API_KEY", self.openai_api_key),
                ("DEEPSEEK_API_KEY", self.deepseek_api_key),
                ("DASHSCOPE_API_KEY", self.dashscope_api_key),
            ):
                if value and is_placeholder(value):
                    raise ValueError(f"{name} contains a production placeholder")
            if self.policy_rag_mode == "pgvector":
                if not self.database_enabled:
                    raise ValueError(
                        "DATABASE_ENABLED must be true when POLICY_RAG_MODE=pgvector"
                    )
                if self.policy_embedding_provider == "mock":
                    raise ValueError(
                        "Mock policy embeddings are forbidden with pgvector in production"
                    )
                required_key = (
                    self.dashscope_api_key
                    if self.policy_embedding_provider == "dashscope"
                    else self.openai_api_key
                )
                if is_placeholder(required_key):
                    raise ValueError(
                        "The selected policy embedding provider requires a real API key"
                    )
        return self

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
