import asyncio
import pytest
from types import SimpleNamespace
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import insert

from app.database.models.business import PolicyChunk
from app.services.chunker import ChunkData
from app.services.embedding import EmbeddingService
from app.services.policy_ingestion import _chunk_provenance
from app.services.vector_store import VectorStore
from app.tools.adapters.policy_crawl4ai import CrawledPolicy
from app.tools.knowledge_tool import KnowledgeTool


def test_policy_chunk_insert_compiles_with_typed_vector_and_metadata():
    statement = insert(PolicyChunk).values(
        chunk_id="GZ-FG-1-c000",
        policy_id="GZ-FG-1",
        chunk_index=0,
        content="政策正文",
        embedding=[0.0] * 1536,
        metadata_={"source_url": "https://www.gz.gov.cn/example"},
    )

    compiled = str(statement.compile(dialect=postgresql.dialect()))
    assert "embedding" in compiled
    assert "metadata" in compiled


def test_alembic_head_preserves_the_full_investment_migration_chain():
    config = Config("alembic.ini")
    config.set_main_option("script_location", "migrations")
    scripts = ScriptDirectory.from_config(config)

    assert scripts.get_current_head() == "010_remove_demo_conditions"
    assert (
        scripts.get_revision("003_investment_candidate").down_revision
        == "002_policy_pgvector"
    )
    assert (
        scripts.get_revision("004_investment_agent_outputs").down_revision
        == "003_investment_candidate"
    )
    assert (
        scripts.get_revision("005_investment_crm").down_revision
        == "004_investment_agent_outputs"
    )
    assert (
        scripts.get_revision("006_policy_conditions").down_revision
        == "005_investment_crm"
    )
    assert (
        scripts.get_revision("007_recommendation_exposure").down_revision
        == "006_policy_conditions"
    )
    assert (
        scripts.get_revision("008_policy_crawler").down_revision
        == "007_recommendation_exposure"
    )
    assert (
        scripts.get_revision("009_business_indexes").down_revision
        == "008_policy_crawler"
    )
    assert (
        scripts.get_revision("010_remove_demo_conditions").down_revision
        == "009_business_indexes"
    )


def test_vector_store_rejects_wrong_embedding_dimension():
    chunk = ChunkData(
        chunk_id="GZ-FG-1-c000",
        policy_id="GZ-FG-1",
        content="政策正文",
    )

    with pytest.raises(ValueError, match="1536"):
        VectorStore._validate([chunk], [[0.0] * 32])


@pytest.mark.asyncio
async def test_embedding_error_never_falls_back_to_mock(monkeypatch):
    service = EmbeddingService(
        provider="openai",
        model="embedding-model",
        dimensions=1536,
    )

    async def fail_request(texts):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(service, "_openai_embed", fail_request)

    with pytest.raises(RuntimeError, match="provider unavailable"):
        await service.embed_batch(["政策正文"])


@pytest.mark.asyncio
async def test_dashscope_embedding_uses_1536_dimensions_and_batches(
    monkeypatch,
):
    import httpx

    calls = []

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "data": [
                    {
                        "index": index,
                        "embedding": [float(index)] * 1536,
                    }
                    for index, _text in enumerate(self.payload["input"])
                ]
            }

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, url, *, headers, json, timeout):
            calls.append(
                {
                    "url": url,
                    "headers": headers,
                    "json": json,
                    "timeout": timeout,
                }
            )
            return FakeResponse(json)

    monkeypatch.setattr(
        "app.config.get_settings",
        lambda: SimpleNamespace(
            dashscope_api_key="dashscope-test-key",
            dashscope_base_url=(
                "https://dashscope.aliyuncs.com/compatible-mode/v1/"
            ),
        ),
    )
    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    service = EmbeddingService(
        provider="dashscope",
        model="text-embedding-v4",
        dimensions=1536,
    )

    vectors = await service.embed_batch(
        [f"政策正文-{index}" for index in range(11)]
    )

    assert len(vectors) == 11
    assert all(len(vector) == 1536 for vector in vectors)
    assert [len(call["json"]["input"]) for call in calls] == [10, 1]
    assert all(
        call["url"]
        == "https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings"
        for call in calls
    )
    assert all(
        call["json"]["dimensions"] == 1536
        and call["json"]["model"] == "text-embedding-v4"
        and call["json"]["encoding_format"] == "float"
        for call in calls
    )
    assert all(
        call["headers"]["Authorization"] == "Bearer dashscope-test-key"
        for call in calls
    )


def test_pgvector_chunk_provenance_preserves_canonical_parser_and_source():
    document = CrawledPolicy(
        policy_id="GZ-FG-1",
        title="政策",
        content="政策正文",
        source_url="https://www.gz.gov.cn/example",
        document_number="穗发改规字〔2026〕1号",
        parser="docling",
        parser_version="docling==2.115.0; table=TableFormerV1; ocr=false",
        parse_status="success",
        input_sha256="a" * 64,
        selected_artifact="enhanced/canonical/policy.md",
    )

    metadata = _chunk_provenance(
        document,
        provider="openai",
        model="text-embedding-3-small",
    )

    assert metadata["source_url"] == document.source_url
    assert metadata["parser"] == "docling"
    assert metadata["parse_status"] == "success"
    assert metadata["input_sha256"] == "a" * 64
    assert metadata["selected_artifact"] == "enhanced/canonical/policy.md"
    assert metadata["embedding_provider"] == "openai"
    assert metadata["embedding_model"] == "text-embedding-3-small"


@pytest.mark.asyncio
async def test_sync_knowledge_tool_uses_bound_application_loop(monkeypatch):
    tool = KnowledgeTool()
    application_loop = asyncio.get_running_loop()
    tool.bind_event_loop(application_loop)

    async def fake_search(_params):
        return {"event_loop": id(asyncio.get_running_loop())}

    monkeypatch.setattr(tool, "policy_hybrid_search", fake_search)

    result = await asyncio.to_thread(
        tool.policy_hybrid_search_sync,
        {"query": "科技创新"},
    )

    assert result["event_loop"] == id(application_loop)
