from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass
from typing import Callable, Sequence


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class SessionTarget:
    session: str
    target: str
    canonical_target: str


@dataclass(frozen=True)
class ProbeResult:
    target: str
    canonical_target: str
    available: bool
    stdout: str
    stderr: str


def default_run_command(args: Sequence[str], **kwargs) -> CommandResult:
    result = subprocess.run(
        list(args),
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        **kwargs,
    )
    return CommandResult(result.returncode, result.stdout, result.stderr)


class TmuxSessionManager:
    def __init__(self, run_command: Callable[..., CommandResult] = default_run_command):
        self.run_command = run_command

    def start(self, *, session: str, command: list[str]) -> SessionTarget:
        if not command:
            raise ValueError("worker command is required")
        result = self.run_command(["tmux", "new-session", "-d", "-s", session, shlex.join(command)])
        if result.returncode != 0:
            raise RuntimeError(result.stderr or "tmux new-session failed")
        target = self.run_command(
            ["tmux", "display-message", "-p", "-t", session, "#{pane_id}"]
        )
        if target.returncode != 0:
            raise RuntimeError(target.stderr or "tmux target lookup failed")
        canonical_target = target.stdout.strip() or session
        return SessionTarget(
            session=session,
            target=canonical_target,
            canonical_target=canonical_target,
        )

    def probe(self, *, target: str) -> ProbeResult:
        identity = self.run_command(
            ["tmux", "display-message", "-p", "-t", target, "#{pane_id}"]
        )
        if identity.returncode != 0:
            return ProbeResult(
                target=target,
                canonical_target="",
                available=False,
                stdout=identity.stdout,
                stderr=identity.stderr,
            )
        canonical_target = identity.stdout.strip() or target
        result = self.run_command(["tmux", "capture-pane", "-pt", canonical_target])
        return ProbeResult(
            target=target,
            canonical_target=canonical_target,
            available=result.returncode == 0,
            stdout=result.stdout,
            stderr=result.stderr,
        )
