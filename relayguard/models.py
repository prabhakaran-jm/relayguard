from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class IncidentStatus(StrEnum):
    OPEN = "open"
    CLAIMED = "claimed"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"


class MemoryKind(StrEnum):
    CURRENT_RUNBOOK = "current_runbook"
    EXPIRED_RUNBOOK = "expired_runbook"
    FAILED_RESTART = "failed_restart"
    HISTORICAL_INCIDENT = "historical_incident"
    UNRELATED = "unrelated"


class MemoryClassification(StrEnum):
    USE = "USE"
    INSPECT = "INSPECT"
    AVOID = "AVOID"


class ActionType(StrEnum):
    ROUTE_TO_STANDBY = "ROUTE_TO_STANDBY"


class ActionIntentStatus(StrEnum):
    RESERVED = "reserved"
    COMMITTED = "committed"
    REJECTED = "rejected"


class Incident(BaseModel):
    incident_id: UUID
    title: str
    status: IncidentStatus
    lease_owner: str | None = None
    lease_epoch: int = 0
    lease_expires_at: Any | None = None


class Memory(BaseModel):
    memory_id: UUID
    incident_id: UUID
    label: str
    content: str
    memory_kind: MemoryKind
    embedding: list[float] | None = None


class ClassifiedMemory(BaseModel):
    memory: Memory
    classification: MemoryClassification


class CheckpointState(BaseModel):
    phase: str
    classified_memories: list[dict[str, Any]] = Field(default_factory=list)
    selected_action: str | None = None
    intent_id: str | None = None
    idempotency_key: str | None = None


class ActionIntent(BaseModel):
    intent_id: UUID
    incident_id: UUID
    action_type: ActionType
    idempotency_key: str
    status: ActionIntentStatus
    lease_owner: str
    lease_epoch: int


class ActionResult(BaseModel):
    result_id: UUID
    intent_id: UUID
    incident_id: UUID
    action_type: ActionType
    status: str
    lease_owner: str
    lease_epoch: int


class AuditEvent(BaseModel):
    event_id: UUID
    incident_id: UUID
    event_type: str
    lease_owner: str | None = None
    lease_epoch: int | None = None
    details_json: dict[str, Any] = Field(default_factory=dict)
