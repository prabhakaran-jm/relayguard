from __future__ import annotations

import time

import psycopg
import pytest
from psycopg.rows import dict_row

from relayguard.config import Settings
from relayguard.db import apply_schema
from relayguard.demo_corpus import DEMO_CORPUS
from relayguard.embeddings import BedrockTitanEmbeddingProvider, DeterministicEmbeddingProvider, cosine_similarity
from relayguard.models import ActionType, MemoryKind
from relayguard.store import RelayStore
from workers.memory_gate import classify_memory
from workers.memory_retriever import retrieve_similar_memories
from workers.worker import run_worker


def _connect(settings: Settings) -> psycopg.Connection:
    return psycopg.connect(
        settings.database_url,
        row_factory=dict_row,
        autocommit=True,
        connect_timeout=5,
    )


def test_deterministic_embeddings_rank_demo_memories_above_unrelated() -> None:
    embedder = DeterministicEmbeddingProvider()
    incident_text = "API latency spike in us-east-1"
    query = embedder.embed(incident_text, is_query=True)

    demo_contents = {
        MemoryKind.CURRENT_RUNBOOK: "Route traffic to standby when primary health checks fail.",
        MemoryKind.EXPIRED_RUNBOOK: "Restart primary node immediately (deprecated 2024-Q1).",
        MemoryKind.FAILED_RESTART: "Prior restart attempt caused cascading failure.",
        MemoryKind.HISTORICAL_INCIDENT: "Similar outage in us-east-1 resolved via standby routing.",
    }
    unrelated_content = "Quarterly billing report template for finance team."

    demo_scores = [
        cosine_similarity(query, embedder.embed(content))
        for kind, content in demo_contents.items()
    ]
    unrelated_score = cosine_similarity(query, embedder.embed(unrelated_content))

    assert min(demo_scores) > unrelated_score


def test_demo_corpus_is_realistic_scale_with_no_duplicate_labels() -> None:
    assert len(DEMO_CORPUS) >= 50
    labels = [label for label, _, _ in DEMO_CORPUS]
    assert len(labels) == len(set(labels))
    for original in ("current_runbook", "expired_runbook", "failed_restart", "historical_incident", "unrelated_finance"):
        assert original in labels


def test_demo_corpus_top5_surfaces_signal_over_noise() -> None:
    embedder = DeterministicEmbeddingProvider()
    incident_text = "API latency spike in us-east-1"
    query = embedder.embed(incident_text, is_query=True)

    scored = sorted(
        (
            (cosine_similarity(query, embedder.embed(content)), label, kind.value)
            for label, content, kind in DEMO_CORPUS
        ),
        reverse=True,
    )
    top5_labels = {label for _, label, _ in scored[:5]}
    top3_kinds = [kind for _, _, kind in scored[:3]]

    assert "current_runbook" in top5_labels
    assert "historical_incident" in top5_labels
    assert MemoryKind.UNRELATED.value not in top3_kinds


def test_deterministic_embeddings_ignore_memory_kind() -> None:
    """memory_kind is accepted for interface compatibility but must not affect the vector."""
    embedder = DeterministicEmbeddingProvider()
    content = "Route traffic to standby when primary health checks fail."
    assert embedder.embed(content) == embedder.embed(content, memory_kind="current_runbook")
    assert embedder.embed(content) == embedder.embed(content, memory_kind="unrelated")


class _FakeBedrockBody:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return self._payload


class _FakeBedrockClient:
    def __init__(self) -> None:
        self.last_kwargs: dict[str, object] = {}

    def invoke_model(self, *, modelId: str, body: str):
        import json

        self.last_kwargs = {"modelId": modelId, "body": json.loads(body)}
        embedding = [0.1] * json.loads(body)["dimensions"]
        return {"body": _FakeBedrockBody(json.dumps({"embedding": embedding}).encode())}


