from __future__ import annotations

import pytest
from psycopg.errors import SerializationFailure

from relayguard.db import run_with_retry


class _FakeConn:
    def __init__(self) -> None:
        self.rollbacks = 0

    def rollback(self) -> None:
        self.rollbacks += 1


def test_run_with_retry_succeeds_after_two_failures() -> None:
    calls = {"n": 0}

    def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise SerializationFailure("restart transaction")
        return "ok"

    conn = _FakeConn()
    result = run_with_retry(flaky, conn, max_retries=3)

    assert result == "ok"
    assert calls["n"] == 3
    assert conn.rollbacks == 2


def test_run_with_retry_reraises_after_exhaustion() -> None:
    calls = {"n": 0}

    def always_fails() -> str:
        calls["n"] += 1
        raise SerializationFailure("restart transaction")

    conn = _FakeConn()
    with pytest.raises(SerializationFailure):
        run_with_retry(always_fails, conn, max_retries=3)

    assert calls["n"] == 4  # initial attempt + 3 retries
