from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    database_url: str
    lease_ttl_seconds: int
    worker_id: str
    fail_after: str | None

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            database_url=os.environ.get(
                "DATABASE_URL",
                "postgresql://root@localhost:26257/relayguard?sslmode=disable",
            ),
            lease_ttl_seconds=int(os.environ.get("LEASE_TTL_SECONDS", "5")),
            worker_id=os.environ.get("WORKER_ID", "worker-a"),
            fail_after=os.environ.get("FAIL_AFTER") or None,
        )
