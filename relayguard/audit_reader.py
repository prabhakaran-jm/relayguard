"""Build evidence-backed audit reports from CockroachDB state."""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from relayguard.audit_timeline import sort_audit_events_story_order
from relayguard.models import ActionIntent, ActionResult, AuditEvent, Incident
from relayguard.store import RelayStore


class MemoryVerdict(BaseModel):
    memory_id: str
    label: str
    verdict: str
    reason: str
    similarity_score: float | None = None


class TimelineEntry(BaseModel):
    event_type: str
    worker: str | None = None
    lease_epoch: int | None = None
    summary: str
    created_at: str | None = None


class ActionLedgerEntry(BaseModel):
    action_type: str
    idempotency_key: str
    status: str
    result_id: str | None = None


class AuditReport(BaseModel):
    incident_id: UUID
    incident_title: str
    selected_action: str | None = None
    selector_type: str | None = None
    selection_reason: str | None = None
    selection_confidence: float | None = None
    fallback_used: bool = False
    used_memory_ids: list[str] = Field(default_factory=list)
    inspected_memory_ids: list[str] = Field(default_factory=list)
    memory_verdicts: list[MemoryVerdict] = Field(default_factory=list)
    execution_timeline: list[TimelineEntry] = Field(default_factory=list)
    action_ledger: list[ActionLedgerEntry] = Field(default_factory=list)
    committed_action_count: int = 0
    stale_commit_rejection_count: int = 0
    retrieved_memory_count: int = 0
    blocked_memory_count: int = 0
    invariant_status: Literal["PASS", "FAIL"] = "FAIL"
    invariant_errors: list[str] = Field(default_factory=list)


class AuditReader:
    def __init__(self, store: RelayStore) -> None:
        self.store = store

    def build_report(self, incident_id: UUID) -> AuditReport:
        incident = self.store.get_incident(incident_id)
        if incident is None:
            return AuditReport(
                incident_id=incident_id,
                incident_title="(not found)",
                invariant_status="FAIL",
                invariant_errors=[f"incident {incident_id} not found"],
            )

        events = sort_audit_events_story_order(self.store.list_audit_events(incident_id))
        intents = self.store.list_action_intents(incident_id)
        results = self.store.list_action_results(incident_id)

        selection = _latest_event(events, "action.selected")
        memory_verdicts = _memory_verdicts(events)
        timeline = _build_timeline(events)
        action_ledger = _build_action_ledger(intents, results)
        committed_count = len([result for result in results if result.status == "committed"])
        stale_rejects = [event for event in events if event.event_type == "action.commit_rejected"]
        retrieved_memory_count = _retrieved_memory_count(events)
        blocked_memory_count = sum(1 for verdict in memory_verdicts if verdict.verdict == "AVOID")

        report = AuditReport(
            incident_id=incident_id,
            incident_title=incident.title,
            selected_action=_detail(selection, "action_type"),
            selector_type=_detail(selection, "selector_type"),
            selection_reason=_detail(selection, "reason"),
            selection_confidence=_as_float(_detail(selection, "confidence")),
            fallback_used=bool(_detail(selection, "fallback_used", False)),
            used_memory_ids=_detail(selection, "used_memory_ids", []) or [],
            inspected_memory_ids=_detail(selection, "inspected_memory_ids", []) or [],
            memory_verdicts=memory_verdicts,
            execution_timeline=timeline,
            action_ledger=action_ledger,
            committed_action_count=committed_count,
            stale_commit_rejection_count=len(stale_rejects),
            retrieved_memory_count=retrieved_memory_count,
            blocked_memory_count=blocked_memory_count,
        )
        report.invariant_errors = _evaluate_invariants(report, events, intents, results)
        report.invariant_status = "PASS" if not report.invariant_errors else "FAIL"
        return report


