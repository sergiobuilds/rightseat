from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass


DEFAULT_REDACTION_PATTERNS = [
    r"(?i)\b(api[_-]?key|token|secret)\s*=\s*[^ \n]+",
    r"sk-[A-Za-z0-9_-]{10,}",
]


@dataclass(frozen=True)
class RedactedScreen:
    text: str
    count: int
    hash: str


def redact_screen(text: str, patterns: list[str] | None = None) -> RedactedScreen:
    count = 0
    redacted = text
    for pattern in patterns or DEFAULT_REDACTION_PATTERNS:
        redacted, replaced = re.subn(pattern, "[REDACTED]", redacted)
        count += replaced
    return RedactedScreen(
        text=redacted,
        count=count,
        hash=hashlib.sha256(redacted.encode("utf-8")).hexdigest(),
    )
