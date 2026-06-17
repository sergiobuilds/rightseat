from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class JsonlLedger:
    def __init__(self, path: Path):
        self.path = path

    def write(self, event: str, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event,
            **payload,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def read_jsonl_records(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not path.exists():
        return records
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def summarize_record(record: dict[str, Any]) -> str:
    event = record.get("event", "unknown")
    if event in {"nudge", "gate_injection"}:
        return (
            f"{event} status={record.get('status', '')} "
            f"target={record.get('target', '')} "
            f"canonical={record.get('canonical_target', '')} "
            f"readiness={record.get('readiness_evidence', '')} "
            f"readback={record.get('readback_status', '')} "
            f"enter_sent={record.get('enter_sent', '')}"
        )
    if event == "gate":
        return (
            f"gate verdict={record.get('verdict', '')} "
            f"action={record.get('action', '')} "
            f"reason={record.get('reason', '')}"
        )
    if event == "session_started":
        return (
            f"session_started session={record.get('session', '')} "
            f"target={record.get('target', '')} "
            f"canonical={record.get('canonical_target', '')}"
        )
    if event == "session_probe":
        return (
            f"session_probe target={record.get('target', '')} "
            f"canonical={record.get('canonical_target', '')} "
            f"available={record.get('available', '')}"
        )
    if event in {"invalid_verdict", "verifier_error"}:
        return f"{event} status={record.get('status', '')} error={record.get('error', '')}"
    if event == "supervise_started":
        return (
            f"supervise_started worker={record.get('worker_command', '')} "
            f"max_turns={record.get('max_turns', '')}"
        )
    if event == "advisor_turn":
        return (
            f"advisor_turn turn={record.get('turn_index', '')} "
            f"action={record.get('action', '')} "
            f"confidence={record.get('confidence', '')} "
            f"injected={record.get('injected', '')} "
            f"question={record.get('question', '')}"
        )
    if event == "advisor_escalated":
        return (
            f"advisor_escalated confidence={record.get('confidence', '')} "
            f"question={record.get('question', '')} "
            f"reason={record.get('reason', '')}"
        )
    if event == "supervise_finished":
        return (
            f"supervise_finished status={record.get('status', '')} "
            f"turns={record.get('turns', '')}"
        )
    if event == "attach_turn":
        return (
            f"attach_turn target={record.get('target', '')} "
            f"canonical={record.get('canonical_target', '')} "
            f"turn={record.get('turn_index', '')} "
            f"backend={record.get('backend', '')} "
            f"model={record.get('backend_model', '')} "
            f"effort={record.get('backend_effort', '')} "
            f"source={record.get('answer_source', '')} "
            f"input_mode={record.get('input_mode', '')} "
            f"action={record.get('action', '')} "
            f"confidence={record.get('confidence', '')} "
            f"readback={record.get('readback_status', '')} "
            f"enter_sent={record.get('enter_sent', '')} "
            f"injected={record.get('injected', '')} "
            f"question={record.get('question', '')}"
        )
    if event == "attach_finished":
        return (
            f"attach_finished target={record.get('target', '')} "
            f"status={record.get('status', '')} "
            f"turns={record.get('turns', '')}"
        )
    if event == "attach_escalated":
        return (
            f"attach_escalated target={record.get('target', '')} "
            f"canonical={record.get('canonical_target', '')} "
            f"confidence={record.get('confidence', '')} "
            f"question={record.get('question', '')} "
            f"reason={record.get('reason', '')}"
        )
    if event in {
        "attach_observed",
        "target_locked",
        "stale_screen",
        "advisor_timeout",
        "advisor_error",
        "confirm_accepted",
        "confirm_rejected",
        "confirm_timeout",
        "confirm_unavailable",
    }:
        return (
            f"{event} target={record.get('target', '')} "
            f"canonical={record.get('canonical_target', '')} "
            f"status={record.get('status', '')} "
            f"injected={record.get('injected', '')}"
        )
    return f"{event} status={record.get('status', '')}"
