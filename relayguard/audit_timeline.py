"""Stable story-order sorting for audit event timelines."""

from __future__ import annotations

from relayguard.models import AuditEvent

# Narrative order for judge-facing timelines (lower = earlier in story).
_STORY_RANK: dict[str, int] = {
    "incident.created": 100,
    "memories.seeded": 200,
    "lease.claimed": 300,
    "memory.retrieved": 400,
    "memory.classified": 500,
    "checkpoint.memories_classified": 550,
    "action.selected": 600,
    "action_intent.reserved": 700,
    "checkpoint.action_reserved": 800,
    "action.committed": 1000,
    "checkpoint.completed": 1100,
    "action.commit_rejected": 1200,
}

# Second lease.claimed (failover worker) sorts after reservation checkpoint.
_LEASE_FAILOVER_RANK = 950


def story_rank(event: AuditEvent) -> tuple:
    """Sort key: story rank, timestamp, tie-breaker, event id."""
    event_type = event.event_type
    created = str(event.created_at or "")
    event_id = str(event.event_id)

    if event_type == "lease.claimed":
        epoch = event.lease_epoch or 0
        rank = _STORY_RANK["lease.claimed"] if epoch <= 1 else _LEASE_FAILOVER_RANK
        return (rank, created, epoch, event_id)

    if event_type == "memory.classified":
        score = event.details_json.get("similarity_score")
        try:
            score_f = -float(score) if score is not None else 0.0
        except (TypeError, ValueError):
            score_f = 0.0
        label = str(event.details_json.get("label", ""))
        return (_STORY_RANK["memory.classified"], created, score_f, label, event_id)

    rank = _STORY_RANK.get(event_type, 5000)
    return (rank, created, 0, event_id)


def sort_audit_events_story_order(events: list[AuditEvent]) -> list[AuditEvent]:
    """Return events in demo story order; old rows without ranks sort last by time."""
    return sorted(events, key=story_rank)


def story_ordered_event_types(events: list[AuditEvent]) -> list[str]:
    return [event.event_type for event in sort_audit_events_story_order(events)]
