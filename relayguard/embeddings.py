"""Text-feature local embeddings; swap for Bedrock Titan via EmbeddingProvider."""

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

# Weight of the (noisy, centered) hash features vs. the keyword-overlap features.
# Keyword overlap dominates so ranking reflects shared operational vocabulary,
# not hash coincidence. See tests/test_m2_memory.py for the empirical check.
_HASH_WEIGHT = 0.03
_KEYWORD_WEIGHT = 1.2


class EmbeddingProvider(Protocol):
    """Pluggable embedding backend (DeterministicEmbeddingProvider, Bedrock Titan, etc.)."""

    @property
    def dimensions(self) -> int: ...

    def embed(self, text: str, *, memory_kind: str | None = None, is_query: bool = False) -> list[float]: ...


class DeterministicEmbeddingProvider:
    """Hash + keyword-overlap features for stable ranking in tests and local demos.

    Ranking comes entirely from the text: `memory_kind` is accepted for interface
    compatibility but has no effect on the vector.
    """

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
                # Center around 0 so unrelated text doesn't accumulate a
                # spurious positive bias against the query's own hash noise.
                vec[i] += (digest[i % len(digest)] / 255.0 - 0.5) * _HASH_WEIGHT

        for token in tokens & _INCIDENT_TERMS:
            idx = sum(ord(c) for c in token) % self._dimensions
            vec[idx] += _KEYWORD_WEIGHT

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


class BedrockTitanEmbeddingProvider:
    """Amazon Bedrock Titan Text Embeddings V2 (amazon.titan-embed-text-v2:0)."""

    MODEL_ID = "amazon.titan-embed-text-v2:0"

    def __init__(
        self,
        *,
        dimensions: int = 256,
        region: str = "us-east-1",
        client: object | None = None,
    ) -> None:
        if dimensions not in (256, 512, 1024):
            raise ValueError("Titan v2 embeddings support dimensions 256, 512, or 1024")
        self._dimensions = dimensions
        self._region = region
        self._client = client

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed(self, text: str, *, memory_kind: str | None = None, is_query: bool = False) -> list[float]:
        client = self._client or self._build_client()
        body = {
            "inputText": text,
            "dimensions": self._dimensions,
            "normalize": True,
        }
        import json

        response = client.invoke_model(
            modelId=self.MODEL_ID,
            body=json.dumps(body),
        )
        payload = json.loads(response["body"].read())
        return [float(v) for v in payload["embedding"]]

    def _build_client(self) -> object:
        import boto3

        return boto3.client("bedrock-runtime", region_name=self._region)


def get_embedding_provider(settings: object) -> EmbeddingProvider:
    """Build the configured EmbeddingProvider from Settings.

    `settings` duck-types relayguard.config.Settings (embedding_provider,
    embedding_dimensions, aws_region) to avoid a circular import.
    """
    provider = getattr(settings, "embedding_provider", "deterministic")
    dimensions = getattr(settings, "embedding_dimensions", EMBEDDING_DIM)
    if provider == "bedrock":
        region = getattr(settings, "aws_region", "us-east-1")
        return BedrockTitanEmbeddingProvider(dimensions=dimensions, region=region)
    return DeterministicEmbeddingProvider(dimensions=dimensions)
