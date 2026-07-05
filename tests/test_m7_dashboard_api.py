from __future__ import annotations

import json
import re
import subprocess
import sys
from uuid import uuid4

import pytest

from relayguard.audit_reader import AuditReader
from relayguard.config import Settings
from tests.test_m2_memory import _connect
from tests.test_m4_audit_reader import _run_demo_handoff


SECRET_PATTERNS = [
    re.compile(r"postgresql://", re.I),
    re.compile(r"relayguard_app:[^@]+@", re.I),
    re.compile(r"password", re.I),
]


def _assert_no_secrets(text: str) -> None:
    for pattern in SECRET_PATTERNS:
        assert not pattern.search(text), f"Secret pattern matched: {pattern.pattern}"


@pytest.mark.integration
def test_audit_incident_json_shape(settings: Settings, db_available: None) -> None:
    incident_id = _run_demo_handoff(settings)
    result = subprocess.run(
        [sys.executable, "-m", "apps.cli.audit_incident", "--incident-id", str(incident_id), "--json"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    _assert_no_secrets(result.stdout)
    payload = json.loads(result.stdout)

    assert payload["selected_action"] == "ROUTE_TO_STANDBY"
    assert payload["committed_action_count"] == 1
    assert payload["stale_commit_rejection_count"] == 1
    assert payload["invariant_status"] == "PASS"
    assert len(payload["memory_verdicts"]) >= 1
    assert len(payload["execution_timeline"]) >= 1
    assert len(payload["action_ledger"]) >= 1
    assert "retrieved_memory_count" in payload
    assert "blocked_memory_count" in payload


@pytest.mark.integration
def test_list_incidents_json_no_secrets(settings: Settings, db_available: None) -> None:
    _run_demo_handoff(settings)
    result = subprocess.run(
        [sys.executable, "-m", "apps.cli.list_incidents", "--json", "--limit", "5"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    _assert_no_secrets(result.stdout)
    data = json.loads(result.stdout)
    assert "incidents" in data
    assert len(data["incidents"]) >= 1


@pytest.mark.integration
def test_audit_incident_json_missing_incident(settings: Settings, db_available: None) -> None:
    missing = uuid4()
    result = subprocess.run(
        [sys.executable, "-m", "apps.cli.audit_incident", "--incident-id", str(missing), "--json"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["incident_title"] == "(not found)"
    assert payload["invariant_status"] == "FAIL"
    _assert_no_secrets(result.stdout)


@pytest.mark.integration
def test_dashboard_view_model_fields_from_audit_reader(settings: Settings, db_available: None) -> None:
    from relayguard.store import RelayStore

    incident_id = _run_demo_handoff(settings)
    conn = _connect(settings)
    try:
        report = AuditReader(RelayStore(conn, settings)).build_report(incident_id)
    finally:
        conn.close()

    assert report.selected_action
    assert report.memory_verdicts
    assert report.committed_action_count >= 1
    assert report.retrieved_memory_count >= 0
    assert report.blocked_memory_count >= 0


@pytest.mark.integration
def test_timeline_story_order_in_audit_report(settings: Settings, db_available: None) -> None:
    incident_id = _run_demo_handoff(settings)
    from relayguard.store import RelayStore

    conn = _connect(settings)
    try:
        report = AuditReader(RelayStore(conn, settings)).build_report(incident_id)
    finally:
        conn.close()

    types = [entry.event_type for entry in report.execution_timeline]
    if "memory.retrieved" in types and "memory.classified" in types:
        assert types.index("memory.retrieved") < types.index("memory.classified")
    if "action_intent.reserved" in types:
        lease_after = [i for i, t in enumerate(types) if t == "lease.claimed"]
        if len(lease_after) >= 2:
            assert lease_after[1] > types.index("action_intent.reserved")
