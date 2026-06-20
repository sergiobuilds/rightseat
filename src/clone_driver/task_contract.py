from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path


_AC_HEADER_RE = re.compile(
    r"^#{1,6}\s+.*(?:합격\s*기준|acceptance\s+criteria)", re.IGNORECASE
)
_HEADER_RE = re.compile(r"^#{1,6}\s+")
_AC_BULLET_RE = re.compile(r"^\s*[-*]\s+(?:\[[ xX]\]\s+)?(.+?)\s*$")


@dataclass(frozen=True)
class TaskContract:
    seed: str
    wiw: str
    not_to_do: str
    final_artifact: str
    hashes: dict[str, str]
    acceptance_criteria: list[str] = field(default_factory=list)


def parse_acceptance_criteria(seed_text: str) -> list[str]:
    """Extract the measurable checklist under a '합격 기준'/'Acceptance Criteria'
    heading. Bullets only (- / *), optional [ ]/[x] checkbox. Stops at next heading.
    These are criteria to match evidence against, not a judgment to make."""
    in_section = False
    out: list[str] = []
    for line in seed_text.splitlines():
        if _AC_HEADER_RE.match(line):
            in_section = True
            continue
        if in_section and _HEADER_RE.match(line):
            break
        if in_section:
            bullet = _AC_BULLET_RE.match(line)
            if bullet:
                out.append(bullet.group(1).strip())
    return out


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_task_contract(
    seed_path: Path,
    wiw_path: Path,
    not_to_do_path: Path,
    final_artifact_path: Path,
) -> TaskContract:
    seed = _read(seed_path)
    wiw = _read(wiw_path)
    not_to_do = _read(not_to_do_path)
    final_artifact = _read(final_artifact_path)
    return TaskContract(
        seed=seed,
        wiw=wiw,
        not_to_do=not_to_do,
        final_artifact=final_artifact,
        hashes={
            "seed": _hash(seed),
            "wiw": _hash(wiw),
            "not_to_do": _hash(not_to_do),
            "final_artifact": _hash(final_artifact),
        },
        acceptance_criteria=parse_acceptance_criteria(seed),
    )
