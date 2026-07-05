SET database = relayguard;

-- Demo memories are inserted per-incident by the create-incident CLI.
-- memory_kind values drive MemoryGate classification:
--   current_runbook, expired_runbook, failed_restart, historical_incident
