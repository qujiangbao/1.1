"""Keep the test suite deterministic and isolated from host credentials."""
import os


# These assignments intentionally override host-level credentials before test
# modules import app.config and construct cached Settings/LLMGateway instances.
os.environ["APP_ENV"] = "test"
os.environ["OPENAI_API_KEY"] = ""
os.environ["DEEPSEEK_API_KEY"] = ""
os.environ["LLM_WARMUP_ENABLED"] = "false"
os.environ["LLM_VALIDATE_MODELS_ON_STARTUP"] = "false"
os.environ["DATABASE_ENABLED"] = "false"
os.environ["AUTH_ENABLED"] = "false"
os.environ["POLICY_RAG_MODE"] = "crawl4ai"
os.environ["STREAMING_ENABLED"] = "false"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "admin"
os.environ["JWT_SECRET"] = "test-only-jwt-secret-with-at-least-32-characters"
