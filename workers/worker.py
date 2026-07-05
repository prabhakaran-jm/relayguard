from __future__ import annotations

from uuid import UUID

from relayguard.config import Settings
from relayguard.models import ActionType, CheckpointState
from relayguard.store import DuplicateIntentError, RelayStore, StaleLeaseError
from workers.memory_gate import classify_memories


def log(msg: str) -> None:
    print(msg, flush=True)


def select_action() -> ActionType:
    """Deterministic mock model decision (Bedrock not called)."""
    return ActionType.ROUTE_TO_STANDBY


def run_worker(store: RelayStore, incident_id: UUID, settings: Settings) -> int:
    worker_id = settings.worker_id
    log(f"[{worker_id}] starting for incident {incident_id}")

    try:
        incident = store.claim_incident(incident_id, worker_id)
    except StaleLeaseError as exc:
        log(f"[{worker_id}] claim failed: {exc}")
        return 1

    log(f"[{worker_id}] claimed lease epoch={incident.lease_epoch}")

    checkpoint = store.get_latest_checkpoint(incident_id)
    if checkpoint:
        state, prev_owner, prev_epoch = checkpoint
        log(f"[{worker_id}] resuming checkpoint from {prev_owner} epoch={prev_epoch} phase={state.phase}")
    else:
        state = CheckpointState(phase="claimed")
        memories = store.get_memories(incident_id)
        classified = classify_memories(memories)
        for memory, classification in classified:
            log(f"[{worker_id}] MemoryGate: {memory.label} -> {classification.value}")
        state.classified_memories = [
            {"label": m.label, "classification": c.value} for m, c in classified
        ]
        state.phase = "memories_classified"
        store.save_checkpoint(incident_id, worker_id, incident.lease_epoch, state)

    if state.intent_id is None:
        existing = store.get_reserved_intent(incident_id)
        if existing:
            state.intent_id = str(existing.intent_id)
            state.selected_action = existing.action_type.value
            state.idempotency_key = existing.idempotency_key
            state.phase = "action_reserved"
            log(f"[{worker_id}] adopting reserved intent intent_id={existing.intent_id}")
        else:
            action = select_action()
            idempotency_key = f"{incident_id}:{action.value}:v1"
            log(f"[{worker_id}] reserving action {action.value} (idempotency={idempotency_key})")
            try:
                intent = store.reserve_action_intent(
                    incident_id,
                    action,
                    idempotency_key,
                    worker_id,
                    incident.lease_epoch,
                )
            except DuplicateIntentError as exc:
                log(f"[{worker_id}] duplicate intent rejected: {exc}")
                return 1

            state.selected_action = action.value
            state.intent_id = str(intent.intent_id)
            state.idempotency_key = idempotency_key
            state.phase = "action_reserved"
            store.save_checkpoint(incident_id, worker_id, incident.lease_epoch, state)
            log(f"[{worker_id}] action reserved intent_id={intent.intent_id}")

            if settings.fail_after == "ACTION_RESERVED":
                log(f"[{worker_id}] FAIL_AFTER=ACTION_RESERVED — simulating crash")
                return 2

    intent_id = UUID(state.intent_id)
    log(f"[{worker_id}] committing action intent_id={intent_id}")
    result = store.commit_action(incident_id, intent_id, worker_id, incident.lease_epoch)
    if result is None:
        log(f"[{worker_id}] commit rejected (stale lease or already committed)")
        return 1

    log(f"[{worker_id}] action committed result_id={result.result_id}")
    state.phase = "completed"
    store.save_checkpoint(incident_id, worker_id, incident.lease_epoch, state)
    log(f"[{worker_id}] done")
    return 0


def run_stale_commit(store: RelayStore, incident_id: UUID, worker_id: str, lease_epoch: int, intent_id: UUID) -> bool:
    """Attempt commit with a stale lease epoch (demo step 10)."""
    log(f"[{worker_id}] stale commit attempt epoch={lease_epoch}")
    result = store.commit_action(incident_id, intent_id, worker_id, lease_epoch)
    if result is None:
        log(f"[{worker_id}] stale commit rejected as expected")
        return False
    log(f"[{worker_id}] stale commit unexpectedly succeeded")
    return True
