from __future__ import annotations

import argparse
import json
import sys

from relayguard.audit_reader import AuditReader
from relayguard.config import Settings
from relayguard.db import get_connection
from relayguard.store import RelayStore


def main() -> None:
    parser = argparse.ArgumentParser(description="List recent RelayGuard incidents")
    parser.add_argument("--limit", type=int, default=20, help="Maximum incidents to return")
    parser.add_argument("--json", action="store_true", help="Emit JSON for dashboard/API consumers")
    args = parser.parse_args()

    settings = Settings.from_env()
    with get_connection(settings) as conn:
        store = RelayStore(conn, settings)
        rows = store.list_incidents(limit=args.limit)
        incidents = []
        for row in rows:
            incident_id = str(row["incident_id"])
            invariant_status = None
            try:
                report = AuditReader(store).build_report(row["incident_id"])
                invariant_status = report.invariant_status
            except Exception:
                invariant_status = None
            incidents.append(
                {
                    "incident_id": incident_id,
                    "title": row["title"],
                    "status": row["status"],
                    "created_at": str(row["created_at"]) if row.get("created_at") else None,
                    "invariant_status": invariant_status,
                }
            )

    if args.json:
        print(json.dumps({"incidents": incidents}, indent=2))
    else:
        for item in incidents:
            print(
                f"{item['incident_id']}  {item['status']:12s}  "
                f"{item.get('invariant_status') or '-':4s}  {item['title']}"
            )


if __name__ == "__main__":
    main()
