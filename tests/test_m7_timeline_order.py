from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from relayguard.audit_timeline import sort_audit_events_story_order, story_ordered_event_types
from relayguard.models import AuditEvent


def _event(event_type: str, *, epoch: int | None = None, score: float | None = None, label: str = "") -> AuditEvent:
    details: dict = {}
    if score is not None:
        details["similarity_score"] = score
    if label:
        details["label"] = label
    return AuditEvent(
        event_id=uuid4(),
        incident_id=uuid4(),
        event_type=event_type,
        lease_owner="worker-a" if epoch != 2 else "worker-b",
        lease_epoch=epoch,
        details_json=details,
        created_at=datetime.now(timezone.utc),
    )


def test_story_order_retrieved_before_classified() -> None:
    events = [
        _event("memory.classified", score=0.9, label="bad-runbook"),
        _event("memory.retrieved"),
        _event("action_intent.reserved"),
        _event("lease.claimed", epoch=1),
    ]
    ordered = story_ordered_event_types(events)
    assert ordered.index("memory.retrieved") < ordered.index("memory.classified")
    assert ordered.index("lease.claimed") < ordered.index("memory.retrieved")


def test_story_order_failover_lease_after_reservation() -> None:
    events = [
        _event("lease.claimed", epoch=1),
        _event("memory.retrieved"),
        _event("memory.classified", score=0.8, label="a"),
        _event("action_intent.reserved"),
        _event("checkpoint.action_reserved"),
        _event("lease.claimed", epoch=2),
        _event("action.committed"),
        _event("action.commit_rejected"),
    ]
    ordered = story_ordered_event_types(events)
    lease_positions = [i for i, t in enumerate(ordered) if t == "lease.claimed"]
    assert len(lease_positions) == 2
    assert lease_positions[0] < ordered.index("memory.retrieved")
    assert lease_positions[1] > ordered.index("action_intent.reserved")


def test_full_demo_story_sequence_ranks() -> None:
    """Canonical M6 demo narrative order."""
    events = [
        _event("action.commit_rejected"),
        _event("checkpoint.completed"),
        _event("action.committed"),
        _event("lease.claimed", epoch=2),
        _event("checkpoint.action_reserved"),
        _event("action_intent.reserved"),
        _event("action.selected"),
        _event("checkpoint.memories_classified"),
        _event("memory.classified", score=0.5, label="z"),
        _event("memory.classified", score=0.9, label="a"),
        _event("memory.retrieved"),
        _event("lease.claimed", epoch=1),
        _event("memories.seeded"),
        _event("incident.created"),
    ]
    ordered = story_ordered_event_types(events)
    expected_prefix = [
        "incident.created",
        "memories.seeded",
        "lease.claimed",
        "memory.retrieved",
        "memory.classified",
        "memory.classified",
        "checkpoint.memories_classified",
        "action.selected",
        "action_intent.reserved",
        "checkpoint.action_reserved",
        "lease.claimed",
        "action.committed",
        "checkpoint.completed",
        "action.commit_rejected",
    ]
    assert ordered == expected_prefix


def test_sort_is_stable_for_equal_ranks() -> None:
    a = _event("memory.classified", score=0.9, label="alpha")
    b = _event("memory.classified", score=0.7, label="beta")
    sorted_events = sort_audit_events_story_order([b, a])
    labels = [e.details_json.get("label") for e in sorted_events]
    assert labels == ["alpha", "beta"]
