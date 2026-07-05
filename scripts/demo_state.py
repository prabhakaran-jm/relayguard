"""Print latest checkpoint state and lease info for demo orchestration."""
from __future__ import annotations

import json
import sys
from uuid import UUID

from relayguard.config import Settings
from relayguard.db import get_connection
from relayguard.store import RelayStore


def main() -> None:
    incident_id = UUID(sys.argv[1])
    settings = Settings.from_env()
    with get_connection(settings) as conn:
        store = RelayStore(conn, settings)
        incident = store.get_incident(incident_id)
        checkpoint = store.get_latest_checkpoint(incident_id)
        if checkpoint is None or incident is None:
            print(json.dumps({"error": "no checkpoint"}))
            sys.exit(1)
        state, owner, epoch = checkpoint
        intent_id = state.intent_id
        if intent_id is None:
            reserved = store.get_reserved_intent(incident_id)
            if reserved:
                intent_id = str(reserved.intent_id)
        print(
            json.dumps(
                {
                    "incident_id": str(incident_id),
                    "lease_owner": owner,
                    "lease_epoch": epoch,
                    "intent_id": intent_id,
                    "phase": state.phase,
                    "incident_lease_epoch": incident.lease_epoch,
                }
            )
        )


if __name__ == "__main__":
    main()
