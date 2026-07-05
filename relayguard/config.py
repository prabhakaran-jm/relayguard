from __future__ import annotations

import os
from dataclasses import dataclass, replace

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    database_url: str
    lease_ttl_seconds: int
    worker_id: str
    fail_after: str | None
    action_selector: str
    bedrock_model_id: str
    aws_region: str
    incident_severity: str
    action_min_confidence: float

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
            action_selector=os.environ.get("ACTION_SELECTOR", "mock").lower(),
            bedrock_model_id=os.environ.get(
                "BEDROCK_MODEL_ID",
                "anthropic.claude-3-haiku-20240307-v1:0",
            ),
            aws_region=os.environ.get("AWS_REGION", "us-east-1"),
            incident_severity=os.environ.get("INCIDENT_SEVERITY", "high"),
            action_min_confidence=float(os.environ.get("ACTION_MIN_CONFIDENCE", "0.5")),
        )

    def override(self, **kwargs: object) -> Settings:
        return replace(self, **kwargs)
