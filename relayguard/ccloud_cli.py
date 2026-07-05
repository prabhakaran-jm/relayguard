"""Locate the ccloud CLI when it is installed but not on PATH."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _ccloud_candidates() -> list[Path]:
    home = Path.home()
    local_app = Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local"))
    roaming_app = Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
    binary = "ccloud.exe" if sys.platform == "win32" else "ccloud"
    return [
        REPO_ROOT / "ccloud" / binary,
        roaming_app / "ccloud" / binary,
        local_app / "ccloud" / binary,
        home / "ccloud" / binary,
        home / ".ccloud" / binary,
        Path("C:/Program Files/Cockroach Labs/ccloud") / binary,
        Path("/usr/local/bin/ccloud"),
        home / ".local" / "bin" / "ccloud",
        home / "scoop" / "shims" / binary,
        local_app / "Microsoft" / "WinGet" / "Links" / binary,
    ]


def resolve_ccloud_bin() -> str | None:
    """Return path to ccloud binary, or None if not found."""
    explicit = (os.environ.get("CCLOUD_BIN") or "").strip().strip('"')
    if explicit:
        path = Path(explicit).expanduser()
        return str(path) if path.is_file() else None

    found = shutil.which("ccloud")
    if found:
        return found

    for candidate in _ccloud_candidates():
        if candidate.is_file():
            return str(candidate)
    return None


def ccloud_available() -> bool:
    return resolve_ccloud_bin() is not None
