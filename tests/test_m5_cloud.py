from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from relayguard.config import (
    Settings,
    redact_database_url,
    resolve_database_url,
)
from relayguard.db import collect_database_status, detect_embedding_storage, format_database_status


def test_resolve_database_url_local_target() -> None:
    url = resolve_database_url(
        db_target="local",
        database_url_local="postgresql://root@localhost:26257/relayguard?sslmode=disable",
        database_url_cloud="postgresql://cloud@host:26257/relayguard?sslmode=require",
    )
    assert "localhost" in url


def test_resolve_database_url_cloud_target() -> None:
    url = resolve_database_url(
        db_target="cloud",
        database_url_local="postgresql://root@localhost:26257/relayguard?sslmode=disable",
        database_url_cloud="postgresql://cloud@host:26257/relayguard?sslmode=require",
    )
    assert "host" in url
    assert "cloud@" in url


def test_cloud_verify_full_uses_system_trust_store(monkeypatch: pytest.MonkeyPatch) -> None:
    from relayguard.config import ensure_database_url_runtime_compat

    monkeypatch.delenv("RELAYGUARD_SSL_ROOT_CERT", raising=False)
    monkeypatch.setattr("relayguard.config.os.path.isfile", lambda _path: False)
    url = ensure_database_url_runtime_compat(
        "postgresql://user:pass@host.cockroachlabs.cloud:26257/relayguard?sslmode=verify-full"
    )
    assert "sslrootcert=system" in url


def test_cloud_verify_full_uses_bundled_cert_when_present(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from relayguard.config import ensure_database_url_runtime_compat

    cert = tmp_path / "root.crt"
    cert.write_text("dummy", encoding="utf-8")
    monkeypatch.setenv("RELAYGUARD_SSL_ROOT_CERT", str(cert))
    url = ensure_database_url_runtime_compat(
        "postgresql://user:pass@host.cockroachlabs.cloud:26257/relayguard?sslmode=verify-full"
    )
    assert f"sslrootcert={cert}" in url


def test_redact_database_url_hides_password() -> None:
    raw = "postgresql://relayguard:supersecret@cluster.example:26257/relayguard?sslmode=require"
    redacted = redact_database_url(raw)
    assert "supersecret" not in redacted
    assert "***" in redacted
    assert "cluster.example" in redacted
    assert "sslmode=require" in redacted


def test_redact_database_url_preserves_verify_full() -> None:
    raw = "postgresql://relayguard_app:secret@host.cockroachlabs.cloud:26257/relayguard?sslmode=verify-full"
    redacted = redact_database_url(raw)
    assert "secret" not in redacted
    assert "sslmode=verify-full" in redacted


def test_settings_from_env_defaults_local_target(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RELAYGUARD_DB_TARGET", raising=False)
    monkeypatch.delenv("DATABASE_URL_CLOUD", raising=False)
    settings = Settings.from_env()
    assert settings.db_target == "local"
    assert "localhost" in settings.database_url or "26257" in settings.database_url


@pytest.mark.integration
def test_db_status_output_excludes_credentials(settings: Settings, db_available: None) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "apps.cli.db_status"],
        capture_output=True,
        text=True,
        check=False,
        env={
            **dict(**{k: v for k, v in __import__("os").environ.items()}),
            "DATABASE_URL_LOCAL": settings.database_url,
            "RELAYGUARD_DB_TARGET": "local",
        },
    )
    assert result.returncode == 0
    assert "RelayGuard Database Status" in result.stdout
    assert "Redacted URL" in result.stdout
    if "password" in settings.database_url.lower():
        assert "password" not in result.stdout.lower() or "***" in result.stdout


@pytest.mark.integration
def test_db_status_collects_local_counts(settings: Settings, db_available: None) -> None:
    from relayguard.db import get_connection
    from relayguard.store import RelayStore

    with get_connection(settings) as conn:
        store = RelayStore(conn, settings)
        incident = store.create_incident("db status test")
        store.seed_demo_memories(incident.incident_id)

    status = collect_database_status(settings)
    output = format_database_status(status)
    assert status.db_target == "local"
    assert status.memory_count >= 5
    assert status.incident_count >= 1
    assert "float8[]" in status.embedding_storage_mode or status.embedding_storage_mode == "vector"
    assert "***" in output


def test_vector_mode_float_array_skips_vector_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def execute(self, sql: str, params: tuple = ()) -> None:
            self.last_sql = sql

        def fetchone(self):
            return None

    class FakeConn:
        def cursor(self):
            return FakeCursor()

    mode = __import__("relayguard.db", fromlist=["ensure_embedding_column"]).ensure_embedding_column(
        FakeConn(),  # type: ignore[arg-type]
        "float_array",
    )
    assert mode == "float8[]"


def test_ccloud_scripts_exist() -> None:
    root = Path(__file__).resolve().parent.parent
    assert (root / "infra" / "ccloud" / "check-cluster.ps1").is_file()
    assert (root / "infra" / "ccloud" / "check-cluster.sh").is_file()


def test_docs_mention_managed_mcp_read_only() -> None:
    root = Path(__file__).resolve().parent.parent
    mcp_doc = (root / "docs" / "mcp-auditor.md").read_text(encoding="utf-8")
    cloud_doc = (root / "docs" / "cockroach-cloud.md").read_text(encoding="utf-8")
    ccloud_doc = (root / "docs" / "ccloud.md").read_text(encoding="utf-8")
    assert "read-only" in mcp_doc.lower()
    assert "SELECT" in mcp_doc
    assert "RELAYGUARD_DB_TARGET" in cloud_doc
    assert "ccloud" in ccloud_doc.lower()


def test_detect_embedding_storage_on_local_db(settings: Settings, db_available: None) -> None:
    import psycopg
    from psycopg.rows import dict_row

    conn = psycopg.connect(settings.database_url, row_factory=dict_row, autocommit=True, connect_timeout=5)
    try:
        mode = detect_embedding_storage(conn)
        assert mode in ("vector", "float8[]", "none")
    finally:
        conn.close()
