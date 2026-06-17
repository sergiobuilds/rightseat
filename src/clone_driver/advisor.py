from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass, field
from typing import Any


VALID_ACTIONS = {"ANSWER", "WAIT", "TYPE", "SUBMIT", "KEYS", "ESCALATE"}
VALID_CONFIDENCE = {"high", "medium", "low"}


@dataclass(frozen=True)
class AdvisorRequest:
    question: str
    screen_tail: str
    profile: str
    answer_policy: str
    turn_index: int
    screen_state: str = ""
    current_input: str = ""
    screen_adapter: str = ""
    seed: str = ""
    wiw: str = ""
    not_to_do: str = ""
    final_artifact: str = ""
    contract_hashes: dict[str, str] = field(default_factory=dict)
    redacted_screen_hash: str = ""
    redaction_count: int = 0

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, sort_keys=True)


@dataclass(frozen=True)
class AdvisorResponse:
    action: str
    answer: str
    reason: str
    confidence: str
    input_mode: str = "text"
    keys: list[str] | None = None
    choice_label: str = ""
    answer_source: str = "llm"

    @classmethod
    def from_json(cls, text: str) -> "AdvisorResponse":
        data: dict[str, Any] = json.loads(text)
        action = str(data.get("action", ""))
        answer = str(data.get("answer", data.get("text", "")))
        reason = str(data.get("reason", ""))
        confidence = str(data.get("confidence", ""))
        if action == "SUBMIT":
            input_mode = "keys"
        elif action == "KEYS":
            input_mode = "keys"
        else:
            input_mode = str(data.get("input_mode", "text") or "text")
        keys = data.get("keys", [])
        if action == "SUBMIT" and not keys:
            keys = ["Enter"]
        if not isinstance(keys, list):
            raise ValueError("advisor keys must be a list")
        keys = [str(key) for key in keys]
        choice_label = str(data.get("choice_label", ""))
        answer_source = str(data.get("answer_source", "llm") or "llm")

        if action not in VALID_ACTIONS:
            raise ValueError(f"invalid advisor action: {action}")
        if confidence not in VALID_CONFIDENCE:
            raise ValueError(f"invalid advisor confidence: {confidence}")
        if input_mode not in {"text", "keys"}:
            raise ValueError(f"invalid input mode: {input_mode}")
        if answer_source not in {"llm", "quick_reply", "manual"}:
            answer_source = "llm"
        if action in {"ANSWER", "TYPE"} and input_mode == "text" and not answer.strip():
            raise ValueError(f"text {action} requires a non-empty answer")
        if action in {"ANSWER", "KEYS", "SUBMIT"} and input_mode == "keys" and not keys:
            raise ValueError(f"key {action} requires keys")
        if not reason.strip():
            raise ValueError("advisor reason is required")

        return cls(
            action=action,
            answer=answer,
            reason=reason,
            confidence=confidence,
            input_mode=input_mode,
            keys=keys,
            choice_label=choice_label,
            answer_source=answer_source,
        )


class ExternalAdvisor:
    def __init__(self, command: list[str]):
        self.command = command

    def ask(
        self,
        request: AdvisorRequest,
        *,
        timeout_seconds: float | None = None,
    ) -> AdvisorResponse:
        try:
            result = subprocess.run(
                self.command,
                input=request.to_json(),
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as error:
            raise TimeoutError("advisor command timed out") from error
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "advisor command failed")
        return AdvisorResponse.from_json(result.stdout)
