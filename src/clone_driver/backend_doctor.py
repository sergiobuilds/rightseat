from __future__ import annotations

import shutil
from dataclasses import dataclass

from .advisor import AdvisorResponse


@dataclass(frozen=True)
class DoctorResult:
    status: str
    detail: str = ""


def check_cli_available(command: str) -> DoctorResult:
    return DoctorResult("ok" if shutil.which(command) else "missing_cli", command)


def validate_advisor_schema(output: str) -> DoctorResult:
    try:
        AdvisorResponse.from_json(output)
    except (ValueError, TypeError) as error:
        return DoctorResult(status="schema_error", detail=str(error))
    return DoctorResult(status="ok")
