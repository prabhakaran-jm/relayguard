"""Helpers for sponsor evidence capture into docs/evidence/."""

from __future__ import annotations

from pathlib import Path

from relayguard.ccloud_cli import resolve_ccloud_bin

REPO_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_DIR = REPO_ROOT / "docs" / "evidence"


def evidence_dir(repo_root: Path | None = None) -> Path:
    return (repo_root or REPO_ROOT) / "docs" / "evidence"


def ensure_evidence_dir(repo_root: Path | None = None) -> Path:
    path = evidence_dir(repo_root)
    path.mkdir(parents=True, exist_ok=True)
    return path


def ccloud_available() -> bool:
    return resolve_ccloud_bin() is not None


def ccloud_skip_message() -> str:
    return """ccloud CLI check - SKIPPED
==========================

The ccloud CLI was not found on PATH or in common install locations.

Fix options:
  1. Add ccloud to your PATH and open a new terminal
  2. Set CCLOUD_BIN in .env to the full path of ccloud.exe, for example:
       CCLOUD_BIN=C:\\Users\\You\\AppData\\Local\\ccloud\\ccloud.exe
  3. Extract the CLI into the repo: relayguard/ccloud/ccloud.exe

Then run: ccloud auth login
Re-run: scripts/capture-evidence.ps1

Manual check:
  .\\infra\\ccloud\\check-cluster.ps1
  bash infra/ccloud/check-cluster.sh
"""


def ccloud_failed_message(stdout: str, stderr: str) -> str:
    detail = "\n".join(part.strip() for part in (stdout, stderr) if part and part.strip())
    if not detail:
        detail = "(no output)"
    return f"""ccloud CLI check - FAILED
=========================

{detail}

Fix auth or cluster config, then re-run scripts/capture-evidence.ps1
"""


def dashboard_instructions(incident_id: str | None = None) -> str:
    railway_base = "https://relayguard-production.up.railway.app"
    lines = [
        "RelayGuard judge dashboard",
        "==========================",
        "",
        "Live (Railway):",
        f"   {railway_base}",
    ]
    if incident_id:
        lines.append(f"   {railway_base}/incident/{incident_id}")
    lines.extend(
        [
            "",
            "Local:",
            "1. Start the read-only dashboard:",
            "   .\\scripts\\run-web.ps1",
            "   ./scripts/run-web.sh",
            "",
            "2. Open in browser:",
            "   http://localhost:3000",
        ]
    )
    if incident_id:
        lines.extend(
            [
                f"   http://localhost:3000/incident/{incident_id}",
                "",
                f"Latest captured incident: {incident_id}",
            ]
        )
    lines.extend(
        [
            "",
            "3. API (read-only JSON):",
            "   GET http://localhost:3000/api/incidents",
            "   GET http://localhost:3000/api/incidents/<incident-id>",
            "",
            "DATABASE_URL is never exposed to the browser.",
        ]
    )
    return "\n".join(lines) + "\n"
