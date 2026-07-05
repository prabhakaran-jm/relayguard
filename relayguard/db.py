from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Generator
from urllib.parse import urlparse, urlunparse

import psycopg
from psycopg.rows import dict_row
from pydantic import BaseModel

from relayguard.config import Settings, describe_database_target, redact_database_url

logger = logging.getLogger(__name__)


class DatabaseStatus(BaseModel):
    db_target: str
    database_target: str
    redacted_database_url: str
    database_version: str | None
    embedding_storage_mode: str
    vector_mode_setting: str
    memory_count: int
    incident_count: int
    vector_index_present: bool


@contextmanager
def get_connection(settings: Settings | None = None) -> Generator[psycopg.Connection, None, None]:
    cfg = settings or Settings.from_env()
    logger.info("Connecting to %s", describe_database_target(cfg.database_url, cfg.db_target))
    conn = psycopg.connect(
        cfg.database_url,
        row_factory=dict_row,
        autocommit=False,
        connect_timeout=5,
    )
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def apply_schema(settings: Settings | None = None) -> str:
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    schema_path = root / "db" / "schema.sql"
    sql = schema_path.read_text(encoding="utf-8")
    cfg = settings or Settings.from_env()

    parsed = urlparse(cfg.database_url)
    bootstrap_url = urlunparse(parsed._replace(path="/defaultdb"))

    with psycopg.connect(bootstrap_url, autocommit=True, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE DATABASE IF NOT EXISTS relayguard")

    embedding_mode = "none"
    with psycopg.connect(cfg.database_url, autocommit=True, connect_timeout=5, row_factory=dict_row) as conn:
        for statement in _split_sql(sql):
            stmt = statement.strip()
            if stmt and not stmt.upper().startswith("CREATE DATABASE"):
                with conn.cursor() as cur:
                    cur.execute(stmt)

        migrations_dir = root / "db" / "migrations"
        if migrations_dir.exists():
            for migration in sorted(migrations_dir.glob("*.sql")):
                for statement in _split_sql(migration.read_text(encoding="utf-8")):
                    stmt = statement.strip()
                    if stmt and not stmt.upper().startswith("SET DATABASE"):
                        with conn.cursor() as cur:
                            cur.execute(stmt)

        embedding_mode = ensure_embedding_column(conn, cfg.cockroach_vector_mode)
        _try_create_vector_index(conn, embedding_mode)

    logger.info("Embedding storage mode active: %s", embedding_mode)
    return embedding_mode


def detect_embedding_storage(conn: psycopg.Connection) -> str:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT data_type FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'memories' AND column_name = 'embedding'
            """
        )
        existing = cur.fetchone()
        if existing is None:
            return "none"
        dtype = str(existing["data_type"]).lower()
        if "vector" in dtype:
            return "vector"
        if "array" in dtype or "float" in dtype:
            return "float8[]"
        return "none"


def ensure_embedding_column(conn: psycopg.Connection, vector_mode: str) -> str:
    existing = detect_embedding_storage(conn)
    if existing != "none":
        logger.info("Using existing embedding column type: %s", existing)
        return existing

    if vector_mode == "float_array":
        with conn.cursor() as cur:
            cur.execute("ALTER TABLE memories ADD COLUMN IF NOT EXISTS embedding FLOAT8[]")
        return "float8[]"

    if vector_mode in ("auto", "vector"):
        try:
            with conn.cursor() as cur:
                cur.execute("ALTER TABLE memories ADD COLUMN IF NOT EXISTS embedding VECTOR(64)")
            return "vector"
        except psycopg.Error:
            if vector_mode == "vector":
                logger.warning("VECTOR mode requested but cluster does not support VECTOR type")
            if vector_mode == "auto":
                with conn.cursor() as cur:
                    cur.execute("ALTER TABLE memories ADD COLUMN IF NOT EXISTS embedding FLOAT8[]")
                return "float8[]"
            return "none"

    return "none"


def _try_create_vector_index(conn: psycopg.Connection, embedding_mode: str) -> None:
    if embedding_mode != "vector":
        return
    try:
        with conn.cursor() as cur:
            cur.execute(
                "CREATE VECTOR INDEX IF NOT EXISTS idx_memories_embedding ON memories (embedding)"
            )
        logger.info("Vector index available: idx_memories_embedding")
    except Exception:
        logger.info("Vector index not available on this cluster; SQL vector search may still work")


def vector_index_exists(conn: psycopg.Connection) -> bool:
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT index_name FROM information_schema.statistics
                WHERE table_schema = 'public'
                  AND table_name = 'memories'
                  AND index_name = 'idx_memories_embedding'
                LIMIT 1
                """
            )
            return cur.fetchone() is not None
    except psycopg.Error:
        return False


def collect_database_status(settings: Settings | None = None) -> DatabaseStatus:
    cfg = settings or Settings.from_env()
    with psycopg.connect(cfg.database_url, row_factory=dict_row, connect_timeout=5) as conn:
        embedding_mode = detect_embedding_storage(conn)
        version = _database_version(conn)
        memory_count = _scalar(conn, "SELECT COUNT(*) AS cnt FROM memories")
        incident_count = _scalar(conn, "SELECT COUNT(*) AS cnt FROM incidents")
        index_present = vector_index_exists(conn)

    return DatabaseStatus(
        db_target=cfg.db_target,
        database_target=describe_database_target(cfg.database_url, cfg.db_target),
        redacted_database_url=redact_database_url(cfg.database_url),
        database_version=version,
        embedding_storage_mode=embedding_mode,
        vector_mode_setting=cfg.cockroach_vector_mode,
        memory_count=memory_count,
        incident_count=incident_count,
        vector_index_present=index_present,
    )


def format_database_status(status: DatabaseStatus) -> str:
    return "\n".join(
        [
            "RelayGuard Database Status",
            "==========================",
            f"Target:              {status.db_target}",
            f"Connection:          {status.database_target}",
            f"Redacted URL:        {status.redacted_database_url}",
            f"Database version:    {status.database_version or 'unavailable'}",
            f"Vector mode setting: {status.vector_mode_setting}",
            f"Embedding storage:   {status.embedding_storage_mode}",
            f"Vector index:        {'yes' if status.vector_index_present else 'no'}",
            f"Memories:            {status.memory_count}",
            f"Incidents:           {status.incident_count}",
        ]
    )


def _database_version(conn: psycopg.Connection) -> str | None:
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT version() AS version")
            row = cur.fetchone()
            return str(row["version"]) if row else None
    except psycopg.Error:
        return None


def _scalar(conn: psycopg.Connection, sql: str) -> int:
    with conn.cursor() as cur:
        cur.execute(sql)
        row = cur.fetchone()
        return int(row["cnt"]) if row else 0


def _split_sql(sql: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    for line in sql.splitlines():
        stripped = line.strip()
        if stripped.startswith("--"):
            continue
        current.append(line)
        if stripped.endswith(";"):
            parts.append("\n".join(current))
            current = []
    if current:
        parts.append("\n".join(current))
    return parts
