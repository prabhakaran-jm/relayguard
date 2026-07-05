from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import psycopg

from relayguard.config import Settings
from relayguard.db import detect_embedding_storage
from relayguard.embeddings import DeterministicEmbeddingProvider, vector_literal
from relayguard.models import (
    ActionIntent,
    ActionIntentStatus,
    ActionResult,
    ActionType,
    AuditEvent,
    CheckpointState,
    Incident,
    IncidentStatus,
    Memory,
    MemoryKind,
)


class StaleLeaseError(Exception):
    """Raised when a worker's lease epoch no longer matches."""


class DuplicateIntentError(Exception):
    """Raised when an idempotent action intent already exists."""


class RelayStore:
    def __init__(self, conn: psycopg.Connection, settings: Settings | None = None):
        self.conn = conn
        self.settings = settings or Settings.from_env()

    def write_audit(
        self,
        incident_id: UUID,
        event_type: str,
        lease_owner: str | None = None,
        lease_epoch: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditEvent:
        row = self._fetchone(
            """
            INSERT INTO audit_events (incident_id, event_type, lease_owner, lease_epoch, details_json)
            VALUES (%s, %s, %s, %s, %s::jsonb)
            RETURNING event_id, incident_id, event_type, lease_owner, lease_epoch, details_json
            """,
            (
                incident_id,
                event_type,
                lease_owner,
                lease_epoch,
                json.dumps(details or {}),
            ),
        )
        return AuditEvent.model_validate(row)

    def create_incident(self, title: str) -> Incident:
        row = self._fetchone(
            """
            INSERT INTO incidents (title, status)
            VALUES (%s, %s)
            RETURNING incident_id, title, status, lease_owner, lease_epoch, lease_expires_at
            """,
            (title, IncidentStatus.OPEN.value),
        )
        incident = Incident.model_validate(row)
        self.write_audit(incident.incident_id, "incident.created", details={"title": title})
        return incident

    def seed_demo_memories(self, incident_id: UUID) -> list[Memory]:
        embedder = DeterministicEmbeddingProvider()
        seeds = [
            ("current_runbook", "Route traffic to standby when primary health checks fail.", MemoryKind.CURRENT_RUNBOOK),
            ("expired_runbook", "Restart primary node immediately (deprecated 2024-Q1).", MemoryKind.EXPIRED_RUNBOOK),
            ("failed_restart", "Prior restart attempt caused cascading failure.", MemoryKind.FAILED_RESTART),
            ("historical_incident", "Similar outage in us-east-1 resolved via standby routing.", MemoryKind.HISTORICAL_INCIDENT),
            ("unrelated_finance", "Quarterly billing report template for finance team.", MemoryKind.UNRELATED),
        ]
        memories: list[Memory] = []
        has_embedding = self._embedding_storage()
        for label, content, kind in seeds:
            embedding = embedder.embed(content, memory_kind=kind.value)
            if has_embedding == "vector":
                row = self._fetchone(
                    """
                    INSERT INTO memories (incident_id, label, content, memory_kind, embedding)
                    VALUES (%s, %s, %s, %s, %s::VECTOR)
                    RETURNING memory_id, incident_id, label, content, memory_kind, embedding
                    """,
                    (incident_id, label, content, kind.value, vector_literal(embedding)),
                )
            elif has_embedding == "float8[]":
                row = self._fetchone(
                    """
                    INSERT INTO memories (incident_id, label, content, memory_kind, embedding)
                    VALUES (%s, %s, %s, %s, %s::FLOAT8[])
                    RETURNING memory_id, incident_id, label, content, memory_kind, embedding
                    """,
                    (incident_id, label, content, kind.value, embedding),
                )
            else:
                row = self._fetchone(
                    """
                    INSERT INTO memories (incident_id, label, content, memory_kind)
                    VALUES (%s, %s, %s, %s)
                    RETURNING memory_id, incident_id, label, content, memory_kind
                    """,
                    (incident_id, label, content, kind.value),
                )
                row = dict(row)
                row["embedding"] = embedding
            memories.append(_memory_from_row(row))
        self.write_audit(
            incident_id,
            "memories.seeded",
            details={"count": len(memories)},
        )
        return memories

    def get_incident(self, incident_id: UUID) -> Incident | None:
        row = self._fetchone(
            """
            SELECT incident_id, title, status, lease_owner, lease_epoch, lease_expires_at
            FROM incidents WHERE incident_id = %s
            """,
            (incident_id,),
        )
        return Incident.model_validate(row) if row else None

    def list_incidents(self, limit: int = 20) -> list[dict[str, Any]]:
        return self._fetchall(
            """
            SELECT incident_id, title, status, created_at
            FROM incidents
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (limit,),
        )

    def claim_incident(self, incident_id: UUID, worker_id: str) -> Incident:
        incident = self.get_incident(incident_id)
        if incident is None:
            raise ValueError(f"Incident {incident_id} not found")

        now = datetime.now(timezone.utc)
        expires = now + timedelta(seconds=self.settings.lease_ttl_seconds)
        new_epoch = incident.lease_epoch + 1

        row = self._fetchone(
            """
            UPDATE incidents
            SET lease_owner = %s,
                lease_epoch = %s,
                lease_expires_at = %s,
                status = %s,
                updated_at = now()
            WHERE incident_id = %s
              AND (
                    lease_owner IS NULL
                    OR lease_expires_at < %s
                    OR (lease_owner = %s AND lease_epoch = %s)
                  )
            RETURNING incident_id, title, status, lease_owner, lease_epoch, lease_expires_at
            """,
            (
                worker_id,
                new_epoch,
                expires,
                IncidentStatus.CLAIMED.value,
                incident_id,
                now,
                worker_id,
                incident.lease_epoch,
            ),
        )
        if row is None:
            self.write_audit(
                incident_id,
                "lease.claim_rejected",
                lease_owner=worker_id,
                lease_epoch=new_epoch,
                details={"reason": "active_lease_held"},
            )
            raise StaleLeaseError(f"Worker {worker_id} cannot claim incident {incident_id}")

        claimed = Incident.model_validate(row)
        self.write_audit(
            incident_id,
            "lease.claimed",
            lease_owner=worker_id,
            lease_epoch=claimed.lease_epoch,
            details={"expires_at": expires.isoformat()},
        )
        return claimed

    def get_memories(self, incident_id: UUID) -> list[Memory]:
        storage = self._embedding_storage()
        if storage == "none":
            rows = self._fetchall(
                """
                SELECT memory_id, incident_id, label, content, memory_kind
                FROM memories WHERE incident_id = %s ORDER BY created_at
                """,
                (incident_id,),
            )
            return [_memory_from_row(r) for r in rows]

        rows = self._fetchall(
            """
            SELECT memory_id, incident_id, label, content, memory_kind, embedding
            FROM memories WHERE incident_id = %s ORDER BY created_at
            """,
            (incident_id,),
        )
        return [_memory_from_row(r) for r in rows]

    def save_checkpoint(
        self,
        incident_id: UUID,
        lease_owner: str,
        lease_epoch: int,
        state: CheckpointState,
    ) -> bool:
        row = self._fetchone(
            """
            UPDATE incidents SET updated_at = now()
            WHERE incident_id = %s AND lease_owner = %s AND lease_epoch = %s
            RETURNING incident_id
            """,
            (incident_id, lease_owner, lease_epoch),
        )
        if row is None:
            self.write_audit(
                incident_id,
                "checkpoint.rejected",
                lease_owner=lease_owner,
                lease_epoch=lease_epoch,
                details={"reason": "stale_lease"},
            )
            return False

        self._execute(
            """
            INSERT INTO checkpoints (incident_id, lease_owner, lease_epoch, state_json)
            VALUES (%s, %s, %s, %s::jsonb)
            """,
            (incident_id, lease_owner, lease_epoch, state.model_dump_json()),
        )
        self.write_audit(
            incident_id,
            state.phase if state.phase.startswith("checkpoint.") else f"checkpoint.{state.phase}",
            lease_owner=lease_owner,
            lease_epoch=lease_epoch,
            details={"phase": state.phase},
        )
        return True

    def get_latest_checkpoint(self, incident_id: UUID) -> tuple[CheckpointState, str, int] | None:
        row = self._fetchone(
            """
            SELECT state_json, lease_owner, lease_epoch
            FROM checkpoints
            WHERE incident_id = %s
            ORDER BY created_at DESC, checkpoint_id DESC
            LIMIT 1
            """,
            (incident_id,),
        )
        if row is None:
            return None
        state = CheckpointState.model_validate(row["state_json"])
        return state, row["lease_owner"], row["lease_epoch"]

    def get_reserved_intent(self, incident_id: UUID) -> ActionIntent | None:
        row = self._fetchone(
            """
            SELECT intent_id, incident_id, action_type, idempotency_key, status, lease_owner, lease_epoch
            FROM action_intents
            WHERE incident_id = %s AND status = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (incident_id, ActionIntentStatus.RESERVED.value),
        )
        return ActionIntent.model_validate(row) if row else None

    def reserve_action_intent(
        self,
        incident_id: UUID,
        action_type: ActionType,
        idempotency_key: str,
        lease_owner: str,
        lease_epoch: int,
    ) -> ActionIntent:
        existing = self._fetchone(
            """
            SELECT intent_id, incident_id, action_type, idempotency_key, status, lease_owner, lease_epoch
            FROM action_intents
            WHERE incident_id = %s AND action_type = %s AND idempotency_key = %s
            """,
            (incident_id, action_type.value, idempotency_key),
        )
        if existing:
            self.write_audit(
                incident_id,
                "action_intent.duplicate_rejected",
                lease_owner=lease_owner,
                lease_epoch=lease_epoch,
                details={"idempotency_key": idempotency_key},
            )
            raise DuplicateIntentError(
                f"Intent already exists for {incident_id}/{action_type}/{idempotency_key}"
            )

        lease_ok = self._fetchone(
            """
            SELECT incident_id FROM incidents
            WHERE incident_id = %s AND lease_owner = %s AND lease_epoch = %s
            """,
            (incident_id, lease_owner, lease_epoch),
        )
        if lease_ok is None:
            self.write_audit(
                incident_id,
                "action_intent.reserve_rejected",
                lease_owner=lease_owner,
                lease_epoch=lease_epoch,
                details={"reason": "stale_lease"},
            )
            raise StaleLeaseError("Cannot reserve action with stale lease")

        row = self._fetchone(
            """
            INSERT INTO action_intents
                (incident_id, action_type, idempotency_key, status, lease_owner, lease_epoch)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING intent_id, incident_id, action_type, idempotency_key, status, lease_owner, lease_epoch
            """,
            (
                incident_id,
                action_type.value,
                idempotency_key,
                ActionIntentStatus.RESERVED.value,
                lease_owner,
                lease_epoch,
            ),
        )
        intent = ActionIntent.model_validate(row)
        self.write_audit(
            incident_id,
            "action_intent.reserved",
            lease_owner=lease_owner,
            lease_epoch=lease_epoch,
            details={
                "intent_id": str(intent.intent_id),
                "action_type": action_type.value,
                "idempotency_key": idempotency_key,
            },
        )
        return intent

    def commit_action(
        self,
        incident_id: UUID,
        intent_id: UUID,
        lease_owner: str,
        lease_epoch: int,
    ) -> ActionResult | None:
        intent_row = self._fetchone(
            """
            SELECT intent_id, incident_id, action_type, idempotency_key, status, lease_owner, lease_epoch
            FROM action_intents WHERE intent_id = %s AND incident_id = %s
            """,
            (intent_id, incident_id),
        )
        if intent_row is None:
            self.write_audit(
                incident_id,
                "action.commit_rejected",
                lease_owner=lease_owner,
                lease_epoch=lease_epoch,
                details={"reason": "intent_not_found", "intent_id": str(intent_id)},
            )
            return None

        if intent_row["status"] == ActionIntentStatus.COMMITTED.value:
            self.write_audit(
                incident_id,
                "action.commit_rejected",
                lease_owner=lease_owner,
                lease_epoch=lease_epoch,
                details={"reason": "already_committed", "intent_id": str(intent_id)},
            )
            return None

        lease_ok = self._fetchone(
            """
            SELECT incident_id FROM incidents
            WHERE incident_id = %s AND lease_owner = %s AND lease_epoch = %s
            """,
            (incident_id, lease_owner, lease_epoch),
        )
        if lease_ok is None:
            self.write_audit(
                incident_id,
                "action.commit_rejected",
                lease_owner=lease_owner,
                lease_epoch=lease_epoch,
                details={"reason": "stale_lease", "intent_id": str(intent_id)},
            )
            return None

        updated = self._fetchone(
            """
            UPDATE action_intents
            SET status = %s, lease_owner = %s, lease_epoch = %s
            WHERE intent_id = %s AND incident_id = %s AND status = %s
            RETURNING intent_id, incident_id, action_type, idempotency_key, status, lease_owner, lease_epoch
            """,
            (
                ActionIntentStatus.COMMITTED.value,
                lease_owner,
                lease_epoch,
                intent_id,
                incident_id,
                ActionIntentStatus.RESERVED.value,
            ),
        )
        if updated is None:
            self.write_audit(
                incident_id,
                "action.commit_rejected",
                lease_owner=lease_owner,
                lease_epoch=lease_epoch,
                details={"reason": "stale_intent_lease", "intent_id": str(intent_id)},
            )
            return None

        result_row = self._fetchone(
            """
            INSERT INTO action_results
                (intent_id, incident_id, action_type, status, lease_owner, lease_epoch)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING result_id, intent_id, incident_id, action_type, status, lease_owner, lease_epoch
            """,
            (
                intent_id,
                incident_id,
                intent_row["action_type"],
                "committed",
                lease_owner,
                lease_epoch,
            ),
        )
        self._execute(
            """
            UPDATE incidents SET status = %s, updated_at = now()
            WHERE incident_id = %s AND lease_owner = %s AND lease_epoch = %s
            """,
            (IncidentStatus.RESOLVED.value, incident_id, lease_owner, lease_epoch),
        )
        result = ActionResult.model_validate(result_row)
        self.write_audit(
            incident_id,
            "action.committed",
            lease_owner=lease_owner,
            lease_epoch=lease_epoch,
            details={
                "intent_id": str(intent_id),
                "action_type": intent_row["action_type"],
                "result_id": str(result.result_id),
            },
        )
        return result

    def count_committed_actions(self, incident_id: UUID) -> int:
        row = self._fetchone(
            """
            SELECT COUNT(*) AS cnt FROM action_results
            WHERE incident_id = %s AND status = 'committed'
            """,
            (incident_id,),
        )
        return int(row["cnt"]) if row else 0

    def list_audit_events(self, incident_id: UUID) -> list[AuditEvent]:
        rows = self._fetchall(
            """
            SELECT event_id, incident_id, event_type, lease_owner, lease_epoch, details_json, created_at
            FROM audit_events WHERE incident_id = %s ORDER BY created_at, event_id
            """,
            (incident_id,),
        )
        return [AuditEvent.model_validate(r) for r in rows]

    def list_action_intents(self, incident_id: UUID) -> list[ActionIntent]:
        rows = self._fetchall(
            """
            SELECT intent_id, incident_id, action_type, idempotency_key, status, lease_owner, lease_epoch
            FROM action_intents WHERE incident_id = %s ORDER BY created_at
            """,
            (incident_id,),
        )
        return [ActionIntent.model_validate(r) for r in rows]

    def list_action_results(self, incident_id: UUID) -> list[ActionResult]:
        rows = self._fetchall(
            """
            SELECT result_id, intent_id, incident_id, action_type, status, lease_owner, lease_epoch
            FROM action_results WHERE incident_id = %s ORDER BY committed_at
            """,
            (incident_id,),
        )
        return [ActionResult.model_validate(r) for r in rows]

    def get_embedding_mode(self) -> str:
        return detect_embedding_storage(self.conn)

    def _embedding_storage(self) -> str:
        return self.get_embedding_mode()

    def _execute(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        with self.conn.cursor() as cur:
            cur.execute(sql, params)

    def _fetchone(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()

    def _fetchall(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            return list(cur.fetchall())


def _parse_embedding(raw: Any) -> list[float] | None:
    if raw is None:
        return None
    if isinstance(raw, list):
        return [float(x) for x in raw]
    if isinstance(raw, str):
        inner = raw.strip().strip("[]")
        if not inner:
            return None
        return [float(part) for part in inner.split(",")]
    return None


def _memory_from_row(row: dict[str, Any]) -> Memory:
    data = dict(row)
    data["embedding"] = _parse_embedding(row.get("embedding"))
    return Memory.model_validate(data)
