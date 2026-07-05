"""Pluggable action selection with mock and Bedrock-backed selectors."""

from __future__ import annotations

import json
import os
from typing import Any, Protocol

from pydantic import BaseModel, Field, ValidationError

from relayguard.config import Settings
from relayguard.models import ActionType, MemoryClassification

ALLOWED_ACTIONS: tuple[ActionType, ...] = (
    ActionType.ROUTE_TO_STANDBY,
    ActionType.RESTART_SERVICE,
    ActionType.ESCALATE_TO_HUMAN,
)

MIN_CONFIDENCE = float(os.environ.get("ACTION_MIN_CONFIDENCE", "0.5"))


class MemoryContext(BaseModel):
    memory_id: str
    label: str
    content: str | None = None
    caution: str | None = None


class BlockedMemorySummary(BaseModel):
    memory_id: str
    label: str
    verdict: str
    reason: str


class ActionSelectorContext(BaseModel):
    incident_title: str
    incident_severity: str
    use_memories: list[MemoryContext] = Field(default_factory=list)
    inspect_memories: list[MemoryContext] = Field(default_factory=list)
    blocked_memories: list[BlockedMemorySummary] = Field(default_factory=list)
    allowed_actions: list[str] = Field(
        default_factory=lambda: [action.value for action in ALLOWED_ACTIONS]
    )


class ActionSelection(BaseModel):
    action_type: ActionType
    confidence: float
    reason: str
    used_memory_ids: list[str] = Field(default_factory=list)
    inspected_memory_ids: list[str] = Field(default_factory=list)
    fallback_used: bool = False
    selector_type: str = "mock"


class BedrockActionResponse(BaseModel):
    action_type: str
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    used_memory_ids: list[str] = Field(default_factory=list)
    inspected_memory_ids: list[str] = Field(default_factory=list)


class ActionSelector(Protocol):
    selector_type: str

    def select_action(self, context: ActionSelectorContext) -> ActionSelection: ...


class MockActionSelector:
    selector_type = "mock"

    def select_action(self, context: ActionSelectorContext) -> ActionSelection:
        used = [memory.memory_id for memory in context.use_memories]
        inspected = [memory.memory_id for memory in context.inspect_memories]
        return ActionSelection(
            action_type=ActionType.ROUTE_TO_STANDBY,
            confidence=1.0,
            reason="Mock selector: approved runbook recommends routing to standby.",
            used_memory_ids=used,
            inspected_memory_ids=inspected,
            fallback_used=False,
            selector_type=self.selector_type,
        )


def build_selector_context(
    incident_title: str,
    incident_severity: str,
    classified_rows: list[dict[str, Any]],
) -> ActionSelectorContext:
    use_memories: list[MemoryContext] = []
    inspect_memories: list[MemoryContext] = []
    blocked: list[BlockedMemorySummary] = []

    for row in classified_rows:
        memory_id = str(row["memory_id"])
        label = str(row["label"])
        verdict = str(row["classification"])
        reason = str(row["reason"])

        if verdict == MemoryClassification.USE.value:
            use_memories.append(
                MemoryContext(memory_id=memory_id, label=label, content=row.get("content"))
            )
        elif verdict == MemoryClassification.INSPECT.value:
            inspect_memories.append(
                MemoryContext(
                    memory_id=memory_id,
                    label=label,
                    content=row.get("content"),
                    caution="requires human review before acting on this precedent",
                )
            )
        elif verdict == MemoryClassification.AVOID.value:
            blocked.append(
                BlockedMemorySummary(
                    memory_id=memory_id,
                    label=label,
                    verdict=verdict,
                    reason=reason,
                )
            )

    return ActionSelectorContext(
        incident_title=incident_title,
        incident_severity=incident_severity,
        use_memories=use_memories,
        inspect_memories=inspect_memories,
        blocked_memories=blocked,
    )


def build_action_prompt(context: ActionSelectorContext) -> str:
    """Serialize selector input. AVOID memory content is excluded by design."""
    payload = {
        "incident_title": context.incident_title,
        "incident_severity": context.incident_severity,
        "use_memories": [memory.model_dump() for memory in context.use_memories],
        "inspect_memories": [memory.model_dump() for memory in context.inspect_memories],
        "blocked_evidence": [blocked.model_dump() for blocked in context.blocked_memories],
        "allowed_actions": context.allowed_actions,
        "required_json_schema": {
            "action_type": "one of allowed_actions",
            "confidence": "float between 0 and 1",
            "reason": "short explanation",
            "used_memory_ids": ["memory labels or ids from use_memories"],
            "inspected_memory_ids": ["memory labels or ids from inspect_memories"],
        },
        "instructions": [
            "Choose exactly one allowed action.",
            "Return strict JSON only with no markdown or shell commands.",
            "Do not recommend actions outside allowed_actions.",
            "Blocked evidence is for explanation only; do not treat it as action support.",
        ],
    }
    return json.dumps(payload, indent=2)


def parse_bedrock_response(
    raw_text: str,
    *,
    min_confidence: float = MIN_CONFIDENCE,
) -> ActionSelection:
    """Validate Bedrock JSON; fall back to ESCALATE_TO_HUMAN on any guardrail breach."""
    try:
        text = raw_text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        data = json.loads(text)
        parsed = BedrockActionResponse.model_validate(data)
        action = ActionType(parsed.action_type)
        if action not in ALLOWED_ACTIONS:
            raise ValueError(f"unknown action {parsed.action_type}")
        if parsed.confidence < min_confidence:
            raise ValueError(f"low confidence {parsed.confidence}")
        return ActionSelection(
            action_type=action,
            confidence=parsed.confidence,
            reason=parsed.reason,
            used_memory_ids=parsed.used_memory_ids,
            inspected_memory_ids=parsed.inspected_memory_ids,
            fallback_used=False,
            selector_type="bedrock",
        )
    except (json.JSONDecodeError, ValidationError, ValueError, KeyError):
        return ActionSelection(
            action_type=ActionType.ESCALATE_TO_HUMAN,
            confidence=0.0,
            reason="Bedrock response failed validation; escalating to human operator.",
            used_memory_ids=[],
            inspected_memory_ids=[],
            fallback_used=True,
            selector_type="bedrock",
        )


def get_action_selector(settings: Settings) -> ActionSelector:
    if settings.action_selector == "bedrock":
        from relayguard.bedrock_selector import BedrockActionSelector

        return BedrockActionSelector(
            model_id=settings.bedrock_model_id,
            region=settings.aws_region,
            min_confidence=settings.action_min_confidence,
        )
    return MockActionSelector()
