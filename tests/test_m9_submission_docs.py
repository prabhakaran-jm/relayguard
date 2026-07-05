from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

M9_DOCS = [
    "docs/architecture-diagram.md",
    "docs/architecture-diagram.mmd",
    "docs/architecture-diagram.png",
    "docs/evidence/README.md",
]

MCP_EVIDENCE = [
    "docs/evidence/mcp_worker_rejection_question.png",
    "docs/evidence/mcp_worker_rejection_answer.png",
]

UNSAFE_PHRASES = [
    "exactly-once execution",
    "exactly-once enforcement",
    "guaranteed exactly once",
    "exactly-once proof",
    "exactly-once remediation",
]


def test_m9_submission_docs_exist() -> None:
    missing = [rel for rel in M9_DOCS if not (REPO_ROOT / rel).is_file()]
    assert not missing, f"Missing submission docs: {missing}"


def test_m10_mcp_evidence_screenshots_exist() -> None:
    missing = [rel for rel in MCP_EVIDENCE if not (REPO_ROOT / rel).is_file()]
    assert not missing, f"Missing MCP evidence: {missing}"


def test_m10_docs_reference_mcp_screenshots() -> None:
    for rel in ("docs/evidence/README.md", "docs/mcp-auditor.md"):
        text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        assert "mcp_worker_rejection_question.png" in text
        assert "mcp_worker_rejection_answer.png" in text


def test_m10_no_unsafe_exactly_once_wording_in_docs() -> None:
    docs_root = REPO_ROOT / "docs"
    offenders: list[str] = []
    for path in docs_root.rglob("*.md"):
        text = path.read_text(encoding="utf-8").lower()
        for phrase in UNSAFE_PHRASES:
            if phrase in text:
                offenders.append(f"{path.relative_to(REPO_ROOT)}: {phrase}")
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8").lower()
    for phrase in UNSAFE_PHRASES:
        if phrase in readme:
            offenders.append(f"README.md: {phrase}")
    assert not offenders, "Unsafe wording found:\n" + "\n".join(offenders)


def test_m9_architecture_diagram_mentions_core_components() -> None:
    mmd = (REPO_ROOT / "docs/architecture-diagram.mmd").read_text(encoding="utf-8")
    for token in (
        "CockroachDB",
        "VECTOR",
        "Lambda worker-a",
        "Lambda worker-b",
        "Bedrock",
        "Secrets Manager",
        "CloudWatch",
        "Managed MCP",
        "ccloud",
        "audit_events",
    ):
        assert token in mmd, f"architecture diagram missing {token}"


def test_m10_readme_references_mcp_evidence() -> None:
    text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "mcp_worker_rejection_question.png" in text
    assert "mcp_worker_rejection_answer.png" in text
