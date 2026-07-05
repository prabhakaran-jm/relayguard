from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

import psycopg

from relayguard.embeddings import (
    DeterministicEmbeddingProvider,
    EmbeddingProvider,
    cosine_similarity,
    vector_literal,
)
from relayguard.models import Memory, MemoryKind
from relayguard.store import RelayStore


@dataclass(frozen=True)
class RetrievedMemory:
    memory_id: UUID
    memory_type: str
    content: str
    similarity_score: float
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def memory(self) -> Memory:
        return Memory(
            memory_id=self.memory_id,
            incident_id=UUID(self.metadata["incident_id"]),
            label=self.metadata.get("label", self.memory_type),
            content=self.content,
            memory_kind=MemoryKind(self.memory_type),
        )


def retrieve_similar_memories(
    store: RelayStore,
    incident_id: UUID,
    incident_text: str,
    *,
    provider: EmbeddingProvider | None = None,
    limit: int = 5,
) -> list[RetrievedMemory]:
    embedder = provider or DeterministicEmbeddingProvider()
    query_vec = embedder.embed(incident_text, is_query=True)

    if store._embedding_storage() == "vector":
        ranked = _search_with_vector_sql(store.conn, incident_id, query_vec, limit)
        if ranked is not None:
            return ranked

    return _search_in_python(store, incident_id, query_vec, embedder, limit)


def _search_with_vector_sql(
    conn: psycopg.Connection,
    incident_id: UUID,
    query_vec: list[float],
    limit: int,
) -> list[RetrievedMemory] | None:
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT memory_id, incident_id, label, content, memory_kind,
                       (1 - (embedding <=> %s::VECTOR)) AS similarity_score
                FROM memories
                WHERE incident_id = %s AND embedding IS NOT NULL
                ORDER BY embedding <=> %s::VECTOR
                LIMIT %s
                """,
                (vector_literal(query_vec), incident_id, vector_literal(query_vec), limit),
            )
            rows = cur.fetchall()
    except Exception:
        return None

    return [_row_to_retrieved(row) for row in rows]


def _search_in_python(
    store: RelayStore,
    incident_id: UUID,
    query_vec: list[float],
    embedder: EmbeddingProvider,
    limit: int,
) -> list[RetrievedMemory]:
    memories = store.get_memories(incident_id)
    scored: list[RetrievedMemory] = []
    for memory in memories:
        if memory.embedding:
            score = cosine_similarity(query_vec, memory.embedding)
        else:
            score = cosine_similarity(
                query_vec,
                embedder.embed(memory.content, memory_kind=memory.memory_kind.value),
            )
        scored.append(
            RetrievedMemory(
                memory_id=memory.memory_id,
                memory_type=memory.memory_kind.value,
                content=memory.content,
                similarity_score=round(score, 4),
                metadata={
                    "incident_id": str(memory.incident_id),
                    "label": memory.label,
                },
            )
        )
    scored.sort(key=lambda item: item.similarity_score, reverse=True)
    return scored[:limit]


def _row_to_retrieved(row: dict[str, Any]) -> RetrievedMemory:
    return RetrievedMemory(
        memory_id=row["memory_id"],
        memory_type=row["memory_kind"],
        content=row["content"],
        similarity_score=round(float(row["similarity_score"]), 4),
        metadata={
            "incident_id": str(row["incident_id"]),
            "label": row["label"],
        },
    )