def format_audit_report(report: AuditReport) -> str:
    lines = [
        "RelayGuard Audit Report",
        "=======================",
        f"Incident:      {report.incident_id}",
        f"Title:         {report.incident_title}",
        f"Invariants:    {report.invariant_status}",
        "",
        "Action selection",
        "----------------",
        f"Selected:      {report.selected_action or '-'}",
        f"Selector:      {report.selector_type or '-'}",
        f"Confidence:    {report.selection_confidence if report.selection_confidence is not None else '-'}",
        f"Fallback used: {report.fallback_used}",
        f"Reason:        {report.selection_reason or '-'}",
        f"Used memories: {', '.join(report.used_memory_ids) or '-'}",
        f"Inspected:     {', '.join(report.inspected_memory_ids) or '-'}",
        "",
        "MemoryGate verdicts",
        "-------------------",
    ]
    for verdict in report.memory_verdicts:
        score = f" score={verdict.similarity_score:.3f}" if verdict.similarity_score is not None else ""
        lines.append(
            f"  {verdict.label:22s} {verdict.verdict:8s}{score} — {verdict.reason}"
        )

    lines.extend(
        [
            "",
            "Execution summary",
            "-----------------",
            f"Committed actions:         {report.committed_action_count}",
            f"Stale commit rejections:   {report.stale_commit_rejection_count}",
            f"Retrieved memories:        {report.retrieved_memory_count}",
            f"Blocked memories (AVOID):  {report.blocked_memory_count}",
            "",
            "Action ledger",
            "-------------",
        ]
    )
    for entry in report.action_ledger:
        result = entry.result_id or "-"
        lines.append(
            f"  {entry.action_type:20s} {entry.status:10s} key={entry.idempotency_key} result={result}"
        )

    lines.extend(
        [
            "",
            "Timeline",
            "--------",
        ]
    )
    for entry in report.execution_timeline:
        worker = entry.worker or "-"
        epoch = entry.lease_epoch if entry.lease_epoch is not None else "-"
        lines.append(f"  {entry.event_type:28s} worker={worker} epoch={epoch} — {entry.summary}")

    if report.invariant_errors:
        lines.extend(["", "Invariant failures", "------------------"])
        for error in report.invariant_errors:
            lines.append(f"  ✗ {error}")

    return "\n".join(lines)


def _latest_event(events: list[AuditEvent], event_type: str) -> AuditEvent | None:
    matches = [event for event in events if event.event_type == event_type]
    return matches[-1] if matches else None


def _detail(event: AuditEvent | None, key: str, default: Any = None) -> Any:
    if event is None:
        return default
    return event.details_json.get(key, default)


def _memory_verdicts(events: list[AuditEvent]) -> list[MemoryVerdict]:
    verdicts: list[MemoryVerdict] = []
    for event in events:
        if event.event_type != "memory.classified":
            continue
        details = event.details_json
        verdicts.append(
            MemoryVerdict(
                memory_id=str(details.get("memory_id", details.get("label", "unknown"))),
                label=str(details.get("label", "unknown")),
                verdict=str(details.get("verdict", "UNKNOWN")),
                reason=str(details.get("reason", "")),
                similarity_score=_as_float(details.get("similarity_score")),
            )
        )
    return verdicts


def _build_timeline(events: list[AuditEvent]) -> list[TimelineEntry]:
    interesting = {
        "incident.created",
        "memories.seeded",
        "memory.retrieved",
        "memory.classified",
        "action.selected",
        "action_intent.reserved",
        "checkpoint.memories_classified",
        "checkpoint.action_reserved",
        "checkpoint.completed",
        "lease.claimed",
        "action.committed",
        "action.commit_rejected",
    }
    timeline: list[TimelineEntry] = []
    for event in events:
        if event.event_type not in interesting:
            continue
        timeline.append(
            TimelineEntry(
                event_type=event.event_type,
                worker=event.lease_owner,
                lease_epoch=event.lease_epoch,
                summary=_timeline_summary(event),
                created_at=str(event.created_at) if event.created_at else None,
            )
        )
    return timeline


