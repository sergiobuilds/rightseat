from __future__ import annotations

import shlex
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .ledger import JsonlLedger


@dataclass(frozen=True)
class PairConfig:
    target: str
    run_id: str
    ledger_path: Path
    advisor_transcript_path: Path
    attach_args: list[str] = field(default_factory=list)
    split_direction: str = "-h"
    python_executable: str = sys.executable
    keepalive_seconds: int = 3600


@dataclass(frozen=True)
class PairLaunchResult:
    status: str
    worker_target: str
    advisor_target: str
    run_id: str
    ledger_path: Path
    command: str = ""
    error: str = ""


class PairLauncher:
    def __init__(self, config: PairConfig):
        self.config = config
        self.ledger = JsonlLedger(config.ledger_path)

    def _canonical_target(self) -> tuple[str, str]:
        result = subprocess.run(
            ["tmux", "display-message", "-p", "-t", self.config.target, "#{pane_id}"],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode != 0:
            return self.config.target, result.stderr.strip() or "target lookup failed"
        return result.stdout.strip() or self.config.target, ""

    def _attach_command(self, worker_target: str) -> list[str]:
        return [
            self.config.python_executable,
            "-m",
            "clone_driver",
            "attach",
            "--target",
            worker_target,
            "--run-id",
            self.config.run_id,
            "--ledger",
            str(self.config.ledger_path),
            "--advisor-display",
            "inline",
            "--advisor-transcript",
            str(self.config.advisor_transcript_path),
            *self.config.attach_args,
        ]

    def _advisor_shell_command(self, worker_target: str) -> str:
        attach = shlex.join(self._attach_command(worker_target))
        source_root = Path(__file__).resolve().parents[1]
        header = [
            f"export PYTHONPATH={shlex.quote(str(source_root))}${{PYTHONPATH:+:$PYTHONPATH}}",
            "printf '%s\\n' 'RightSeat ON'",
            "printf '\\n'",
            f"printf '%s\\n' 'worker: {worker_target}'",
            "printf '%s\\n' 'state: starting'",
            "printf '%s\\n' 'last: none'",
            "printf '\\n'",
            "printf '%s\\n' 'off: rightseat off'",
            "printf '%s\\n' 'pause: rightseat pause'",
            "printf '%s\\n' 'resume: rightseat resume'",
            "printf '\\n'",
            "printf '\\n'",
            attach,
            "status=$?",
            "printf '\\n%s\\n' 'RightSeat ON'",
            f"printf '%s\\n' 'worker: {worker_target}'",
            f"printf '%s\\n' \"state: finished status=$status\"",
            f"sleep {int(self.config.keepalive_seconds)}",
            "exit $status",
        ]
        return " ; ".join(header)

    def launch(self) -> PairLaunchResult:
        worker_target, error = self._canonical_target()
        if error:
            self.ledger.write(
                "pair_target_error",
                {
                    "target": self.config.target,
                    "worker_target": worker_target,
                    "run_id": self.config.run_id,
                    "error": error,
                },
            )
            return PairLaunchResult(
                status="target_error",
                worker_target=worker_target,
                advisor_target="",
                run_id=self.config.run_id,
                ledger_path=self.config.ledger_path,
                error=error,
            )

        shell_command = self._advisor_shell_command(worker_target)
        result = subprocess.run(
            [
                "tmux",
                "split-window",
                self.config.split_direction,
                "-t",
                worker_target,
                "-P",
                "-F",
                "#{pane_id}",
                shell_command,
            ],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode != 0:
            error = result.stderr.strip() or "RightSeat pane launch failed"
            self.ledger.write(
                "pair_launch_error",
                {
                    "target": self.config.target,
                    "worker_target": worker_target,
                    "run_id": self.config.run_id,
                    "error": error,
                },
            )
            return PairLaunchResult(
                status="launch_error",
                worker_target=worker_target,
                advisor_target="",
                run_id=self.config.run_id,
                ledger_path=self.config.ledger_path,
                command=shell_command,
                error=error,
            )

        advisor_target = result.stdout.strip()
        self.ledger.write(
            "pair_started",
            {
                "target": self.config.target,
                "worker_target": worker_target,
                "advisor_target": advisor_target,
                "run_id": self.config.run_id,
                "ledger": str(self.config.ledger_path),
                "advisor_transcript": str(self.config.advisor_transcript_path),
                "command": shell_command,
            },
        )
        return PairLaunchResult(
            status="started",
            worker_target=worker_target,
            advisor_target=advisor_target,
            run_id=self.config.run_id,
            ledger_path=self.config.ledger_path,
            command=shell_command,
        )
