from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)

_URL_KEYS = (
    "DATABASE_URL",
    "database_url",
    "DATABASE_URL_CLOUD",
    "database_url_cloud",
)


def load_database_url_from_secret(secret_name: str, *, aws_region: str = "us-east-1") -> str:
    """Load a PostgreSQL connection string from AWS Secrets Manager."""
    import boto3

    logger.info("Loading database URL from secret %s", secret_name)
    client = boto3.client("secretsmanager", region_name=aws_region)
    response = client.get_secret_value(SecretId=secret_name)
    secret_string = response.get("SecretString", "")
    if not secret_string:
        raise ValueError(f"Secret {secret_name} is empty")

    stripped = secret_string.strip()
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        payload = None

    if isinstance(payload, dict):
        for key in _URL_KEYS:
            value = payload.get(key)
            if value:
                return str(value).strip()

    if stripped.startswith("postgresql://") or stripped.startswith("postgres://"):
        return stripped

    raise ValueError(f"Secret {secret_name} does not contain a database URL")
