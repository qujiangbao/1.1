import pytest
from pydantic import ValidationError
from types import SimpleNamespace

from app.config import Settings


def _production_settings(**overrides):
    values = {
        "_env_file": None,
        "app_env": "production",
        "jwt_secret": "a-secure-random-secret-that-is-longer-than-32-characters",
        "auth_enabled": True,
        "admin_password": "strong-admin-password",
        "database_enabled": True,
        "database_url": (
            "postgresql+asyncpg://industrial:strong-password"
            "@postgres/industrial_park"
        ),
        "policy_rag_mode": "crawl4ai",
    }
    values.update(overrides)
    return Settings(**values)


def test_cors_origins_accepts_comma_separated_environment_value(monkeypatch):
    monkeypatch.setenv(
        "CORS_ORIGINS",
        "http://localhost:8080,http://localhost:3000",
    )

    settings = Settings(_env_file=None)

    assert settings.cors_origins == [
        "http://localhost:8080",
        "http://localhost:3000",
    ]


def test_rbac_password_match_uses_bcrypt():
    from app.core.security import hash_password
    from app.database.models.rbac import _password_matches

    password_hash = hash_password("configured-admin-password")

    assert _password_matches("configured-admin-password", password_hash)
    assert not _password_matches("wrong-password", password_hash)


def test_user_context_accepts_database_display_name():
    from app.core.security import UserContext

    context = UserContext(
        user_id="user-admin-001",
        username="admin",
        role="super_admin",
        display_name="系统管理员",
    )

    assert context.display_name == "系统管理员"


@pytest.mark.asyncio
async def test_database_migration_failure_aborts_startup(monkeypatch):
    import app.database.session as database

    class FakeEngine:
        disposed = False

        async def dispose(self):
            self.disposed = True

    fake_engine = FakeEngine()
    monkeypatch.setattr(database, "create_async_engine", lambda *args, **kwargs: fake_engine)
    monkeypatch.setattr(database, "async_sessionmaker", lambda *args, **kwargs: object())

    def fail_migration():
        raise RuntimeError("migration failed")

    monkeypatch.setattr(database, "_run_migrations", fail_migration)

    with pytest.raises(RuntimeError, match="migration failed"):
        await database.init_db("postgresql+asyncpg://user:pass@localhost/test")

    assert fake_engine.disposed is True
    assert database.engine is None
    assert database.SessionLocal is None


def test_production_rejects_placeholder_secrets():
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(
            _env_file=None,
            app_env="production",
            jwt_secret="replace-with-at-least-32-random-characters",
            admin_password="strong-admin-password",
            database_enabled=False,
        )


def test_production_rejects_demo_mode_and_mock_sources():
    with pytest.raises(ValidationError, match="ENABLE_DEMO_MODE"):
        _production_settings(enable_demo_mode=True)
    with pytest.raises(ValidationError, match="Mock enterprise data"):
        _production_settings(enterprise_data_source="mock")
    with pytest.raises(ValidationError, match="Mock policy retrieval"):
        _production_settings(policy_rag_mode="mock")


def test_data_mode_is_real_only_by_default(monkeypatch):
    import app.core.data_mode as data_mode_module

    monkeypatch.setattr(
        data_mode_module,
        "get_settings",
        lambda: SimpleNamespace(app_env="development", enable_demo_mode=False),
    )
    assert data_mode_module.require_allowed_data_mode("real") == "real"
    with pytest.raises(Exception) as exc_info:
        data_mode_module.require_allowed_data_mode("demo")
    assert exc_info.value.status_code == 403


def test_enterprise_adapter_never_silently_falls_back_to_mock():
    from app.tools.adapters.factory import create_adapter

    base = {
        "app_env": "development",
        "enable_demo_mode": False,
        "enterprise_local_json_path": "unused.json",
        "tianyancha_api_key": "",
        "tianyancha_base_url": "https://example.invalid",
        "qichacha_app_key": "",
        "qichacha_secret_key": "",
    }
    with pytest.raises(RuntimeError, match="TIANYANCHA_API_KEY"):
        create_adapter(SimpleNamespace(**base, enterprise_data_source="tianyancha"))
    with pytest.raises(RuntimeError, match="QICHACHA_APP_KEY"):
        create_adapter(SimpleNamespace(**base, enterprise_data_source="qichacha"))
    with pytest.raises(RuntimeError, match="not implemented"):
        create_adapter(SimpleNamespace(**base, enterprise_data_source="government"))
    with pytest.raises(RuntimeError, match="disabled"):
        create_adapter(SimpleNamespace(**base, enterprise_data_source="mock"))


