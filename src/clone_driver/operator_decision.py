from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .input_action import InputAction


ALLOWED_ACTIONS = {"WAIT", "TYPE", "SUBMIT", "KEYS", "ESCALATE"}
ALLOWED_CONFIDENCE = {"high", "medium", "low"}


@dataclass(frozen=True)
class OperatorDecision:
    action: str
    text: str = ""
    keys: list[str] = field(default_factory=list)
    reason: str = ""
    confidence: str = "low"

    @property
    def executable_in_auto(self) -> bool:
        return self.confidence == "high" and self.action in {"TYPE", "SUBMIT", "KEYS"}

    def to_input_action(self) -> InputAction:
        if self.action == "TYPE":
            return InputAction.from_parts(
                mode="text",
                text=self.text,
                keys=[],
                choice_label="",
                source="llm",
            )
        if self.action == "SUBMIT":
            return InputAction.from_parts(
                mode="keys",
                text="",
                keys=["Enter"],
                choice_label="",
                source="llm",
            )
        if self.action == "KEYS":
            return InputAction.from_parts(
                mode="keys",
                text="",
                keys=self.keys,
                choice_label="",
                source="llm",
            )
        raise ValueError(f"{self.action} is not executable")


def _as_dict(value: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(value, str):
        data = json.loads(value)
    else:
        data = value
    if not isinstance(data, dict):
        raise ValueError("operator decision must be a JSON object")
    return data


def parse_operator_decision(value: str | dict[str, Any]) -> OperatorDecision:
    data = _as_dict(value)
    action = str(data.get("action", "")).upper()
    text = str(data.get("text", data.get("answer", "")) or "")
    reason = str(data.get("reason", "") or "")
    confidence = str(data.get("confidence", "") or "")
    keys_raw = data.get("keys", [])
    if not isinstance(keys_raw, list):
        raise ValueError("operator decision keys must be a list")
    keys = [str(key) for key in keys_raw]

    if action not in ALLOWED_ACTIONS:
        raise ValueError(f"invalid operator action: {action}")
    if confidence not in ALLOWED_CONFIDENCE:
        raise ValueError(f"invalid operator confidence: {confidence}")
    if not reason.strip():
        raise ValueError("operator reason is required")
    if action == "TYPE" and not text.strip():
        raise ValueError("TYPE requires non-empty text")
    if action == "KEYS" and not keys:
        raise ValueError("KEYS requires keys")
    if action in {"WAIT", "ESCALATE"}:
        text = ""
        keys = []
    if action == "SUBMIT":
        text = ""
        keys = ["Enter"]

    decision = OperatorDecision(
        action=action,
        text=text,
        keys=keys,
        reason=reason,
        confidence=confidence,
    )
    if action in {"TYPE", "SUBMIT", "KEYS"}:
        decision.to_input_action()
    return decision
