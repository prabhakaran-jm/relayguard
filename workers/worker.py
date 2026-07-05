from __future__ import annotations

from uuid import UUID

from relayguard.config import Settings
from relayguard.embeddings import DeterministicEmbeddingProvider
from relayguard.models import ActionType, CheckpointState
from relayguard.store import DuplicateIntentError, RelayStore, StaleLeaseError
from workers.memory_gate import classify_memory
from workers.memory_retriever import retrieve_similar_memories


def log(msg: str) -> None:
    print(msg, flush=True)


def select_action() -> ActionType:
    """Deterministic mock model decision (Bedrock not called)."""
    return ActionType.ROUTE_TO_STANDBY


def _retrieve_and_classify_memories(
    store: RelayStore,
    incident_id: UUID,
    incident_text: str,
    worker_id: str,
    lease_epoch: int,
) -> CheckpointState:
    embedder = DeterministicEmbeddingProvider()
    retrieved = retrieve_similar_memories(
        store,
        incident_id,
        incident_text,
        provider=embedder,
        limit=5,
    )

    store.write_audit(
        incident_id,
        "memory.retrieved",
        lease_owner=worker_id,
        lease_epoch=lease_epoch,
        details={
            "query": incident_text,
            "results": [
                {
                    "memory_id": str(item.memory_id),
                    "label": item.metadata.get("label"),
                    "memory_type": item.memory_type,
                    "similarity_score": item.similarity_score,
                }
                for item in retrieved
            ],
        },
    )

    classified_rows: list[dict[str, str | float]] = []
    for item in retrieved:
        memory = item.memory
        verdict, reason = classify_memory(memory)
        store.write_audit(
            incident_id,
            "memory.classified",
            lease_owner=worker_id,
            lease_epoch=lease_epoch,
            details={
                "memory_id": str(memory.memory_id),
                "label": memory.label,
                "memory_type": memory.memory_kind.value,
                "similarity_score": item.similarity_score,
                "verdict": verdict.value,
                "reason": reason,
            },
        )
        log(
            f"[{worker_id}] score={item.similarity_score:.3f} "
            f"{memory.label} verdict={verdict.value} reason={reason}"
        )
        classified_rows.append(
            {
                "label": memory.label,
                "classification": verdict.value,
                "reason": reason,
                "similarity_score": item.similarity_score,
            }
        )

    return CheckpointState(
        phase="checkpoint.memories_classified",
        classified_memories=classified_rows,
    )


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
        state = _retrieve_and_classify_memories(
            store, incident_id, incident.title, worker_id, incident.lease_epoch
        )
        store.save_checkpoint(incident_id, worker_id, incident.lease_epoch, state)

    if state.intent_id is None:
        existing = store.get_reserved_intent(incident_id)
        if existing:
            state.intent_id = str(existing.intent_id)
            state.selected_action = existing.action_type.value
            state.idempotency_key = existing.idempotency_key
            state.phase = "checkpoint.action_reserved"
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
            state.phase = "checkpoint.action_reserved"
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
    state.phase = "checkpoint.completed"
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
