from __future__ import annotations

import shlex
import sys
from dataclasses import dataclass


VALID_BACKENDS = {"codex", "claude", "fake", "custom"}


@dataclass(frozen=True)
class AdvisorBackend:
    name: str
    command: list[str]
    model: str
    effort: str
    source: str


def build_advisor_backend(
    *,
    backend: str,
    model: str = "",
    effort: str = "",
    custom_command: str = "",
) -> AdvisorBackend:
    if backend not in VALID_BACKENDS:
        raise ValueError(f"unsupported backend: {backend}")
    if backend == "custom":
        command = shlex.split(custom_command)
        if not command:
            raise ValueError("--advisor-cmd is required when --backend custom")
        if model or effort:
            raise ValueError(
                "custom backend receives settings through --advisor-cmd, "
                "not --advisor-model or --advisor-effort"
            )
        return AdvisorBackend(
            name="custom",
            command=command,
            model="",
            effort="",
            source="custom_command",
        )
    if backend == "fake":
        if model or effort:
            raise ValueError("fake backend does not accept --advisor-model or --advisor-effort")
        return AdvisorBackend(
            name="fake",
            command=[sys.executable, "-m", "clone_driver.fake_advisor"],
            model="",
            effort="",
            source="builtin",
        )

    module = "clone_driver.codex_advisor" if backend == "codex" else "clone_driver.claude_advisor"
    command = [sys.executable, "-m", module]
    if model:
        command.extend(["--model", model])
    if effort:
        command.extend(["--effort", effort])
    return AdvisorBackend(
        name=backend,
        command=command,
        model=model,
        effort=effort,
        source="builtin",
    )
