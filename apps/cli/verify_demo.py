from __future__ import annotations

import argparse
import sys
from uuid import UUID

from relayguard.audit_timeline import sort_audit_events_story_order
from relayguard.config import Settings
from relayguard.db import get_connection
from relayguard.store import RelayStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify RelayGuard demo invariants")
    parser.add_argument("incident_id", help="Incident UUID")
    args = parser.parse_args()

    settings = Settings.from_env()
    incident_id = UUID(args.incident_id)
    errors: list[str] = []

    with get_connection(settings) as conn:
        store = RelayStore(conn, settings)
        committed = store.count_committed_actions(incident_id)
        events = sort_audit_events_story_order(store.list_audit_events(incident_id))
        event_types = [e.event_type for e in events]

        retrieved_count = sum(1 for e in events if e.event_type == "memory.retrieved")
        classified_events = [e for e in events if e.event_type == "memory.classified"]
        avoid_count = sum(1 for e in classified_events if e.details_json.get("verdict") == "AVOID")
        use_count = sum(1 for e in classified_events if e.details_json.get("verdict") == "USE")
        stale_rejects = sum(1 for e in events if e.event_type == "action.commit_rejected")

        retrieved_memories = 0
        for event in events:
            if event.event_type == "memory.retrieved":
                retrieved_memories = max(retrieved_memories, len(event.details_json.get("results", [])))

        print(f"Incident: {incident_id}")
        print(f"Committed actions: {committed}")
        print(f"Stale commits rejected: {stale_rejects}")
        print(f"Retrieved memories: {retrieved_memories}")
        print(f"AVOID memories: {avoid_count}")
        print(f"USE memories: {use_count}")
        print(f"Audit events: {len(events)}")
        print("--- audit trail ---")
        for event in events:
            owner = event.lease_owner or "-"
            epoch = event.lease_epoch if event.lease_epoch is not None else "-"
            print(f"  {event.event_type:30s} worker={owner} epoch={epoch}")

        if committed != 1:
            errors.append(f"expected exactly 1 committed action, got {committed}")
        if stale_rejects < 1:
            errors.append(f"expected at least 1 stale commit rejection, got {stale_rejects}")
        if retrieved_memories < 4:
            errors.append(f"expected at least 4 retrieved memories, got {retrieved_memories}")
        if avoid_count < 1:
            errors.append(f"expected at least 1 AVOID memory, got {avoid_count}")
        if use_count < 1:
            errors.append(f"expected at least 1 USE memory, got {use_count}")

        required_events = [
            "incident.created",
            "memories.seeded",
            "memory.retrieved",
            "memory.classified",
            "lease.claimed",
            "action_intent.reserved",
            "action.committed",
            "action.commit_rejected",
        ]
        for req in required_events:
            if req not in event_types:
                errors.append(f"missing audit event: {req}")

    if errors:
        print("--- FAIL ---")
        for err in errors:
            print(f"  ✗ {err}")
        sys.exit(1)

    print("--- PASS ---")
    print("RelayGuard demo verified: one committed action, semantic retrieval, MemoryGate audit trail.")
    sys.exit(0)


if __name__ == "__main__":
    main()
