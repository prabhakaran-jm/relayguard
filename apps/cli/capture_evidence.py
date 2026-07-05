from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from relayguard.ccloud_cli import resolve_ccloud_bin
from relayguard.evidence_capture import (
    ccloud_failed_message,
    ccloud_skip_message,
    dashboard_instructions,
    ensure_evidence_dir,
)
from relayguard.config import Settings
from relayguard.db import get_connection
from relayguard.store import RelayStore


def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    print(f"wrote {path}")


def _sanitize_env(env: dict[str, str] | None = None) -> dict[str, str]:
    source = env if env is not None else os.environ
    return {key: str(value) for key, value in source.items() if value is not None}


def _run_capture(args: list[str], env: dict[str, str] | None = None) -> tuple[int, str, str]:
    result = subprocess.run(
        args,
        capture_output=True,
        text=True,
        env=_sanitize_env(env) if env is not None else None,
    )
    return result.returncode, result.stdout, result.stderr


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture RelayGuard sponsor evidence into docs/evidence/")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()

    root = args.repo_root
    evidence = ensure_evidence_dir(root)
    python = sys.executable

    # Load .env so CCLOUD_BIN and cluster metadata are visible
    Settings.from_env()

    # db_status
    code, out, err = _run_capture([python, "-m", "apps.cli.db_status"])
    body = out if code == 0 else f"{out}\n{err}\n(db_status exit {code})"
    _write(evidence / "m8_db_status.txt", body)

    # ccloud check (optional — skip cleanly when CLI not installed)
    ccloud_ps1 = root / "infra" / "ccloud" / "check-cluster.ps1"
    ccloud_sh = root / "infra" / "ccloud" / "check-cluster.sh"
    ccloud_bin = resolve_ccloud_bin()
    if not ccloud_bin:
        ccloud_out = ccloud_skip_message()
    elif ccloud_sh.exists():
        check_env = _sanitize_env(os.environ.copy())
        check_env["CCLOUD_BIN"] = ccloud_bin
        if sys.platform == "win32" and ccloud_ps1.exists():
            code, out, err = _run_capture(
                ["powershell", "-File", str(ccloud_ps1)], env=check_env
            )
        else:
            code, out, err = _run_capture(["bash", str(ccloud_sh)], env=check_env)
        ccloud_out = out if code == 0 else ccloud_failed_message(out, err)
    else:
        ccloud_out = "(ccloud check script not found — skipped)\n"
    _write(evidence / "m8_ccloud_check.txt", ccloud_out)

    # latest incident
    latest_id: str | None = None
    settings = Settings.from_env()
    with get_connection(settings) as conn:
        store = RelayStore(conn, settings)
        rows = store.list_incidents(limit=1)
        if rows:
            latest_id = str(rows[0]["incident_id"])

    code, out, err = _run_capture([python, "-m", "apps.cli.list_incidents", "--json", "--limit", "20"])
    _write(
        evidence / "m8_incident_list.json",
        out if code == 0 else json.dumps({"error": err or out}, indent=2),
    )

    if latest_id:
        code, out, err = _run_capture(
            [python, "-m", "apps.cli.audit_incident", "--incident-id", latest_id, "--json"]
        )
        _write(
            evidence / "m8_latest_audit.json",
            out if code == 0 else json.dumps({"error": err or out}, indent=2),
        )
        code, out, err = _run_capture(
            [python, "-m", "apps.cli.audit_incident", "--incident-id", latest_id]
        )
        _write(
            evidence / "m8_latest_audit.txt",
            out if code == 0 else f"{out}\n{err}",
        )
    else:
        _write(evidence / "m8_latest_audit.json", '{"error": "no incidents found"}')
        _write(evidence / "m8_latest_audit.txt", "No incidents found.\n")

    _write(evidence / "m8_dashboard_instructions.txt", dashboard_instructions(latest_id))
    print(f"\nEvidence captured under {evidence}")


if __name__ == "__main__":
    main()
