from __future__ import annotations

import subprocess
import sys
import time
from uuid import UUID

import pytest

from relayguard.audit_reader import AuditReader
from relayguard.config import Settings
from relayguard.store import RelayStore
from tests.test_m2_memory import _connect
from workers.worker import run_worker


@pytest.mark.integration
def test_audit_reader_reports_committed_and_stale_rejection(settings: Settings, db_available: None) -> None:
    incident_id = _run_demo_handoff(settings)
    conn = _connect(settings)
    try:
        report = AuditReader(RelayStore(conn, settings)).build_report(incident_id)
    finally:
        conn.close()

    assert report.committed_action_count == 1
    assert report.stale_commit_rejection_count == 1


@pytest.mark.integration
def test_audit_reader_includes_memory_verdicts_and_selection(settings: Settings, db_available: None) -> None:
    incident_id = _run_demo_handoff(settings)
    conn = _connect(settings)
    try:
        report = AuditReader(RelayStore(conn, settings)).build_report(incident_id)
    finally:
        conn.close()

    assert len(report.memory_verdicts) >= 4
    assert any(verdict.verdict == "AVOID" for verdict in report.memory_verdicts)
    assert report.selected_action == "ROUTE_TO_STANDBY"
    assert report.selection_reason
    assert report.selector_type == "mock"


@pytest.mark.integration
def test_audit_reader_returns_pass_for_valid_demo(settings: Settings, db_available: None) -> None:
    incident_id = _run_demo_handoff(settings)
    conn = _connect(settings)
    try:
        report = AuditReader(RelayStore(conn, settings)).build_report(incident_id)
    finally:
        conn.close()

    assert report.invariant_status == "PASS"
    assert not report.invariant_errors


@pytest.mark.integration
def test_audit_cli_exits_zero_for_valid_incident(settings: Settings, db_available: None) -> None:
    incident_id = _run_demo_handoff(settings)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "apps.cli.audit_incident",
            "--incident-id",
            str(incident_id),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "Invariant" in result.stdout or "Invariants" in result.stdout
    assert "PASS" in result.stdout


def _run_demo_handoff(settings: Settings) -> UUID:
    conn = _connect(settings)
    try:
        store = RelayStore(conn, settings)
        incident = store.create_incident("API latency spike in us-east-1")
        store.seed_demo_memories(incident.incident_id)
        incident_id = incident.incident_id
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
        run_worker(RelayStore(conn, settings_b), incident_id, settings_b)
        store = RelayStore(conn, settings)
        intents = store.list_action_intents(incident_id)
        committed_intent = next(intent for intent in intents if intent.status.value == "committed")
        from workers.worker import run_stale_commit

        run_stale_commit(store, incident_id, "worker-a", 1, committed_intent.intent_id)
    finally:
        conn.close()

    return incident_id
