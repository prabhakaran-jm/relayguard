from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest

ROOT = Path(__file__).resolve().parent.parent
HANDLER_PATH = ROOT / "infra" / "aws" / "lambda_worker" / "handler.py"


def _load_handler_module() -> ModuleType:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("relayguard_lambda_handler", HANDLER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


handler = _load_handler_module()


def test_parse_event_run_worker_defaults() -> None:
    incident_id = str(uuid4())
    parsed = handler.parse_event(
        {
            "incident_id": incident_id,
            "mode": "run_worker",
            "fail_after": "ACTION_RESERVED",
        }
    )
    assert parsed["mode"] == "run_worker"
    assert parsed["incident_id"] == UUID(incident_id)
    assert parsed["worker_id"] == "worker-a"
    assert parsed["fail_after"] == "ACTION_RESERVED"


def test_parse_event_stale_commit_requires_fields() -> None:
    with pytest.raises(handler.HandlerError, match="intent_id"):
        handler.parse_event(
            {
                "mode": "stale_commit",
                "incident_id": str(uuid4()),
                "worker_id": "worker-a",
                "lease_epoch": 1,
            }
        )


def test_parse_event_rejects_unknown_mode() -> None:
    with pytest.raises(handler.HandlerError, match="Unsupported mode"):
        handler.parse_event({"mode": "delete_cluster"})


def test_db_status_mode_does_not_expose_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    from relayguard.db import DatabaseStatus

    fake_status = DatabaseStatus(
        db_target="cloud",
        database_target="cloud (host:26257/relayguard)",
        redacted_database_url="postgresql://relayguard_app:***@host:26257/relayguard?sslmode=verify-full",
        database_version="CockroachDB test",
        embedding_storage_mode="vector",
        vector_mode_setting="auto",
        memory_count=5,
        incident_count=1,
        vector_index_present=True,
    )

    with patch.object(handler, "collect_database_status", return_value=fake_status):
        with patch.object(handler, "Settings") as settings_cls:
            settings_cls.from_env.return_value = MagicMock()
            result = handler.dispatch_event({"mode": "db_status"})

    assert result["ok"] is True
    assert result["mode"] == "db_status"
    assert "***" in result["redacted_database_url"]
    assert "supersecret" not in str(result).lower()
    assert "password" not in str(result).lower() or "***" in result["redacted_database_url"]


def test_run_worker_mode_returns_structured_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    incident_id = uuid4()
    intent_id = uuid4()
    settings = MagicMock()
    settings.override.return_value = settings

    store = MagicMock()
    store.get_incident.return_value = MagicMock(lease_epoch=1)
    store.get_latest_checkpoint.return_value = (
        MagicMock(intent_id=str(intent_id), phase="checkpoint.action_reserved"),
        "worker-a",
        1,
    )
    store.get_reserved_intent.return_value = None

    with patch.object(handler, "Settings") as settings_cls:
        settings_cls.from_env.return_value = settings
        with patch.object(handler, "get_connection") as conn_ctx:
            conn_ctx.return_value.__enter__.return_value = MagicMock()
            with patch.object(handler, "RelayStore", return_value=store):
                with patch.object(handler, "run_worker", return_value=2):
                    result = handler.dispatch_event(
                        {
                            "mode": "run_worker",
                            "incident_id": str(incident_id),
                            "worker_id": "worker-a",
                            "fail_after": "ACTION_RESERVED",
                        }
                    )

    assert result["ok"] is True
    assert result["exit_code"] == 2
    assert result["status"] == "simulated_crash"
    assert result["intent_id"] == str(intent_id)


def test_stale_commit_mode_returns_rejected_status() -> None:
    incident_id = uuid4()
    intent_id = uuid4()
    settings = MagicMock()

    with patch.object(handler, "Settings") as settings_cls:
        settings_cls.from_env.return_value = settings
        with patch.object(handler, "get_connection") as conn_ctx:
            conn_ctx.return_value.__enter__.return_value = MagicMock()
            with patch.object(handler, "RelayStore"):
                with patch.object(handler, "run_stale_commit", return_value=False):
                    result = handler.dispatch_event(
                        {
                            "mode": "stale_commit",
                            "incident_id": str(incident_id),
                            "worker_id": "worker-a",
                            "intent_id": str(intent_id),
                            "lease_epoch": 1,
                        }
                    )

    assert result["ok"] is True
    assert result["rejected"] is True
    assert result["status"] == "rejected"


def test_handler_returns_error_for_invalid_event() -> None:
    result = handler.handler({"mode": "run_worker"})
    assert result["ok"] is False
    assert "incident_id" in result["error"]


def test_load_database_url_from_secret_json() -> None:
    from relayguard.secrets import load_database_url_from_secret

    class FakeClient:
        def get_secret_value(self, SecretId: str) -> dict[str, str]:
            return {
                "SecretString": '{"DATABASE_URL":"postgresql://user:secret@host:26257/relayguard?sslmode=verify-full"}'
            }

    fake_boto3 = MagicMock()
    fake_boto3.client.return_value = FakeClient()

    with patch.dict(sys.modules, {"boto3": fake_boto3}):
        url = load_database_url_from_secret("relayguard/db", aws_region="us-east-1")

    assert url.startswith("postgresql://user:")
    assert "host:26257/relayguard" in url


def test_settings_uses_secret_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RELAYGUARD_DB_TARGET", "cloud")
    monkeypatch.setenv("RELAYGUARD_DATABASE_SECRET_NAME", "relayguard/db")
    monkeypatch.delenv("DATABASE_URL_CLOUD", raising=False)
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://root@localhost:26257/relayguard?sslmode=disable",
    )

    with patch(
        "relayguard.secrets.load_database_url_from_secret",
        return_value="postgresql://cloud:***@cloud.example:26257/relayguard?sslmode=verify-full",
    ):
        from relayguard.config import Settings

        settings = Settings.from_env()

    assert settings.database_secret_name == "relayguard/db"
    assert "cloud.example" in settings.database_url


def test_lambda_database_url_uses_bundled_ca_cert(monkeypatch: pytest.MonkeyPatch) -> None:
    from relayguard.config import ensure_database_url_runtime_compat

    monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "relayguard-worker")
    url = ensure_database_url_runtime_compat(
        "postgresql://user:pass@host:26257/relayguard?sslmode=verify-full"
    )
    assert "sslrootcert=/var/task/certs/root.crt" in url
