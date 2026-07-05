-- Reference queries for RelayGuard audit reporting (M4).
-- Used by relayguard/audit_reader.py and future Managed MCP read-only tools.

-- Incident summary
SELECT incident_id, title, status, lease_owner, lease_epoch, created_at, updated_at
FROM incidents
WHERE incident_id = $1;

-- Full audit trail
SELECT event_id, incident_id, event_type, lease_owner, lease_epoch, details_json, created_at
FROM audit_events
WHERE incident_id = $1
ORDER BY created_at;

-- Memory retrieval evidence
SELECT event_id, details_json, created_at
FROM audit_events
WHERE incident_id = $1 AND event_type = 'memory.retrieved'
ORDER BY created_at;

-- MemoryGate classifications
SELECT event_id, details_json, lease_owner, lease_epoch, created_at
FROM audit_events
WHERE incident_id = $1 AND event_type = 'memory.classified'
ORDER BY created_at;

-- Action selection decision
SELECT event_id, details_json, lease_owner, lease_epoch, created_at
FROM audit_events
WHERE incident_id = $1 AND event_type = 'action.selected'
ORDER BY created_at DESC
LIMIT 1;

-- Reserved intents
SELECT intent_id, action_type, idempotency_key, status, lease_owner, lease_epoch, created_at
FROM action_intents
WHERE incident_id = $1
ORDER BY created_at;

-- Committed results
SELECT result_id, intent_id, action_type, status, lease_owner, lease_epoch, committed_at
FROM action_results
WHERE incident_id = $1
ORDER BY committed_at;

-- Checkpoint phases
SELECT event_id, event_type, lease_owner, lease_epoch, details_json, created_at
FROM audit_events
WHERE incident_id = $1 AND event_type LIKE 'checkpoint.%'
ORDER BY created_at;

-- Stale commit rejections
SELECT event_id, lease_owner, lease_epoch, details_json, created_at
FROM audit_events
WHERE incident_id = $1 AND event_type = 'action.commit_rejected'
ORDER BY created_at;
