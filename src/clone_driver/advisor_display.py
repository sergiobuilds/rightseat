from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class AdvisorDisplay:
    mode: str
    transcript_path: Path
    tmux_target: str = ""

    def _write(self, event: dict[str, object]) -> str:
        self.transcript_path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(event, ensure_ascii=False, sort_keys=True)
        with self.transcript_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
        return line

    def record_status(self, **payload: object) -> None:
        event = {"event": "advisor_status", **payload}
        line = self._write(event)
        if self.mode == "inline":
            status = str(payload.get("status", ""))
            if status == "watching":
                print("RightSeat ON")
                print("")
                print(f"worker: {payload.get('target', '')}")
                print("state: watching")
                print("last: none")
                print("")
                print("off: rightseat off")
                print("pause: rightseat pause")
                print("resume: rightseat resume")
            elif status == "injection_result":
                print("RightSeat ON")
                print("")
                print(f"worker: {payload.get('target', '')}")
                print(f"state: {payload.get('prompt_class', '')}")
                print(f"result: {payload.get('message', '')}")
            elif status in {"stale_screen", "advisor_timeout", "advisor_error"}:
                print("RightSeat ON")
                print("")
                print(f"worker: {payload.get('target', '')}")
                print(f"state: {status}")
                print(f"last: {payload.get('message', '')}")
        elif self.mode == "tmux" and self.tmux_target:
            subprocess.run(
                ["tmux", "display-message", "-t", self.tmux_target, line],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

    def record_decision(self, **payload: object) -> None:
        event = {"event": "advisor_decision", **payload}
        line = self._write(event)
        if self.mode == "inline":
            prompt_class = str(payload.get("prompt_class", ""))
            input_mode = str(payload.get("input_mode", ""))
            proposed_input = str(payload.get("proposed_input", ""))
            print("RightSeat ON")
            print("")
            print(f"worker: {payload.get('target', '')}")
            print(f"state: {prompt_class}")
            print(f"action: {input_mode}")
            if proposed_input:
                print(f"input: {proposed_input}")
            print(f"reason: {payload.get('reason', '')}")
        elif self.mode == "tmux" and self.tmux_target:
            subprocess.run(
                ["tmux", "display-message", "-t", self.tmux_target, line],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
