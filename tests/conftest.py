from __future__ import annotations

import pytest

from relayguard.config import Settings
from relayguard.db import apply_schema


@pytest.fixture(scope="session")
def settings() -> Settings:
    return Settings.from_env()


@pytest.fixture(scope="session")
def db_available(settings: Settings) -> None:
    try:
        apply_schema(settings)
    except Exception as exc:
        pytest.skip(f"CockroachDB unavailable: {exc}")