def _build_action_ledger(
    intents: list[ActionIntent],
    results: list[ActionResult],
) -> list[ActionLedgerEntry]:
    results_by_intent = {str(result.intent_id): result for result in results}
    ledger: list[ActionLedgerEntry] = []
    for intent in intents:
        result = results_by_intent.get(str(intent.intent_id))
        ledger.append(
            ActionLedgerEntry(
                action_type=intent.action_type.value,
                idempotency_key=intent.idempotency_key,
                status=intent.status.value,
                result_id=str(result.result_id) if result else None,
            )
        )
    return ledger


def _retrieved_memory_count(events: list[AuditEvent]) -> int:
    count = 0
    for event in events:
        if event.event_type == "memory.retrieved":
            count = max(count, len(event.details_json.get("results", [])))
    return count


def _timeline_summary(event: AuditEvent) -> str:
    details = event.details_json
    if event.event_type == "action.selected":
        return f"{details.get('action_type')} via {details.get('selector_type')}"
    if event.event_type == "memory.classified":
        return f"{details.get('label')} -> {details.get('verdict')}"
    if event.event_type == "memory.retrieved":
        return f"retrieved {len(details.get('results', []))} memories"
    if event.event_type == "action.committed":
        return f"committed {details.get('action_type')}"
    if event.event_type == "action.commit_rejected":
        return f"rejected stale commit ({details.get('reason')})"
    if event.event_type == "lease.claimed":
        return "incident lease claimed"
    if event.event_type == "action_intent.reserved":
        return f"reserved {details.get('action_type')}"
    if event.event_type.startswith("checkpoint."):
        return f"checkpoint {details.get('phase', event.event_type)}"
    if event.event_type == "incident.created":
        return str(details.get("title", "incident created"))
    if event.event_type == "memories.seeded":
        return f"seeded {details.get('count', 0)} memories"
    return event.event_type


def _evaluate_invariants(
    report: AuditReport,
    events: list[AuditEvent],
    intents: list[ActionIntent],
    results: list[ActionResult],
) -> list[str]:
    errors: list[str] = []
    event_types = {event.event_type for event in events}

    if report.committed_action_count != 1:
        errors.append(f"expected exactly 1 committed action, got {report.committed_action_count}")
    if report.stale_commit_rejection_count < 1:
        errors.append(
            f"expected at least 1 stale commit rejection, got {report.stale_commit_rejection_count}"
        )
    if not report.selected_action:
        errors.append("missing action.selected event")
    if not report.selection_reason:
        errors.append("missing action selection reason")
    if len(report.memory_verdicts) < 4:
        errors.append(f"expected at least 4 memory verdicts, got {len(report.memory_verdicts)}")
    if not any(verdict.verdict == "AVOID" for verdict in report.memory_verdicts):
        errors.append("expected at least one AVOID memory verdict")
    if not any(verdict.verdict == "USE" for verdict in report.memory_verdicts):
        errors.append("expected at least one USE memory verdict")

    required = {
        "incident.created",
        "memories.seeded",
        "memory.retrieved",
        "memory.classified",
        "action.selected",
        "action_intent.reserved",
        "action.committed",
        "action.commit_rejected",
    }
    for req in sorted(required - event_types):
        errors.append(f"missing audit event: {req}")

    reserved = [intent for intent in intents if intent.status.value == "reserved"]
    committed = [intent for intent in intents if intent.status.value == "committed"]
    if len(committed) != 1:
        errors.append(f"expected exactly 1 committed intent, got {len(committed)}")
    if len(reserved) > 1:
        errors.append(f"expected at most 1 reserved intent after completion, got {len(reserved)}")
    if len(results) != 1:
        errors.append(f"expected exactly 1 action result row, got {len(results)}")

    return errors


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
