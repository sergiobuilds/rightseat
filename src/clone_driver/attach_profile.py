from __future__ import annotations

import hashlib
import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AttachProfile:
    values: dict[str, object]
    config_hash: str


def load_attach_profile(path: Path) -> AttachProfile:
    raw = path.read_bytes()
    values = tomllib.loads(raw.decode("utf-8"))
    return AttachProfile(
        values=values,
        config_hash=hashlib.sha256(raw).hexdigest(),
    )
