from __future__ import annotations

import time
from uuid import uuid4

import psycopg
import pytest
from psycopg.rows import dict_row

from relayguard.config import Settings
from relayguard.db import apply_schema
from relayguard.models import ActionType, Memory, MemoryKind
from relayguard.store import DuplicateIntentError, RelayStore
from workers.memory_gate import classify_memory
from workers.worker import run_worker


def _memory(kind: MemoryKind, label: str = "test") -> Memory:
    return Memory(
        memory_id=uuid4(),
        incident_id=uuid4(),
        label=label,
        content="demo content",
        memory_kind=kind,
    )


def _connect(settings: Settings) -> psycopg.Connection:
    return psycopg.connect(
        settings.database_url,
        row_factory=dict_row,
        autocommit=True,
        connect_timeout=5,
    )


def test_failed_memory_classified_as_avoid() -> None:
    assert classify_memory(_memory(MemoryKind.FAILED_RESTART)).value == "AVOID"


def test_expired_memory_classified_as_avoid() -> None:
    assert classify_memory(_memory(MemoryKind.EXPIRED_RUNBOOK)).value == "AVOID"


@pytest.fixture(scope="session")
def settings() -> Settings:
    return Settings.from_env()


@pytest.fixture(scope="session")
def db_available(settings: Settings) -> None:
    try:
        apply_schema(settings)
    except Exception as exc:
        pytest.skip(f"CockroachDB unavailable: {exc}")


@pytest.fixture
def store(settings: Settings, db_available: None) -> RelayStore:
    conn = _connect(settings)
    yield RelayStore(conn, settings)
    conn.close()


@pytest.fixture
def incident(store: RelayStore):
    inc = store.create_incident("test incident")
    store.seed_demo_memories(inc.incident_id)
    return inc.incident_id


@pytest.mark.integration
def test_duplicate_action_intent_rejected(store: RelayStore, incident) -> None:
    claimed = store.claim_incident(incident, "worker-a")
    key = "dup-test-key"
    store.reserve_action_intent(
        incident, ActionType.ROUTE_TO_STANDBY, key, claimed.lease_owner, claimed.lease_epoch
    )
    with pytest.raises(DuplicateIntentError):
        store.reserve_action_intent(
            incident, ActionType.ROUTE_TO_STANDBY, key, claimed.lease_owner, claimed.lease_epoch
        )
    events = store.list_audit_events(incident)
    assert any(e.event_type == "action_intent.duplicate_rejected" for e in events)


@pytest.mark.integration
def test_stale_worker_cannot_commit(store: RelayStore, incident, settings: Settings) -> None:
    settings_short = Settings(
        database_url=settings.database_url,
        lease_ttl_seconds=1,
        worker_id="worker-a",
        fail_after=None,
    )
    store.settings = settings_short

    claimed_a = store.claim_incident(incident, "worker-a")
    intent = store.reserve_action_intent(
        incident,
        ActionType.ROUTE_TO_STANDBY,
        "stale-commit-key",
        claimed_a.lease_owner,
        claimed_a.lease_epoch,
    )
    time.sleep(2)
    store.claim_incident(incident, "worker-b")

    result = store.commit_action(
        incident, intent.intent_id, "worker-a", claimed_a.lease_epoch
    )
    assert result is None
    events = store.list_audit_events(incident)
    assert any(
        e.event_type == "action.commit_rejected" and e.lease_owner == "worker-a"
        for e in events
    )


@pytest.mark.integration
def test_worker_b_resumes_from_checkpoint(incident, settings: Settings) -> None:
    settings_a = Settings(
        database_url=settings.database_url,
        lease_ttl_seconds=2,
        worker_id="worker-a",
        fail_after="ACTION_RESERVED",
    )

    conn = _connect(settings)
    try:
        code = run_worker(RelayStore(conn, settings_a), incident, settings_a)
        assert code == 2
    finally:
        conn.close()

    time.sleep(3)

    settings_b = Settings(
        database_url=settings.database_url,
        lease_ttl_seconds=5,
        worker_id="worker-b",
        fail_after=None,
    )
    conn = _connect(settings)
    try:
        code = run_worker(RelayStore(conn, settings_b), incident, settings_b)
        assert code == 0
    finally:
        conn.close()

    conn = _connect(settings)
    try:
        s = RelayStore(conn, settings_b)
        assert s.count_committed_actions(incident) == 1
        checkpoint = s.get_latest_checkpoint(incident)
        assert checkpoint is not None
        state, owner, _ = checkpoint
        assert owner == "worker-b"
        assert state.phase == "completed"
        assert state.intent_id is not None
    finally:
        conn.close()
