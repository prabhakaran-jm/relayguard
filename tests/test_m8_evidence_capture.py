from __future__ import annotations

from pathlib import Path

from relayguard.evidence_capture import dashboard_instructions, ensure_evidence_dir, evidence_dir


def test_evidence_dir_path() -> None:
    root = Path(__file__).resolve().parents[1]
    assert evidence_dir(root) == root / "docs" / "evidence"


def test_ensure_evidence_dir_creates_folder(tmp_path: Path) -> None:
    path = ensure_evidence_dir(tmp_path)
    assert path == tmp_path / "docs" / "evidence"
    assert path.is_dir()


def test_dashboard_instructions_include_urls() -> None:
    text = dashboard_instructions("abc-123")
    assert "http://localhost:3000" in text
    assert "abc-123" in text
    assert "DATABASE_URL" in text


def test_ccloud_skip_message_is_judge_friendly() -> None:
    from relayguard.evidence_capture import ccloud_skip_message

    text = ccloud_skip_message()
    assert "SKIPPED" in text
    assert "ccloud CLI was not found" in text
    assert "Require-Command" not in text
