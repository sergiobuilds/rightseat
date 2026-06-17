from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TaskContract:
    seed: str
    wiw: str
    not_to_do: str
    final_artifact: str
    hashes: dict[str, str]


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
    )
