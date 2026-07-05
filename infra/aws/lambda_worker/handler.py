from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID

from relayguard.config import Settings
from relayguard.db import collect_database_status, get_connection
from relayguard.store import RelayStore
from workers.worker import run_stale_commit, run_worker

logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)


class HandlerError(Exception):
    def __init__(self, message: str, *, status: str = "error") -> None:
        super().__init__(message)
        self.status = status


SUPPORTED_MODES = frozenset({"run_worker", "stale_commit", "db_status"})


def parse_event(event: dict[str, Any] | str | None) -> dict[str, Any]:
    if event is None:
        raise HandlerError("Event is required")
    if isinstance(event, str):
        try:
            event = json.loads(event)
        except json.JSONDecodeError as exc:
            raise HandlerError(f"Invalid JSON event: {exc}") from exc
    if not isinstance(event, dict):
        raise HandlerError("Event must be a JSON object")

    mode = str(event.get("mode", "run_worker")).strip().lower()
    if mode not in SUPPORTED_MODES:
        raise HandlerError(f"Unsupported mode: {mode}")

    parsed: dict[str, Any] = {"mode": mode}
    if mode in {"run_worker", "stale_commit"}:
        incident_id = event.get("incident_id")
        if not incident_id:
            raise HandlerError("incident_id is required")
        try:
            parsed["incident_id"] = UUID(str(incident_id))
        except ValueError as exc:
            raise HandlerError(f"Invalid incident_id: {incident_id}") from exc

    if mode == "run_worker":
        parsed["worker_id"] = str(event.get("worker_id", "worker-a"))
        fail_after = event.get("fail_after")
        parsed["fail_after"] = str(fail_after) if fail_after else None
    elif mode == "stale_commit":
        parsed["worker_id"] = str(event.get("worker_id", "worker-a"))
        intent_id = event.get("intent_id")
        if not intent_id:
            raise HandlerError("intent_id is required for stale_commit")
        try:
            parsed["intent_id"] = UUID(str(intent_id))
        except ValueError as exc:
            raise HandlerError(f"Invalid intent_id: {intent_id}") from exc
        lease_epoch = event.get("lease_epoch")
        if lease_epoch is None:
            raise HandlerError("lease_epoch is required for stale_commit")
        parsed["lease_epoch"] = int(lease_epoch)

    return parsed


def _worker_status(exit_code: int) -> str:
    if exit_code == 0:
        return "completed"
    if exit_code == 2:
        return "simulated_crash"
    return "failed"


def _enrich_worker_payload(
    store: RelayStore,
    incident_id: UUID,
    payload: dict[str, Any],
) -> None:
    incident = store.get_incident(incident_id)
    checkpoint = store.get_latest_checkpoint(incident_id)
    if checkpoint:
        state, _owner, epoch = checkpoint
        payload["lease_epoch"] = epoch
        if state.intent_id:
            payload["intent_id"] = state.intent_id
        payload["phase"] = state.phase
    if payload.get("intent_id") is None:
        reserved = store.get_reserved_intent(incident_id)
        if reserved:
            payload["intent_id"] = str(reserved.intent_id)
    if incident is not None:
        payload["incident_lease_epoch"] = incident.lease_epoch


def handle_run_worker(parsed: dict[str, Any], settings: Settings) -> dict[str, Any]:
    incident_id = parsed["incident_id"]
    worker_id = parsed["worker_id"]
    settings = settings.override(
        worker_id=worker_id,
        fail_after=parsed.get("fail_after"),
    )
    with get_connection(settings) as conn:
        store = RelayStore(conn, settings)
        exit_code = run_worker(store, incident_id, settings)
        payload: dict[str, Any] = {
            "mode": "run_worker",
            "incident_id": str(incident_id),
            "worker_id": worker_id,
            "exit_code": exit_code,
            "status": _worker_status(exit_code),
        }
        _enrich_worker_payload(store, incident_id, payload)
        return payload


def handle_stale_commit(parsed: dict[str, Any], settings: Settings) -> dict[str, Any]:
    incident_id = parsed["incident_id"]
    worker_id = parsed["worker_id"]
    lease_epoch = parsed["lease_epoch"]
    intent_id = parsed["intent_id"]
    with get_connection(settings) as conn:
        store = RelayStore(conn, settings)
        succeeded = run_stale_commit(store, incident_id, worker_id, lease_epoch, intent_id)
    return {
        "mode": "stale_commit",
        "incident_id": str(incident_id),
        "worker_id": worker_id,
        "intent_id": str(intent_id),
        "lease_epoch": lease_epoch,
        "rejected": not succeeded,
        "status": "rejected" if not succeeded else "unexpected_commit",
    }


def handle_db_status(settings: Settings) -> dict[str, Any]:
    status = collect_database_status(settings)
    return {
        "mode": "db_status",
        "db_target": status.db_target,
        "database_target": status.database_target,
        "redacted_database_url": status.redacted_database_url,
        "database_version": status.database_version,
        "vector_mode_setting": status.vector_mode_setting,
        "embedding_storage_mode": status.embedding_storage_mode,
        "vector_index_present": status.vector_index_present,
        "memory_count": status.memory_count,
        "incident_count": status.incident_count,
    }


def dispatch_event(event: dict[str, Any] | str | None, _context: Any = None) -> dict[str, Any]:
    parsed = parse_event(event)
    settings = Settings.from_env()
    mode = parsed["mode"]

    if mode == "run_worker":
        body = handle_run_worker(parsed, settings)
    elif mode == "stale_commit":
        body = handle_stale_commit(parsed, settings)
    else:
        body = handle_db_status(settings)

    return {"ok": True, **body}


def handler(event: dict[str, Any] | str | None, context: Any = None) -> dict[str, Any]:
    try:
        return dispatch_event(event, context)
    except HandlerError as exc:
        logger.warning("Handler rejected request: %s", exc)
        return {"ok": False, "status": exc.status, "error": str(exc)}
    except Exception as exc:
        logger.exception("Handler failed")
        return {"ok": False, "status": "error", "error": str(exc)}
