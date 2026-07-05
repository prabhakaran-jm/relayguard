from __future__ import annotations

import logging
import os
from dataclasses import dataclass, replace
from typing import Literal
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv()

DbTarget = Literal["local", "cloud"]
VectorMode = Literal["auto", "vector", "float_array"]

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Settings:
    database_url: str
    db_target: DbTarget
    database_url_local: str
    database_url_cloud: str | None
    cockroach_vector_mode: VectorMode
    ccloud_cluster_name: str | None
    ccloud_database_name: str
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
        database_url_local = os.environ.get("DATABASE_URL_LOCAL") or os.environ.get(
            "DATABASE_URL",
            "postgresql://root@localhost:26257/relayguard?sslmode=disable",
        )
        database_url_cloud = os.environ.get("DATABASE_URL_CLOUD") or None
        legacy_database_url = os.environ.get("DATABASE_URL")
        db_target = _parse_db_target(os.environ.get("RELAYGUARD_DB_TARGET", "local"))
        vector_mode = _parse_vector_mode(os.environ.get("COCKROACH_VECTOR_MODE", "auto"))

        database_url = resolve_database_url(
            db_target=db_target,
            database_url_local=database_url_local,
            database_url_cloud=database_url_cloud,
            legacy_database_url=legacy_database_url,
        )

        return cls(
            database_url=database_url,
            db_target=db_target,
            database_url_local=database_url_local,
            database_url_cloud=database_url_cloud,
            cockroach_vector_mode=vector_mode,
            ccloud_cluster_name=os.environ.get("CCLOUD_CLUSTER_NAME") or None,
            ccloud_database_name=os.environ.get("CCLOUD_DATABASE_NAME", "relayguard"),
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
        updated = replace(self, **kwargs)
        if "database_url" not in kwargs and any(
            key in kwargs
            for key in ("db_target", "database_url_local", "database_url_cloud")
        ):
            return replace(
                updated,
                database_url=resolve_database_url(
                    db_target=updated.db_target,
                    database_url_local=updated.database_url_local,
                    database_url_cloud=updated.database_url_cloud,
                    legacy_database_url=updated.database_url,
                ),
            )
        return updated

    @property
    def safe_database_target(self) -> str:
        return describe_database_target(self.database_url, self.db_target)


def resolve_database_url(
    *,
    db_target: DbTarget,
    database_url_local: str,
    database_url_cloud: str | None,
    legacy_database_url: str | None = None,
) -> str:
    if db_target == "cloud":
        if database_url_cloud:
            return database_url_cloud
        if legacy_database_url:
            return legacy_database_url
        raise ValueError(
            "RELAYGUARD_DB_TARGET=cloud requires DATABASE_URL_CLOUD or DATABASE_URL"
        )
    return database_url_local


def describe_database_target(database_url: str, db_target: DbTarget) -> str:
    parsed = urlparse(database_url)
    host = parsed.hostname or "unknown-host"
    port = parsed.port or 26257
    database = parsed.path.lstrip("/") or "relayguard"
    return f"{db_target} ({host}:{port}/{database})"


def redact_database_url(database_url: str) -> str:
    parsed = urlparse(database_url)
    host = parsed.hostname or "unknown-host"
    port = parsed.port or 26257
    database = parsed.path.lstrip("/") or "relayguard"
    user = parsed.username or "unknown-user"
    query = parsed.query or "sslmode=disable"
    return f"postgresql://{user}:***@{host}:{port}/{database}?{query}"


def _parse_db_target(value: str) -> DbTarget:
    target = value.strip().lower()
    if target not in ("local", "cloud"):
        raise ValueError("RELAYGUARD_DB_TARGET must be 'local' or 'cloud'")
    return target  # type: ignore[return-value]


def _parse_vector_mode(value: str) -> VectorMode:
    mode = value.strip().lower().replace("-", "_")
    if mode == "float_array":
        return "float_array"
    if mode in ("auto", "vector"):
        return mode  # type: ignore[return-value]
    raise ValueError("COCKROACH_VECTOR_MODE must be auto, vector, or float_array")
