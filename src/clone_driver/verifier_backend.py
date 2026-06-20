from __future__ import annotations

import shlex
import sys
from dataclasses import dataclass


VALID_VERIFIER_BACKENDS = {"codex", "claude", "custom"}


@dataclass(frozen=True)
class VerifierBackend:
    name: str
    command: list[str]
    model: str
    effort: str
    source: str


def build_verifier_backend(
    *,
    backend: str,
    model: str = "",
    effort: str = "",
    custom_command: str = "",
) -> VerifierBackend:
    if backend not in VALID_VERIFIER_BACKENDS:
        raise ValueError(f"unsupported verifier backend: {backend}")
    if backend == "custom":
        command = shlex.split(custom_command)
        if not command:
            raise ValueError("--verifier-cmd is required when --verifier-backend custom")
        if model or effort:
            raise ValueError(
                "custom backend receives settings through --verifier-cmd, "
                "not --verifier-model or --verifier-effort"
            )
        return VerifierBackend("custom", command, "", "", "custom_command")

    module = (
        "clone_driver.codex_verifier"
        if backend == "codex"
        else "clone_driver.claude_verifier"
    )
    command = [sys.executable, "-m", module]
    if model:
        command.extend(["--model", model])
    if effort:
        command.extend(["--effort", effort])
    return VerifierBackend(backend, command, model, effort, "builtin")
