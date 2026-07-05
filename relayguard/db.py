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

    schema_path = Path(__file__).resolve().parent.parent / "db" / "schema.sql"
    sql = schema_path.read_text(encoding="utf-8")
    cfg = settings or Settings.from_env()

    parsed = urlparse(cfg.database_url)
    bootstrap_url = urlunparse(parsed._replace(path="/defaultdb"))

    with psycopg.connect(bootstrap_url, autocommit=True, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE DATABASE IF NOT EXISTS relayguard")

    with psycopg.connect(cfg.database_url, autocommit=True, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            for statement in _split_sql(sql):
                stmt = statement.strip()
                if stmt and not stmt.upper().startswith("CREATE DATABASE"):
                    cur.execute(statement)


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
