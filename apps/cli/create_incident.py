from __future__ import annotations

import argparse
import sys

from relayguard.config import Settings
from relayguard.db import apply_schema, get_connection
from relayguard.store import RelayStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a RelayGuard demo incident")
    parser.add_argument("--title", default="API latency spike in us-east-1")
    parser.add_argument("--apply-schema", action="store_true", help="Apply DB schema before creating")
    args = parser.parse_args()

    settings = Settings.from_env()
    if args.apply_schema:
        print("Applying schema...")
        apply_schema(settings)

    with get_connection(settings) as conn:
        store = RelayStore(conn, settings)
        incident = store.create_incident(args.title)
        memories = store.seed_demo_memories(incident.incident_id)
        print(f"Created incident: {incident.incident_id}")
        print(f"Seeded {len(memories)} demo memories")
        print(incident.incident_id)


if __name__ == "__main__":
    main()