def test_bedrock_titan_embedding_provider_builds_expected_request() -> None:
    fake_client = _FakeBedrockClient()
    provider = BedrockTitanEmbeddingProvider(dimensions=256, client=fake_client)

    result = provider.embed("API latency spike in us-east-1")

    assert fake_client.last_kwargs["modelId"] == "amazon.titan-embed-text-v2:0"
    assert fake_client.last_kwargs["body"] == {
        "inputText": "API latency spike in us-east-1",
        "dimensions": 256,
        "normalize": True,
    }
    assert len(result) == 256
    assert provider.dimensions == 256


def test_bedrock_titan_embedding_provider_rejects_unsupported_dimensions() -> None:
    with pytest.raises(ValueError):
        BedrockTitanEmbeddingProvider(dimensions=128)


def test_memory_gate_expired_runbook_has_avoid_reason() -> None:
    from tests.test_relayguard import _memory

    verdict, reason = classify_memory(_memory(MemoryKind.EXPIRED_RUNBOOK))
    assert verdict.value == "AVOID"
    assert "expired" in reason.lower() or "deprecated" in reason.lower()


def test_memory_gate_failed_restart_has_avoid_reason() -> None:
    from tests.test_relayguard import _memory

    verdict, reason = classify_memory(_memory(MemoryKind.FAILED_RESTART))
    assert verdict.value == "AVOID"
    assert "failed" in reason.lower()


@pytest.fixture(scope="session")
def settings() -> Settings:
    return Settings.from_env()


@pytest.fixture(scope="session")
def db_available(settings: Settings) -> None:
    try:
        apply_schema(settings)
    except Exception as exc:
        pytest.skip(f"CockroachDB unavailable: {exc}")


@pytest.mark.integration
def test_semantic_retrieval_returns_ranked_memories(settings: Settings, db_available: None) -> None:
    conn = _connect(settings)
    try:
        store = RelayStore(conn, settings)
        incident = store.create_incident("API latency spike in us-east-1")
        store.seed_demo_memories(incident.incident_id)

        results = retrieve_similar_memories(
            store,
            incident.incident_id,
            incident.title,
            limit=5,
        )
        assert len(results) >= 4
        labels = [item.metadata["label"] for item in results]
        assert "current_runbook" in labels
        assert "historical_incident" in labels
        top3_kinds = [item.memory_type for item in results[:3]]
        assert MemoryKind.UNRELATED.value not in top3_kinds
        assert results[0].similarity_score >= results[-1].similarity_score
    finally:
        conn.close()


@pytest.mark.integration
def test_worker_audit_contains_memory_events(settings: Settings, db_available: None) -> None:
    settings_a = settings.override(
        lease_ttl_seconds=2, worker_id="worker-a", fail_after="ACTION_RESERVED"
    )

    conn = _connect(settings)
    try:
        store = RelayStore(conn, settings)
        inc = store.create_incident("API latency spike in us-east-1")
        store.seed_demo_memories(inc.incident_id)
        incident_id = inc.incident_id

        code = run_worker(RelayStore(conn, settings_a), incident_id, settings_a)
        assert code == 2

        events = store.list_audit_events(incident_id)
        types = [event.event_type for event in events]
        assert "memory.retrieved" in types
        assert types.count("memory.classified") >= 4
    finally:
        conn.close()


@pytest.mark.integration
def test_worker_demo_still_commits_only_one_action(settings: Settings, db_available: None) -> None:
    conn = _connect(settings)
    try:
        store = RelayStore(conn, settings)
        inc = store.create_incident("API latency spike in us-east-1")
        store.seed_demo_memories(inc.incident_id)
        incident_id = inc.incident_id
    finally:
        conn.close()

    settings_a = settings.override(
        lease_ttl_seconds=2, worker_id="worker-a", fail_after="ACTION_RESERVED"
    )
    conn = _connect(settings)
    try:
        run_worker(RelayStore(conn, settings_a), incident_id, settings_a)
    finally:
        conn.close()

    time.sleep(3)

    settings_b = settings.override(lease_ttl_seconds=5, worker_id="worker-b", fail_after=None)
    conn = _connect(settings)
    try:
        code = run_worker(RelayStore(conn, settings_b), incident_id, settings_b)
        assert code == 0
        assert RelayStore(conn, settings_b).count_committed_actions(incident_id) == 1
    finally:
        conn.close()
