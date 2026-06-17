from __future__ import annotations

from dataclasses import dataclass

from .verifier import Verdict


@dataclass(frozen=True)
class DriverAction:
    status: str
    message: str


def decide_next_input(verdict: Verdict) -> DriverAction:
    if verdict.status == "PASS":
        return DriverAction(status="hold", message="")
    if verdict.status == "FAIL":
        return DriverAction(
            status="inject",
            message=(
                "외부 검증 실패입니다. worker 자기평가를 믿지 말고 "
                f"이 문제를 고치세요: {verdict.reason}"
            ),
        )
    if verdict.status == "ESCALATE":
        return DriverAction(status="escalate", message=verdict.reason)
    return DriverAction(status="stop", message="")
