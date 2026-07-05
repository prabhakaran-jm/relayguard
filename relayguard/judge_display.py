"""Judge-facing display labels (contract tested; mirrored in apps/web/lib/display-labels.ts)."""

from __future__ import annotations

ACTION_LABELS: dict[str, str] = {
    "ROUTE_TO_STANDBY": "Route to standby",
    "RESTART_SERVICE": "Restart service",
    "ESCALATE_TO_HUMAN": "Escalate to human",
}

SELECTOR_LABELS: dict[str, str] = {
    "mock": "Guarded selector",
    "bedrock": "Amazon Bedrock",
}

SELECTOR_META: dict[str, str | None] = {
    "mock": "local mock",
    "bedrock": None,
}


def action_display_label(action: str | None) -> str:
    if not action:
        return "—"
    if action in ACTION_LABELS:
        return ACTION_LABELS[action]
    return " ".join(word.capitalize() for word in action.lower().split("_"))


def selector_display_label(selector: str | None) -> str:
    if not selector:
        return "—"
    return SELECTOR_LABELS.get(selector, selector.capitalize())


def selector_meta_label(selector: str | None) -> str | None:
    if not selector:
        return None
    return SELECTOR_META.get(selector)


def selection_reason_display(reason: str | None, selector_type: str | None) -> str | None:
    if not reason:
        return None
    if selector_type == "mock":
        return reason.replace("Mock selector:", "Guarded selector:", 1).replace(
            "mock selector:", "Guarded selector:", 1
        )
    return reason
