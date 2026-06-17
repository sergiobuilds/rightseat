from __future__ import annotations

import re
from dataclasses import dataclass


SAFE_NAMED_KEYS = {
    "Up",
    "Down",
    "Left",
    "Right",
    "Space",
    "Tab",
    "BTab",
    "Enter",
    "Escape",
    "C-c",
    "C-d",
}
SAFE_SINGLE_KEY = re.compile(r"^[A-Za-z0-9]$")


@dataclass(frozen=True)
class InputAction:
    mode: str
    text: str
    keys: list[str]
    choice_label: str
    source: str

    @classmethod
    def from_parts(
        cls,
        *,
        mode: str,
        text: str,
        keys: list[str],
        choice_label: str,
        source: str,
    ) -> "InputAction":
        if mode not in {"text", "keys"}:
            raise ValueError(f"unsupported input mode: {mode}")
        if source not in {"quick_reply", "llm", "manual"}:
            raise ValueError(f"unsupported input source: {source}")
        if mode == "text":
            if not text.strip():
                raise ValueError("text input action requires text")
            return cls(
                mode=mode,
                text=text,
                keys=[],
                choice_label=choice_label,
                source=source,
            )
        if not keys:
            raise ValueError("key input action requires at least one key")
        unsafe = [
            key
            for key in keys
            if key not in SAFE_NAMED_KEYS and not SAFE_SINGLE_KEY.match(key)
        ]
        if unsafe:
            raise ValueError(f"unsafe tmux keys: {unsafe}")
        return cls(
            mode=mode,
            text="",
            keys=keys,
            choice_label=choice_label,
            source=source,
        )
