from __future__ import annotations

from pathlib import Path

from relayguard.ccloud_cli import resolve_ccloud_bin


def test_resolve_ccloud_bin_from_env(tmp_path: Path, monkeypatch) -> None:
    fake = tmp_path / "ccloud.exe"
    fake.write_text("", encoding="utf-8")
    monkeypatch.setenv("CCLOUD_BIN", str(fake))
    assert resolve_ccloud_bin() == str(fake)


def test_resolve_ccloud_bin_missing_env(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("CCLOUD_BIN", raising=False)
    monkeypatch.setenv("CCLOUD_BIN", str(tmp_path / "missing.exe"))
    assert resolve_ccloud_bin() is None
