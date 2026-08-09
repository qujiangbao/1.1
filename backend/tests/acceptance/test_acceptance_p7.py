"""P7 System Acceptance — In-repo acceptance test suite

Usage:
    cd backend
    PYTHONPATH=. .venv/bin/python3 -m pytest tests/acceptance/test_acceptance_p7.py -v
    # or:
    PYTHONPATH=. .venv/bin/python3 tests/acceptance/test_acceptance_p7.py
"""

import os, sys, ast
import pytest

BACKEND = os.path.join(os.path.dirname(__file__), "..", "..")
os.chdir(BACKEND)
sys.path.insert(0, ".")


class TestSyntax:
    """1. Backend syntax check — all key .py files"""

    SYNTAX_FILES = [
        "app/main.py", "app/config.py", "app/database/session.py",
        "app/database/models/business.py", "app/database/models/runtime.py",
        "app/database/models/rbac.py",
        "app/core/security.py", "app/core/permissions.py",
        "app/langgraph/graph.py", "app/langgraph/state.py",
        "app/langgraph/nodes/supervisor_nodes.py",
        "app/langgraph/nodes/policy_nodes.py",
        "app/agents/registry.py", "app/agents/executor.py",
        "app/tools/gateway.py", "app/tools/database_tool.py",
        "app/tools/knowledge_tool.py",
        "app/services/event_bus.py", "app/services/event_normalizer.py",
        "app/services/stream_executor.py",
        "app/api/v1/agent.py", "app/api/v1/auth.py",
        "app/api/v1/stream.py", "app/api/v1/health.py",
        "app/api/v1/admin.py", "app/api/v1/business.py",
    ]

    @pytest.mark.parametrize("relpath", SYNTAX_FILES)
    def test_syntax(self, relpath):
        path = os.path.join(BACKEND, relpath)
        assert os.path.exists(path), f"Missing: {relpath}"
        with open(path) as fh:
            ast.parse(fh.read())


class TestModels:
    """2. Database models — table count and key columns"""

    def test_table_count(self):
        from app.database.models.business import Enterprise, EnterpriseProfile, Industry as Ind, Policy as Pol, PolicyDocument, PolicyChunk, Risk
        from app.database.models.runtime import AgentTask, AgentExecution, AgentTrace, AgentMemory, Conversation
        from app.database.models.rbac import User, Role, Permission, UserRole, RolePermission
        tables = {}
        for m in [Enterprise, EnterpriseProfile, Ind, Pol, PolicyDocument, PolicyChunk, Risk,
                  AgentTask, AgentExecution, AgentTrace, AgentMemory, Conversation,
                  User, Role, Permission, UserRole, RolePermission]:
            tables[m.__tablename__] = m
        assert len(tables) >= 17, f"Expected >=17 tables, got {len(tables)}"

    def test_user_columns(self):
        from app.database.models.rbac import User
        cols = {c.name for c in User.__table__.columns}
        assert "data_scope" in cols

    def test_conversation_columns(self):
        from app.database.models.runtime import Conversation
        cols = {c.name for c in Conversation.__table__.columns}
        for c in ["thread_id", "message_count", "last_message_at"]:
            assert c in cols


class TestConfig:
    """3. Config and defaults"""

    def test_config_loads(self):
        from app.config import get_settings
        s = get_settings()
        assert s.app_name is not None

    def test_dev_defaults(self):
        from app.config import get_settings
        s = get_settings()
        assert s.database_enabled is False
        assert s.streaming_enabled is False
        assert s.auth_enabled is False


class TestAgents:
    """4. Agent chain integration"""

    def test_registry_count(self):
        from app.agents.registry import AGENT_REGISTRY
        assert len(AGENT_REGISTRY) >= 6

    def test_intent_routing_count(self):
        from app.langgraph.graph import INTENT_ROUTING
        assert len(INTENT_ROUTING) >= 16

    def test_tool_gateway_count(self):
        from app.tools.gateway import get_tool_gateway
        tg = get_tool_gateway()
        assert len(tg._tools) >= 15


class TestRBAC:
    """5. RBAC permissions"""

    def test_role_count(self):
        from app.core.permissions import ROLE_AGENT_WHITELIST, ROLE_HIERARCHY
        assert len(ROLE_AGENT_WHITELIST) == 6
        assert len(ROLE_HIERARCHY) == 6

    def test_bcrypt(self):
        from app.core.security import hash_password, verify_password
        h = hash_password("test")
        assert h.startswith("$2b$")
        assert verify_password("test", h)
        assert not verify_password("wrong", h)


class TestGraph:
    """6. Supervisor graph compile"""

    @pytest.mark.asyncio
    async def test_supervisor_compile(self):
        from app.langgraph.graph import get_supervisor_graph
        g = await get_supervisor_graph()
        assert g is not None
        assert "InMemorySaver" in type(g.checkpointer).__name__


class TestAPI:
    """7. API route registration"""

    def test_route_count(self):
        from app.api.v1 import router
        count = sum(1 for _ in router.routes)
        assert count >= 8, f"Expected >=8 routes, got {count}"


class TestDocker:
    """8. Docker config files"""

    def test_docker_files(self):
        root = os.path.join(BACKEND, "..")
        for f in ["docker-compose.yml", ".env.production.example", "nginx.conf", "deploy.sh"]:
            assert os.path.exists(os.path.join(root, f)), f"Missing: {f}"


class TestDocs:
    """9. Documentation completeness"""

    def test_phase_docs(self):
        docdir = os.path.join(BACKEND, "..", "docs")
        required_docs = [
            "ARCHITECTURE.md",
            "PROJECT_CONTEXT.md",
            "doc-index.md",
        ]
        assert os.path.isdir(docdir), "Missing public docs directory"
        for filename in required_docs:
            assert os.path.isfile(os.path.join(docdir, filename)), f"Missing: {filename}"
