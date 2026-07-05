from __future__ import annotations

import argparse
import sys
from uuid import UUID

from relayguard.config import Settings
from relayguard.db import get_connection
from relayguard.store import RelayStore
from workers.worker import run_stale_commit


def main() -> None:
    parser = argparse.ArgumentParser(description="Attempt a stale commit with old lease epoch")
    parser.add_argument("incident_id")
    parser.add_argument("intent_id")
    parser.add_argument("--worker-id", default="worker-a")
    parser.add_argument("--lease-epoch", type=int, required=True)
    args = parser.parse_args()

    settings = Settings.from_env()
    with get_connection(settings) as conn:
        store = RelayStore(conn, settings)
        ok = run_stale_commit(
            store,
            UUID(args.incident_id),
            args.worker_id,
            args.lease_epoch,
            UUID(args.intent_id),
        )
    sys.exit(0 if not ok else 1)


if __name__ == "__main__":
    main()