def test_production_rejects_wildcard_cors_with_credentials():
    with pytest.raises(ValidationError, match="CORS_ORIGINS"):
        Settings(
            _env_file=None,
            app_env="production",
            jwt_secret="a-secure-random-secret-that-is-longer-than-32-characters",
            auth_enabled=False,
            database_enabled=False,
            cors_origins=["*"],
        )


def test_rejects_unsafe_jwt_algorithm():
    with pytest.raises(ValidationError, match="JWT_ALGORITHM"):
        Settings(_env_file=None, jwt_algorithm="none")


def test_production_cannot_disable_authentication():
    with pytest.raises(ValidationError, match="AUTH_ENABLED"):
        Settings(
            _env_file=None,
            app_env="production",
            jwt_secret="a-secure-random-secret-that-is-longer-than-32-characters",
            auth_enabled=False,
            database_enabled=True,
            database_url=(
                "postgresql+asyncpg://industrial:strong-password"
                "@postgres/industrial_park"
            ),
        )


def test_production_rejects_default_database_password():
    with pytest.raises(ValidationError, match="DATABASE_URL"):
        Settings(
            _env_file=None,
            app_env="production",
            jwt_secret="a-secure-random-secret-that-is-longer-than-32-characters",
            auth_enabled=True,
            admin_password="strong-admin-password",
            database_enabled=True,
            database_url="postgresql+asyncpg://industrial:industrial@postgres/industrial_park",
        )


def test_checkpoint_url_uses_psycopg_scheme():
    from app.langgraph.graph import _postgres_checkpoint_url

    assert _postgres_checkpoint_url(
        "postgresql+asyncpg://user:pass@postgres:5432/industrial_park"
    ) == "postgresql://user:pass@postgres:5432/industrial_park"


def test_production_pgvector_requires_database():
    with pytest.raises(ValidationError, match="DATABASE_ENABLED"):
        Settings(
            _env_file=None,
            app_env="production",
            jwt_secret="a-secure-random-secret-that-is-longer-than-32-characters",
            auth_enabled=False,
            database_enabled=False,
            policy_rag_mode="pgvector",
            policy_embedding_provider="openai",
            openai_api_key="a-real-looking-openai-key",
        )


def test_production_pgvector_rejects_missing_embedding_key():
    with pytest.raises(ValidationError, match="embedding provider"):
        Settings(
            _env_file=None,
            app_env="production",
            jwt_secret="a-secure-random-secret-that-is-longer-than-32-characters",
            auth_enabled=True,
            admin_password="strong-admin-password",
            database_enabled=True,
            database_url=(
                "postgresql+asyncpg://industrial:strong-password"
                "@postgres/industrial_park"
            ),
            policy_rag_mode="pgvector",
            policy_embedding_provider="openai",
            openai_api_key="",
        )


def test_production_pgvector_accepts_dashscope_embedding_key():
    settings = Settings(
        _env_file=None,
        app_env="production",
        jwt_secret="a-secure-random-secret-that-is-longer-than-32-characters",
        auth_enabled=True,
        admin_password="strong-admin-password",
        database_enabled=True,
        database_url=(
            "postgresql+asyncpg://industrial:strong-password"
            "@postgres/industrial_park"
        ),
        policy_rag_mode="pgvector",
        policy_embedding_provider="dashscope",
        policy_embedding_model="text-embedding-v4",
        policy_embedding_dimensions=1536,
        dashscope_api_key="a-real-looking-dashscope-key",
    )

    assert settings.policy_embedding_provider == "dashscope"
    assert settings.policy_embedding_model == "text-embedding-v4"


def test_production_dashscope_rejects_openai_key_as_substitute():
    with pytest.raises(ValidationError, match="embedding provider"):
        Settings(
            _env_file=None,
            app_env="production",
            jwt_secret=(
                "a-secure-random-secret-that-is-longer-than-32-characters"
            ),
            auth_enabled=True,
            admin_password="strong-admin-password",
            database_enabled=True,
            database_url=(
                "postgresql+asyncpg://industrial:strong-password"
                "@postgres/industrial_park"
            ),
            policy_rag_mode="pgvector",
            policy_embedding_provider="dashscope",
            openai_api_key="a-real-looking-openai-key",
            dashscope_api_key="",
        )
