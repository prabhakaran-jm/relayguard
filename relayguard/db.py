from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

import psycopg
from psycopg.rows import dict_row

from relayguard.config import Settings


@contextmanager
def get_connection(settings: Settings | None = None) -> Generator[psycopg.Connection, None, None]:
    cfg = settings or Settings.from_env()
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


def apply_schema(settings: Settings | None = None) -> None:
    from pathlib import Path
    from urllib.parse import urlparse, urlunparse

    root = Path(__file__).resolve().parent.parent
    schema_path = root / "db" / "schema.sql"
    sql = schema_path.read_text(encoding="utf-8")
    cfg = settings or Settings.from_env()

    parsed = urlparse(cfg.database_url)
    bootstrap_url = urlunparse(parsed._replace(path="/defaultdb"))

    with psycopg.connect(bootstrap_url, autocommit=True, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE DATABASE IF NOT EXISTS relayguard")

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

        _ensure_embedding_column(conn)
        _try_create_vector_index(conn)


def _ensure_embedding_column(conn: psycopg.Connection) -> str:
    """Return 'vector', 'float8[]', or 'none' depending on cluster capabilities."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT data_type FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'memories' AND column_name = 'embedding'
            """
        )
        existing = cur.fetchone()
        if existing:
            dtype = str(existing["data_type"]).lower()
            return "vector" if "vector" in dtype else "float8[]"

    try:
        with conn.cursor() as cur:
            cur.execute("ALTER TABLE memories ADD COLUMN IF NOT EXISTS embedding VECTOR(64)")
        return "vector"
    except psycopg.Error:
        pass

    try:
        with conn.cursor() as cur:
            cur.execute("ALTER TABLE memories ADD COLUMN IF NOT EXISTS embedding FLOAT8[]")
        return "float8[]"
    except psycopg.Error:
        return "none"


def _try_create_vector_index(conn: psycopg.Connection) -> None:
    try:
        with conn.cursor() as cur:
            cur.execute(
                "CREATE VECTOR INDEX IF NOT EXISTS idx_memories_embedding ON memories (embedding)"
            )
    except Exception:
        # Local single-node images may lack vector indexing; CockroachDB Cloud enables it.
        pass


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
