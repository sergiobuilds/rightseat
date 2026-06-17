from __future__ import annotations

import hashlib
import os
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .ledger import read_jsonl_records
from .run_control import read_control_state


@dataclass(frozen=True)
class TargetCandidate:
    pane_id: str
    pane_ref: str
    command: str
    title: str
    preview: str
    fingerprint: str
    locked: bool


@dataclass(frozen=True)
class RunPaths:
    run_id: str
    ledger_path: Path
    control_path: Path
    lock_root: Path


@dataclass(frozen=True)
class RightSeatSession:
    run_id: str
    worker_target: str
    advisor_target: str
    ledger_path: Path
    control_path: Path
    mode: str
    active: bool


@dataclass(frozen=True)
class TmuxPaneLocation:
    session_name: str
    window_index: str
    pane_id: str


def fingerprint_transcript(text: str) -> str:
    normalized = "\n".join(line.rstrip() for line in text.splitlines()[-40:])
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def _safe_run_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-")
    return cleaned or f"run-{int(time.time())}"


def _lock_name(pane_id: str) -> str:
    return pane_id.replace("%", "pane-") + ".lock"


def default_run_paths(run_id: str) -> RunPaths:
    safe = _safe_run_id(run_id)
    root = Path("runtime") / "attach-runs" / safe
    return RunPaths(
        run_id=safe,
        ledger_path=root / "ledger.jsonl",
        control_path=root / "control.json",
        lock_root=Path("runtime") / "attach-locks",
    )


