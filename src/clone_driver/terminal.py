from __future__ import annotations

import subprocess
import re
import uuid
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Protocol

from .ledger import JsonlLedger


@dataclass(frozen=True)
class Readiness:
    idle: bool
    evidence: str
    canonical_target: str


@dataclass(frozen=True)
class CaptureResult:
    status: str
    transcript: str
    canonical_target: str
    error: str = ""


@dataclass(frozen=True)
class InjectionResult:
    status: str
    enter_sent: bool
    readback_status: str
    canonical_target: str


@dataclass(frozen=True)
class KeyInjectionResult:
    status: str
    enter_sent: bool
    readback_status: str
    canonical_target: str


class TerminalBroker(Protocol):
    def capture(self, session: str) -> CaptureResult:
        ...

    def readiness(self, session: str) -> Readiness:
        ...

    def is_idle(self, session: str) -> bool:
        ...

    def send(self, session: str, message: str) -> InjectionResult:
        ...

    def send_keys(self, session: str, keys: list[str]) -> KeyInjectionResult:
        ...


@dataclass
class FakeTerminalBroker:
    idle: bool = True
    transcript: str = ""
    sent: list[tuple[str, str]] = field(default_factory=list)

    def capture(self, session: str) -> CaptureResult:
        return CaptureResult(
            status="captured",
            transcript=self.transcript,
            canonical_target=session,
        )

    def readiness(self, session: str) -> Readiness:
        return Readiness(
            idle=self.idle,
            evidence="fake_idle" if self.idle else "missing",
            canonical_target=session,
        )

    def is_idle(self, session: str) -> bool:
        return self.readiness(session).idle

    def send(self, session: str, message: str) -> InjectionResult:
        self.sent.append((session, message))
        return InjectionResult(
            status="sent",
            enter_sent=True,
            readback_status="fake",
            canonical_target=session,
        )

    def send_keys(self, session: str, keys: list[str]) -> KeyInjectionResult:
        self.sent.append((session, " ".join(keys)))
        return KeyInjectionResult(
            status="sent",
            enter_sent="Enter" in keys,
            readback_status="key_sequence_sent",
            canonical_target=session,
        )


