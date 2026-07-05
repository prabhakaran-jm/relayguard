from __future__ import annotations

from relayguard.models import Memory, MemoryClassification, MemoryKind


_VERDICT_REASONS: dict[MemoryKind, tuple[MemoryClassification, str]] = {
    MemoryKind.CURRENT_RUNBOOK: (
        MemoryClassification.USE,
        "active runbook approved for current incident response",
    ),
    MemoryKind.EXPIRED_RUNBOOK: (
        MemoryClassification.AVOID,
        "runbook is expired or deprecated",
    ),
    MemoryKind.FAILED_RESTART: (
        MemoryClassification.AVOID,
        "prior action failed and must not be repeated",
    ),
    MemoryKind.HISTORICAL_INCIDENT: (
        MemoryClassification.INSPECT,
        "related historical incident requires human review",
    ),
    MemoryKind.UNRELATED: (
        MemoryClassification.AVOID,
        "memory is unrelated to the active incident",
    ),
}


def classify_memory(memory: Memory) -> tuple[MemoryClassification, str]:
    """Deterministic MemoryGate: map memory_kind to USE / INSPECT / AVOID + reason."""
    if memory.memory_kind in _VERDICT_REASONS:
        return _VERDICT_REASONS[memory.memory_kind]
    return (
        MemoryClassification.AVOID,
        f"unknown memory kind '{memory.memory_kind.value}' defaults to AVOID",
    )


def classify_memories(
    memories: list[Memory],
) -> list[tuple[Memory, MemoryClassification, str]]:
    return [(memory, verdict, reason) for memory in memories for verdict, reason in [classify_memory(memory)]]
