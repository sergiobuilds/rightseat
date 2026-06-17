from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


VALID_MODES = {"auto", "confirm", "suggest", "paused"}


@dataclass(frozen=True)
class ControlState:
    mode: str


def read_control_state(path: Path) -> ControlState:
    if not path.exists():
        return ControlState(mode="auto")
    data = json.loads(path.read_text(encoding="utf-8"))
    mode = str(data.get("mode", "auto"))
    if mode not in VALID_MODES:
        return ControlState(mode="paused")
    return ControlState(mode=mode)


def write_control_state(path: Path, *, mode: str) -> None:
    if mode not in VALID_MODES:
        raise ValueError(f"invalid control mode: {mode}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"mode": mode}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