class TmuxTerminalBroker:
    def __init__(self, idle_marker: str = "", idle_regex: str = ""):
        self.idle_marker = idle_marker
        self.idle_regex = idle_regex

    def _canonical_target(self, session: str) -> tuple[str, str]:
        result = subprocess.run(
            ["tmux", "display-message", "-p", "-t", session, "#{pane_id}"],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode != 0:
            return session, result.stderr.strip() or "target lookup failed"
        return result.stdout.strip() or session, ""

    def capture(self, session: str) -> CaptureResult:
        canonical_target, error = self._canonical_target(session)
        if error:
            return CaptureResult(
                status="target_error",
                transcript="",
                canonical_target=canonical_target,
                error=error,
            )
        result = subprocess.run(
            ["tmux", "capture-pane", "-pt", canonical_target],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode != 0:
            return CaptureResult(
                status="capture_error",
                transcript="",
                canonical_target=canonical_target,
                error=result.stderr.strip(),
            )
        return CaptureResult(
            status="captured",
            transcript=result.stdout,
            canonical_target=canonical_target,
        )

    def readiness(self, session: str) -> Readiness:
        capture = self.capture(session)
        if capture.status != "captured":
            return Readiness(
                idle=False,
                evidence=f"{capture.status}:{capture.error}",
                canonical_target=capture.canonical_target,
            )
        if not self.idle_marker and not self.idle_regex:
            return Readiness(
                idle=False,
                evidence="missing_idle_condition",
                canonical_target=capture.canonical_target,
            )
        if self.idle_marker and self.idle_marker in capture.transcript:
            return Readiness(
                idle=True,
                evidence=f"idle_marker:{self.idle_marker}",
                canonical_target=capture.canonical_target,
            )
        if self.idle_regex:
            try:
                if re.search(self.idle_regex, capture.transcript):
                    return Readiness(
                        idle=True,
                        evidence=f"idle_regex:{self.idle_regex}",
                        canonical_target=capture.canonical_target,
                    )
            except re.error as error:
                return Readiness(
                    idle=False,
                    evidence=f"idle_regex_error:{error}",
                    canonical_target=capture.canonical_target,
                )
            return Readiness(
                idle=False,
                evidence=f"idle_regex_missing:{self.idle_regex}",
                canonical_target=capture.canonical_target,
            )
        return Readiness(
            idle=False,
            evidence=f"idle_marker_missing:{self.idle_marker}",
            canonical_target=capture.canonical_target,
        )

    def is_idle(self, session: str) -> bool:
        return self.readiness(session).idle

    def send(self, session: str, message: str) -> InjectionResult:
        canonical_target, error = self._canonical_target(session)
        if error:
            return InjectionResult(
                status="tmux_error",
                enter_sent=False,
                readback_status="error",
                canonical_target=canonical_target,
            )

        buffer_name = f"clone-driver-input-{uuid.uuid4().hex}"
        try:
            subprocess.run(
                ["tmux", "load-buffer", "-b", buffer_name, "-"],
                input=message,
                check=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                ["tmux", "paste-buffer", "-b", buffer_name, "-t", canonical_target],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            captured = subprocess.run(
                ["tmux", "capture-pane", "-pt", canonical_target],
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if captured.returncode != 0:
                return InjectionResult(
                    status="tmux_error",
                    enter_sent=False,
                    readback_status="error",
                    canonical_target=canonical_target,
                )
            if message not in captured.stdout:
                return InjectionResult(
                    status="readback_failed",
                    enter_sent=False,
                    readback_status="missing",
                    canonical_target=canonical_target,
                )
            subprocess.run(
                ["tmux", "send-keys", "-t", canonical_target, "Enter"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            return InjectionResult(
                status="sent",
                enter_sent=True,
                readback_status="matched",
                canonical_target=canonical_target,
            )
        except subprocess.CalledProcessError:
            return InjectionResult(
                status="tmux_error",
                enter_sent=False,
                readback_status="error",
                canonical_target=canonical_target,
            )
        finally:
            subprocess.run(
                ["tmux", "delete-buffer", "-b", buffer_name],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

    def send_keys(self, session: str, keys: list[str]) -> KeyInjectionResult:
        canonical_target, error = self._canonical_target(session)
        if error:
            return KeyInjectionResult(
                status="tmux_error",
                enter_sent=False,
                readback_status="error",
                canonical_target=canonical_target,
            )
        if "Enter" not in keys:
            try:
                subprocess.run(
                    ["tmux", "send-keys", "-t", canonical_target, *keys],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
            except subprocess.CalledProcessError:
                return KeyInjectionResult(
                    status="tmux_error",
                    enter_sent=False,
                    readback_status="error",
                    canonical_target=canonical_target,
                )
            return KeyInjectionResult(
                status="sent",
                enter_sent=False,
                readback_status="key_sequence_sent",
                canonical_target=canonical_target,
            )

        enter_index = keys.index("Enter")
        before_enter = keys[:enter_index]
        if not before_enter:
            return KeyInjectionResult(
                status="readback_failed",
                enter_sent=False,
                readback_status="missing",
                canonical_target=canonical_target,
            )

        try:
            before = subprocess.run(
                ["tmux", "capture-pane", "-pt", canonical_target],
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if before.returncode != 0:
                return KeyInjectionResult(
                    status="tmux_error",
                    enter_sent=False,
                    readback_status="error",
                    canonical_target=canonical_target,
                )
            subprocess.run(
                ["tmux", "send-keys", "-t", canonical_target, *before_enter],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            after = subprocess.run(
                ["tmux", "capture-pane", "-pt", canonical_target],
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if after.returncode != 0:
                return KeyInjectionResult(
                    status="tmux_error",
                    enter_sent=False,
                    readback_status="error",
                    canonical_target=canonical_target,
                )
            if after.stdout == before.stdout:
                return KeyInjectionResult(
                    status="readback_failed",
                    enter_sent=False,
                    readback_status="missing",
                    canonical_target=canonical_target,
                )
            subprocess.run(
                ["tmux", "send-keys", "-t", canonical_target, "Enter"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except subprocess.CalledProcessError:
            return KeyInjectionResult(
                status="tmux_error",
                enter_sent=False,
                readback_status="error",
                canonical_target=canonical_target,
            )
        return KeyInjectionResult(
            status="sent",
            enter_sent="Enter" in keys,
            readback_status="key_sequence_sent",
            canonical_target=canonical_target,
        )


@dataclass
class NudgeRunner:
    terminal: TerminalBroker
    ledger: JsonlLedger

    def run(self, session: str, message: str, *, event: str = "nudge") -> dict[str, object]:
        readiness = self.terminal.readiness(session)
        base = {
            "target": session,
            "canonical_target": readiness.canonical_target,
            "readiness_evidence": readiness.evidence,
            "message_hash": sha256(message.encode("utf-8")).hexdigest(),
        }
        if not readiness.idle:
            result = {
                **base,
                "status": "not_idle",
                "readback_status": "not_attempted",
                "enter_sent": False,
            }
            self.ledger.write(event, result)
            return result
        injection = self.terminal.send(readiness.canonical_target, message)
        result = {
            **base,
            "status": injection.status,
            "canonical_target": injection.canonical_target,
            "readback_status": injection.readback_status,
            "enter_sent": injection.enter_sent,
        }
        self.ledger.write(event, result)
        return result
