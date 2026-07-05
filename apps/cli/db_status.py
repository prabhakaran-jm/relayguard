from __future__ import annotations

import sys

from relayguard.config import Settings
from relayguard.db import collect_database_status, format_database_status


def main() -> None:
    settings = Settings.from_env()
    try:
        status = collect_database_status(settings)
    except Exception as exc:
        print(f"Database status check failed: {exc}")
        sys.exit(1)

    print(format_database_status(status))

    raw_password = ""
    if settings.database_url and "@" in settings.database_url:
        userinfo = settings.database_url.split("://", 1)[-1].split("@", 1)[0]
        if ":" in userinfo:
            raw_password = userinfo.split(":", 1)[1]

    if raw_password and raw_password in format_database_status(status):
        print("Credential leak detected in db_status output", file=sys.stderr)
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
