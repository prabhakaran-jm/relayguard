from __future__ import annotations

from relayguard.judge_display import (
    action_display_label,
    selection_reason_display,
    selector_display_label,
    selector_meta_label,
)


def test_action_display_label() -> None:
    assert action_display_label("ROUTE_TO_STANDBY") == "Route to standby"
    assert action_display_label("RESTART_SERVICE") == "Restart service"
    assert action_display_label(None) == "—"


def test_selector_display_label() -> None:
    assert selector_display_label("mock") == "Guarded selector"
    assert selector_display_label("bedrock") == "Amazon Bedrock"
    assert selector_meta_label("mock") == "local mock"
    assert selector_meta_label("bedrock") is None


def test_selection_reason_display_masks_mock() -> None:
    reason = "Mock selector: approved runbook recommends routing to standby."
    assert selection_reason_display(reason, "mock") == (
        "Guarded selector: approved runbook recommends routing to standby."
    )
    assert selection_reason_display(reason, "bedrock") == reason
