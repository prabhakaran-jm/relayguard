"""Deterministic local embeddings; swap for Bedrock Titan via EmbeddingProvider."""

from __future__ import annotations

import hashlib
import math
from typing import Protocol

EMBEDDING_DIM = 64

# Operational terms shared by incident descriptions and relevant runbooks.
_INCIDENT_TERMS = frozenset(
    {
        "api",
        "latency",
        "spike",
        "outage",
        "standby",
        "routing",
        "primary",
        "health",
        "restart",
        "traffic",
        "node",
        "failure",
        "incident",
        "resolved",
        "similar",
        "east",
        "deprecated",
        "cascading",
        "checks",
        "route",
        "fail",
    }
)

_KIND_BIAS: dict[str, list[float]] = {
    "current_runbook": [0.9] + [0.0] * (EMBEDDING_DIM - 1),
    "expired_runbook": [0.0, 0.85] + [0.0] * (EMBEDDING_DIM - 2),
    "failed_restart": [0.0, 0.0, 0.85] + [0.0] * (EMBEDDING_DIM - 3),
    "historical_incident": [0.0, 0.0, 0.0, 0.85] + [0.0] * (EMBEDDING_DIM - 4),
}


class EmbeddingProvider(Protocol):
    """Pluggable embedding backend (DeterministicEmbeddingProvider, Bedrock Titan, etc.)."""

    @property
    def dimensions(self) -> int: ...

    def embed(self, text: str, *, memory_kind: str | None = None, is_query: bool = False) -> list[float]: ...


class DeterministicEmbeddingProvider:
    """Hash + keyword features for stable ranking in tests and local demos."""

    def __init__(self, dimensions: int = EMBEDDING_DIM) -> None:
        self._dimensions = dimensions

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed(self, text: str, *, memory_kind: str | None = None, is_query: bool = False) -> list[float]:
        vec = [0.0] * self._dimensions
        tokens = _tokenize(text)

        for token in tokens:
            digest = hashlib.sha256(token.encode()).digest()
            for i in range(self._dimensions):
                vec[i] += (digest[i % len(digest)] / 255.0) * 0.15

        for token in tokens & _INCIDENT_TERMS:
            idx = sum(ord(c) for c in token) % self._dimensions
            vec[idx] += 0.35

        if is_query:
            for i in range(4):
                vec[i] += 0.45

        if memory_kind and memory_kind in _KIND_BIAS:
            bias = _KIND_BIAS[memory_kind]
            for i in range(min(len(bias), self._dimensions)):
                vec[i] += bias[i]

        if memory_kind == "unrelated":
            for i in range(4):
                vec[i] *= 0.05

        return _normalize(vec)


def _tokenize(text: str) -> set[str]:
    cleaned = "".join(ch.lower() if ch.isalnum() else " " for ch in text)
    return {part for part in cleaned.split() if part}


def _normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0:
        return vec
    return [v / norm for v in vec]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        raise ValueError("embedding dimensions must match")
    return sum(x * y for x, y in zip(a, b))


def vector_literal(vec: list[float]) -> str:
    """Format a float vector for CockroachDB VECTOR literals."""
    return "[" + ",".join(f"{v:.8f}" for v in vec) + "]"