def list_tmux_targets(lock_root: Path | None = None) -> list[TargetCandidate]:
    root = lock_root or Path("runtime") / "attach-locks"
    active_advisor_targets = {
        session.advisor_target for session in list_rightseat_sessions() if session.advisor_target
    }
    result = subprocess.run(
        [
            "tmux",
            "list-panes",
            "-a",
            "-F",
            "#{pane_id}\t#{session_name}:#{window_index}.#{pane_index}\t#{pane_current_command}\t#{pane_title}",
        ],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        return []

    candidates: list[TargetCandidate] = []
    for line in result.stdout.splitlines():
        pane_id, pane_ref, command, title = (line.split("\t") + ["", "", "", ""])[:4]
        if pane_id in active_advisor_targets:
            continue
        captured = subprocess.run(
            ["tmux", "capture-pane", "-pt", pane_id],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        preview = "\n".join(captured.stdout.splitlines()[-5:]) if captured.returncode == 0 else ""
        if _is_rightseat_seat_pane(command=command, title=title, preview=preview):
            continue
        if _is_reserved_channel_pane(pane_ref=pane_ref, command=command, title=title):
            continue
        candidates.append(
            TargetCandidate(
                pane_id=pane_id,
                pane_ref=pane_ref,
                command=command,
                title=title,
                preview=preview,
                fingerprint=fingerprint_transcript(preview),
                locked=(root / _lock_name(pane_id)).exists(),
            )
        )
    return candidates


def _is_rightseat_seat_pane(*, command: str, title: str, preview: str) -> bool:
    normalized = " ".join(preview.split())
    return (
        title.strip() == "RightSeat"
        or "RightSeat ON" in preview
        or "off: rightseat off" in preview
        or "RightSeat finished" in preview
        or (command == "bash" and "worker:" in normalized and "state:" in normalized)
    )


def _is_reserved_channel_pane(*, pane_ref: str, command: str, title: str) -> bool:
    session_name = pane_ref.split(":", 1)[0].strip().lower()
    title_text = title.strip().lower()
    command_text = command.strip().lower()
    reserved_sessions = {
        "agent-discord",
        "agent-slack",
        "service-discord",
        "service-slack",
        "channel-discord",
        "channel-slack",
    }
    if session_name in reserved_sessions:
        return True
    if session_name.startswith("claude-") and (
        "discord" in session_name or "slack" in session_name or "channel" in session_name
    ):
        return True
    if session_name.startswith("channel-"):
        return True
    return command_text == "claude" and "channel" in title_text


def canonical_tmux_target(target: str) -> str:
    result = subprocess.run(
        ["tmux", "display-message", "-p", "-t", target, "#{pane_id}"],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        return target
    return result.stdout.strip() or target


def tmux_pane_location(target: str) -> TmuxPaneLocation | None:
    result = subprocess.run(
        [
            "tmux",
            "display-message",
            "-p",
            "-t",
            target,
            "#{session_name}\t#{window_index}\t#{pane_id}",
        ],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        return None
    session_name, window_index, pane_id = (result.stdout.strip().split("\t") + ["", "", ""])[:3]
    if not session_name or not window_index:
        return None
    return TmuxPaneLocation(
        session_name=session_name,
        window_index=window_index,
        pane_id=pane_id or target,
    )


def show_tmux_pane(target: str) -> bool:
    location = tmux_pane_location(target)
    if location is None:
        return False
    tmux_target = f"{location.session_name}:{location.window_index}"
    if os.environ.get("TMUX"):
        switch = subprocess.run(
            ["tmux", "switch-client", "-t", tmux_target],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        select = subprocess.run(
            ["tmux", "select-pane", "-t", location.pane_id],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return switch.returncode == 0 and select.returncode == 0
    attached = subprocess.run(
        ["tmux", "attach-session", "-t", tmux_target],
        check=False,
        text=True,
    )
    return attached.returncode == 0


def tmux_pane_exists(pane_id: str) -> bool:
    if not pane_id:
        return False
    result = subprocess.run(
        ["tmux", "display-message", "-p", "-t", pane_id, "#{pane_id}"],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.returncode == 0 and bool(result.stdout.strip())


def kill_rightseat_pane(pane_id: str) -> bool:
    if not pane_id:
        return False
    result = subprocess.run(
        ["tmux", "kill-pane", "-t", pane_id],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.returncode == 0


def _last_pair_started(records: list[dict[str, Any]]) -> dict[str, Any] | None:
    for record in reversed(records):
        if record.get("event") == "pair_started":
            return record
    return None


def list_rightseat_sessions(
    runtime_root: Path | str = Path("runtime") / "attach-runs",
    *,
    active_only: bool = True,
) -> list[RightSeatSession]:
    root = Path(runtime_root)
    if not root.exists():
        return []

    sessions: list[RightSeatSession] = []
    for ledger_path in sorted(root.glob("*/ledger.jsonl")):
        records = read_jsonl_records(ledger_path)
        pair = _last_pair_started(records)
        if pair is None:
            continue
        run_id = str(pair.get("run_id") or ledger_path.parent.name)
        worker_target = str(pair.get("worker_target", ""))
        advisor_target = str(pair.get("advisor_target", ""))
        control_path = ledger_path.parent / "control.json"
        mode = read_control_state(control_path).mode
        active = tmux_pane_exists(advisor_target)
        if active_only and not active:
            continue
        sessions.append(
            RightSeatSession(
                run_id=run_id,
                worker_target=worker_target,
                advisor_target=advisor_target,
                ledger_path=ledger_path,
                control_path=control_path,
                mode=mode,
                active=active,
            )
        )
    return sessions


class TargetLock:
    def __init__(self, lock_root: Path, pane_id: str, run_id: str):
        self.lock_root = lock_root
        self.pane_id = pane_id
        self.run_id = run_id
        self.path = lock_root / _lock_name(pane_id)

    def acquire(self, *, steal: bool = False) -> bool:
        self.lock_root.mkdir(parents=True, exist_ok=True)
        if steal and self.path.exists():
            self.path.unlink()
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            return False
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(self.run_id + "\n")
        return True

    def release(self) -> None:
        try:
            if self.path.read_text(encoding="utf-8").strip() == self.run_id:
                self.path.unlink()
        except OSError:
            return
        try:
            self.lock_root.rmdir()
        except OSError:
            return
