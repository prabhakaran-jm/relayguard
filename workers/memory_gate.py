from __future__ import annotations

from relayguard.models import Memory, MemoryClassification, MemoryKind


def classify_memory(memory: Memory) -> MemoryClassification:
    """Deterministic MemoryGate: map memory_kind to USE / INSPECT / AVOID."""
    mapping = {
        MemoryKind.CURRENT_RUNBOOK: MemoryClassification.USE,
        MemoryKind.EXPIRED_RUNBOOK: MemoryClassification.AVOID,
        MemoryKind.FAILED_RESTART: MemoryClassification.AVOID,
        MemoryKind.HISTORICAL_INCIDENT: MemoryClassification.INSPECT,
    }
    return mapping[memory.memory_kind]


def classify_memories(memories: list[Memory]) -> list[tuple[Memory, MemoryClassification]]:
    return [(m, classify_memory(m)) for m in memories]
