from __future__ import annotations

import argparse
import json
import sys
from uuid import UUID

from relayguard.audit_reader import AuditReader, format_audit_report
from relayguard.config import Settings
from relayguard.db import get_connection
from relayguard.store import RelayStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Print an evidence-backed RelayGuard audit report")
    parser.add_argument("--incident-id", required=True, help="Incident UUID")
    parser.add_argument("--json", action="store_true", help="Emit JSON for dashboard/API consumers")
    args = parser.parse_args()

    settings = Settings.from_env()
    incident_id = UUID(args.incident_id)

    with get_connection(settings) as conn:
        report = AuditReader(RelayStore(conn, settings)).build_report(incident_id)

    if args.json:
        print(json.dumps(report.model_dump(mode="json"), indent=2))
        sys.exit(0)
    print(format_audit_report(report))
    sys.exit(0 if report.invariant_status == "PASS" else 1)


if __name__ == "__main__":
    main()
