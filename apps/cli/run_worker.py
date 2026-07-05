from __future__ import annotations

import argparse
import sys
from uuid import UUID

from relayguard.config import Settings
from relayguard.db import get_connection
from relayguard.store import RelayStore
from workers.worker import run_worker


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a RelayGuard worker")
    parser.add_argument("incident_id", help="Incident UUID")
    args = parser.parse_args()

    settings = Settings.from_env()
    incident_id = UUID(args.incident_id)

    with get_connection(settings) as conn:
        store = RelayStore(conn, settings)
        code = run_worker(store, incident_id, settings)

    sys.exit(code)


if __name__ == "__main__":
    main()
