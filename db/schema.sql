CREATE DATABASE IF NOT EXISTS relayguard;

SET database = relayguard;

CREATE TABLE IF NOT EXISTS incidents (
    incident_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title             STRING NOT NULL,
    status            STRING NOT NULL DEFAULT 'open',
    lease_owner       STRING,
    lease_epoch       INT NOT NULL DEFAULT 0,
    lease_expires_at  TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS memories (
    memory_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id  UUID NOT NULL REFERENCES incidents(incident_id),
    label        STRING NOT NULL,
    content      STRING NOT NULL,
    memory_kind  STRING NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS checkpoints (
    checkpoint_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id   UUID NOT NULL REFERENCES incidents(incident_id),
    lease_owner   STRING NOT NULL,
    lease_epoch   INT NOT NULL,
    state_json    JSONB NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS action_intents (
    intent_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id      UUID NOT NULL REFERENCES incidents(incident_id),
    action_type      STRING NOT NULL,
    idempotency_key  STRING NOT NULL,
    status           STRING NOT NULL DEFAULT 'reserved',
    lease_owner      STRING NOT NULL,
    lease_epoch      INT NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (incident_id, action_type, idempotency_key)
);

CREATE TABLE IF NOT EXISTS action_results (
    result_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    intent_id     UUID NOT NULL REFERENCES action_intents(intent_id),
    incident_id   UUID NOT NULL REFERENCES incidents(incident_id),
    action_type   STRING NOT NULL,
    status        STRING NOT NULL,
    lease_owner   STRING NOT NULL,
    lease_epoch   INT NOT NULL,
    committed_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audit_events (
    event_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id   UUID NOT NULL REFERENCES incidents(incident_id),
    event_type    STRING NOT NULL,
    lease_owner   STRING,
    lease_epoch   INT,
    details_json  JSONB NOT NULL DEFAULT '{}',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_incidents_lease ON incidents (lease_expires_at);
CREATE INDEX IF NOT EXISTS idx_checkpoints_incident ON checkpoints (incident_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_incident ON audit_events (incident_id, created_at);
