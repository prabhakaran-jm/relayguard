from __future__ import annotations

import logging
import os
from dataclasses import dataclass, replace
from typing import Literal
from urllib.parse import urlparse

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

DbTarget = Literal["local", "cloud"]
VectorMode = Literal["auto", "vector", "float_array"]

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Settings:
    database_url: str
    db_target: DbTarget
    database_url_local: str
    database_url_cloud: str | None
    database_secret_name: str | None
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
        database_secret_name = os.environ.get("RELAYGUARD_DATABASE_SECRET_NAME") or None
        legacy_database_url = os.environ.get("DATABASE_URL")
        db_target = _parse_db_target(os.environ.get("RELAYGUARD_DB_TARGET", "local"))
        vector_mode = _parse_vector_mode(os.environ.get("COCKROACH_VECTOR_MODE", "auto"))
        aws_region = os.environ.get("AWS_REGION", "us-east-1")

        if database_secret_name and not database_url_cloud:
            from relayguard.secrets import load_database_url_from_secret

            database_url_cloud = load_database_url_from_secret(
                database_secret_name,
                aws_region=aws_region,
            )

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
            database_secret_name=database_secret_name,
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
            aws_region=aws_region,
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
            return ensure_database_url_runtime_compat(database_url_cloud)
        if legacy_database_url:
            return ensure_database_url_runtime_compat(legacy_database_url)
        raise ValueError(
            "RELAYGUARD_DB_TARGET=cloud requires DATABASE_URL_CLOUD or DATABASE_URL"
        )
    return database_url_local


_BUNDLED_SSL_ROOT_CERTS = (
    "/var/task/certs/root.crt",
    "/app/certs/root.crt",
)


def _bundled_ssl_root_cert() -> str | None:
    override = os.environ.get("RELAYGUARD_SSL_ROOT_CERT")
    if override:
        return override
    for path in _BUNDLED_SSL_ROOT_CERTS:
        if os.path.isfile(path):
            return path
    return None


def ensure_database_url_runtime_compat(database_url: str) -> str:
    """Adjust SSL settings for runtimes without a local PostgreSQL CA bundle."""
    lowered = database_url.lower()
    if "sslmode=verify-full" not in lowered and "sslmode=verify_full" not in lowered:
        return database_url
    if "sslrootcert=" in lowered:
        return database_url
    separator = "&" if "?" in database_url else "?"
    cert = _bundled_ssl_root_cert()
    if cert:
        return f"{database_url}{separator}sslrootcert={cert}"
    return f"{database_url}{separator}sslrootcert=system"


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
