-- M2 migration: memory embeddings (VECTOR on Cloud, FLOAT8[] locally).
SET database = relayguard;

-- Applied programmatically in relayguard/db.py with VECTOR -> FLOAT8[] fallback.
