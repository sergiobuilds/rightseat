from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .artifacts import ArtifactCollector
from .completion_check import verify_completion
from .decision import decide_next_input
from .packet import PacketBuilder
from .verifier import ExternalVerifier, Verdict


@dataclass(frozen=True)
class GateOutcome:
    verdict: str  # complete / inject / escalate
    message: str
    verifier_status: str  # PASS / FAIL / ESCALATE / skipped
    exit_code: int | None
    reason: str


def _read_exit_code(manifest_path: Path) -> int | None:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    value = data.get("test_exit_code")
    return value if isinstance(value, int) else None


def run_completion_gate(
    *,
    seed_path: Path,
    wiw_path: Path,
    not_to_do_path: Path,
    final_artifact_path: Path,
    acceptance_criteria: list[str],
    workdir: Path,
    test_cmd: list[str],
    out_dir: Path,
    verifier: ExternalVerifier,
    regressed: bool = False,
    collector: ArtifactCollector | None = None,
    packet_builder: PacketBuilder | None = None,
) -> GateOutcome:
    """Worker가 done을 주장할 때 도는 결정론 완료 게이트.

    대조(verifier)와 산수(completion_check)만 한다. 판단하지 않는다.
    worker의 자기평가는 입력이 아니다. 게이트 자리는 attach 루프 밖이라
    worker가 채점자를 볼 수 없다.
    """
    if not acceptance_criteria:
        return GateOutcome(
            "escalate",
            "seed에 합격 기준(rubric)이 없어 정합성을 잴 수 없음",
            "skipped",
            None,
            "no acceptance criteria",
        )

    collector = collector or ArtifactCollector()
    packet_builder = packet_builder or PacketBuilder()

    manifest_path = collector.collect(
        workdir=workdir, out_dir=out_dir, test_cmd=test_cmd
    )
    exit_code = _read_exit_code(manifest_path)

    # 1차 결정론 게이트: 런타임 증거가 없으면 비싼 외부 대조를 건너뛴다.
    if exit_code is None or exit_code != 0 or regressed:
        completion = verify_completion(
            ac_results=[False], exit_code=exit_code, regressed=regressed
        )
        action = decide_next_input(Verdict("FAIL", completion.reason))
        return GateOutcome(
            "inject", action.message, "skipped", exit_code, completion.reason
        )

    # 2차 외부 대조: seed 합격 기준에 증거를 대조한다(대조만, 판단 아님).
    packet = packet_builder.build(
        seed=seed_path,
        wiw=wiw_path,
        not_to_do=not_to_do_path,
        final_artifact=final_artifact_path,
        artifact_manifest=manifest_path,
    )
    packet_path = out_dir / "packet.json"
    packet_builder.write(packet, packet_path)
    verdict = verifier.verify(packet_path)

    if verdict.status == "ESCALATE":
        return GateOutcome(
            "escalate", verdict.reason, "ESCALATE", exit_code, verdict.reason
        )

    # 종합 결정론 판정: 대조 통과 + 런타임 증거.
    completion = verify_completion(
        ac_results=[verdict.status == "PASS"], exit_code=exit_code, regressed=regressed
    )
    if completion.passed:
        return GateOutcome(
            "complete",
            "합격 기준 충족 + 런타임 증거",
            "PASS",
            exit_code,
            completion.reason,
        )
    action = decide_next_input(Verdict("FAIL", verdict.reason or completion.reason))
    return GateOutcome("inject", action.message, verdict.status, exit_code, verdict.reason)
