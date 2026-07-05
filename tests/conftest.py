from __future__ import annotations

import os

import pytest

from relayguard.config import Settings
from relayguard.db import apply_schema


@pytest.fixture(scope="session", autouse=True)
def force_local_test_database() -> None:
    local_url = os.environ.get(
        "DATABASE_URL_LOCAL",
        "postgresql://root@localhost:26257/relayguard?sslmode=disable",
    )
    os.environ["RELAYGUARD_DB_TARGET"] = "local"
    os.environ["DATABASE_URL"] = local_url
    os.environ["DATABASE_URL_LOCAL"] = local_url


@pytest.fixture(scope="session")
def settings() -> Settings:
    local_url = os.environ.get(
        "DATABASE_URL_LOCAL",
        "postgresql://root@localhost:26257/relayguard?sslmode=disable",
    )
    return Settings.from_env().override(
        db_target="local",
        database_url=local_url,
        database_url_local=local_url,
    )


@pytest.fixture(scope="session")
def db_available(settings: Settings) -> None:
    try:
        apply_schema(settings)
    except Exception as exc:
        pytest.skip(f"CockroachDB unavailable: {exc}")
