from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Verdict:
    status: str
    reason: str


class ExternalVerifier:
    def __init__(self, command: list[str]):
        self.command = command

    def verify(self, packet_path: Path) -> Verdict:
        packet_text = packet_path.read_text(encoding="utf-8")
        result = subprocess.run(
            self.command,
            input=packet_text,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "verifier command failed")
        data = json.loads(result.stdout)
        status = data.get("status")
        reason = data.get("reason", "")
        if status not in {"PASS", "FAIL", "ESCALATE"}:
            raise ValueError(f"invalid verifier status: {status}")
        return Verdict(status=status, reason=reason)
