from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CompletionResult:
    passed: bool
    all_passed: bool
    pass_rate: float
    reason: str


def verify_completion(
    *,
    ac_results: list[bool],
    exit_code: int | None,
    regressed: bool,
) -> CompletionResult:
    """Deterministic completion verdict. Worker claims are not inputs."""
    total = len(ac_results)
    passed_count = sum(1 for item in ac_results if item)
    all_passed = total > 0 and passed_count == total
    pass_rate = passed_count / total if total else 0.0

    if total == 0:
        return CompletionResult(False, False, 0.0, "no acceptance criteria")
    if exit_code is None:
        return CompletionResult(False, all_passed, pass_rate, "no runtime evidence")
    if regressed:
        return CompletionResult(False, all_passed, pass_rate, "regression detected")
    if not all_passed:
        return CompletionResult(False, all_passed, pass_rate, "not all acceptance criteria passed")
    if exit_code != 0:
        return CompletionResult(False, all_passed, pass_rate, f"runtime exit_code={exit_code}")
    return CompletionResult(True, True, pass_rate, "all AC passed with runtime evidence")
