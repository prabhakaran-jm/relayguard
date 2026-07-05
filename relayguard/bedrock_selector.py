"""Amazon Bedrock Runtime integration for guarded action selection."""

from __future__ import annotations

import json
from typing import Any

from relayguard.action_selector import (
    ActionSelection,
    ActionSelectorContext,
    build_action_prompt,
    parse_bedrock_response,
)


class BedrockActionSelector:
    selector_type = "bedrock"

    def __init__(
        self,
        model_id: str,
        region: str,
        *,
        min_confidence: float = 0.5,
        client: Any | None = None,
    ) -> None:
        self.model_id = model_id
        self.region = region
        self.min_confidence = min_confidence
        self._client = client

    def select_action(self, context: ActionSelectorContext) -> ActionSelection:
        prompt = build_action_prompt(context)
        raw = self._invoke(prompt)
        return parse_bedrock_response(raw, min_confidence=self.min_confidence)

    def _invoke(self, prompt: str) -> str:
        client = self._client or self._build_client()
        response = client.converse(
            modelId=self.model_id,
            messages=[
                {
                    "role": "user",
                    "content": [{"text": prompt}],
                }
            ],
            inferenceConfig={"maxTokens": 512, "temperature": 0},
        )
        content = response["output"]["message"]["content"]
        for block in content:
            if "text" in block:
                return block["text"]
        return json.dumps({})

    def _build_client(self) -> Any:
        import boto3

        return boto3.client("bedrock-runtime", region_name=self.region)
