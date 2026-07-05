from __future__ import annotations

import argparse
import sys
from uuid import UUID

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
        events = store.list_audit_events(incident_id)
        event_types = [e.event_type for e in events]

        print(f"Incident: {incident_id}")
        print(f"Committed actions: {committed}")
        print(f"Audit events: {len(events)}")
        print("--- audit trail ---")
        for event in events:
            owner = event.lease_owner or "-"
            epoch = event.lease_epoch if event.lease_epoch is not None else "-"
            print(f"  {event.event_type:30s} worker={owner} epoch={epoch}")

        if committed != 1:
            errors.append(f"expected exactly 1 committed action, got {committed}")

        required_events = [
            "incident.created",
            "memories.seeded",
            "lease.claimed",
            "action_intent.reserved",
            "action.committed",
        ]
        for req in required_events:
            if req not in event_types:
                errors.append(f"missing audit event: {req}")

        if "action.commit_rejected" not in event_types:
            errors.append("missing stale commit rejection audit event")

    if errors:
        print("--- FAIL ---")
        for err in errors:
            print(f"  ✗ {err}")
        sys.exit(1)

    print("--- PASS ---")
    print("RelayGuard demo verified: one committed action, full audit trail.")
    sys.exit(0)


if __name__ == "__main__":
    main()
