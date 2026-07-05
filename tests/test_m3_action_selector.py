from __future__ import annotations

import json

import pytest

from relayguard.action_selector import (
    ActionSelectorContext,
    BlockedMemorySummary,
    MemoryContext,
    MockActionSelector,
    build_action_prompt,
    build_selector_context,
    parse_bedrock_response,
)
from relayguard.bedrock_selector import BedrockActionSelector
from relayguard.config import Settings
from relayguard.models import ActionType, MemoryClassification
from relayguard.store import RelayStore
from tests.test_m2_memory import _connect
from workers.worker import run_worker


def test_mock_action_selector_returns_route_to_standby() -> None:
    selector = MockActionSelector()
    context = ActionSelectorContext(
        incident_title="API latency spike",
        incident_severity="high",
        use_memories=[MemoryContext(memory_id="current_runbook", label="current_runbook", content="route to standby")],
    )
    selection = selector.select_action(context)
    assert selection.action_type == ActionType.ROUTE_TO_STANDBY
    assert selection.confidence == 1.0
    assert selection.fallback_used is False


def test_bedrock_valid_response_parses() -> None:
    raw = json.dumps(
        {
            "action_type": "ROUTE_TO_STANDBY",
            "confidence": 0.87,
            "reason": "Approved runbook recommends standby routing.",
            "used_memory_ids": ["current_runbook"],
            "inspected_memory_ids": ["historical_incident"],
        }
    )
    selection = parse_bedrock_response(raw)
    assert selection.action_type == ActionType.ROUTE_TO_STANDBY
    assert selection.confidence == 0.87
    assert selection.fallback_used is False


def test_invalid_json_falls_back_to_escalate() -> None:
    selection = parse_bedrock_response("not json at all")
    assert selection.action_type == ActionType.ESCALATE_TO_HUMAN
    assert selection.fallback_used is True


def test_unknown_action_falls_back_to_escalate() -> None:
    raw = json.dumps(
        {
            "action_type": "DROP_DATABASE",
            "confidence": 0.99,
            "reason": "bad idea",
        }
    )
    selection = parse_bedrock_response(raw)
    assert selection.action_type == ActionType.ESCALATE_TO_HUMAN
    assert selection.fallback_used is True


def test_low_confidence_falls_back_to_escalate() -> None:
    raw = json.dumps(
        {
            "action_type": "ROUTE_TO_STANDBY",
            "confidence": 0.2,
            "reason": "unsure",
        }
    )
    selection = parse_bedrock_response(raw, min_confidence=0.5)
    assert selection.action_type == ActionType.ESCALATE_TO_HUMAN
    assert selection.fallback_used is True


def test_avoid_memory_content_not_in_action_prompt() -> None:
    classified = [
        {
            "memory_id": "mem-use",
            "label": "current_runbook",
            "classification": MemoryClassification.USE.value,
            "reason": "approved",
            "content": "Route traffic to standby when health checks fail.",
        },
        {
            "memory_id": "mem-avoid",
            "label": "failed_restart",
            "classification": MemoryClassification.AVOID.value,
            "reason": "prior action failed",
        },
    ]
    context = build_selector_context("API latency spike", "high", classified)
    prompt = build_action_prompt(context)

    assert "Route traffic to standby" in prompt
    assert "prior action failed" in prompt
    assert "failed_restart" in prompt
    blocked = json.loads(prompt)["blocked_evidence"][0]
    assert "content" not in blocked
    assert "prior restart attempt" not in prompt.lower()


def test_bedrock_selector_uses_injected_client() -> None:
    class FakeClient:
        def converse(self, **kwargs: object) -> dict:
            return {
                "output": {
                    "message": {
                        "content": [
                            {
                                "text": json.dumps(
                                    {
                                        "action_type": "RESTART_SERVICE",
                                        "confidence": 0.91,
                                        "reason": "Restart is safe now.",
                                        "used_memory_ids": [],
                                        "inspected_memory_ids": [],
                                    }
                                )
                            }
                        ]
                    }
                }
            }

    selector = BedrockActionSelector(
        model_id="test-model",
        region="us-east-1",
        client=FakeClient(),
    )
    selection = selector.select_action(
        ActionSelectorContext(incident_title="test", incident_severity="medium")
    )
    assert selection.action_type == ActionType.RESTART_SERVICE
    assert selection.fallback_used is False


def test_get_action_selector_defaults_to_mock() -> None:
    from relayguard.action_selector import get_action_selector

    selector = get_action_selector(Settings.from_env())
    assert selector.selector_type == "mock"


@pytest.mark.integration
def test_worker_mock_mode_commits_one_action(settings: Settings, db_available: None) -> None:
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

    import time

    time.sleep(3)

    settings_b = settings.override(lease_ttl_seconds=5, worker_id="worker-b", fail_after=None)
    conn = _connect(settings)
    try:
        code = run_worker(RelayStore(conn, settings_b), incident_id, settings_b)
        assert code == 0
        s = RelayStore(conn, settings_b)
        assert s.count_committed_actions(incident_id) == 1
        events = s.list_audit_events(incident_id)
        selected = [e for e in events if e.event_type == "action.selected"]
        assert len(selected) == 1
        assert selected[0].details_json["action_type"] == "ROUTE_TO_STANDBY"
        assert selected[0].details_json["selector_type"] == "mock"
    finally:
        conn.close()
