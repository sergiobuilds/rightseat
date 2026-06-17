from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class QuestionDetection:
    status: str
    question: str


def _first_non_empty_group(match: re.Match[str]) -> str:
    for group in match.groups():
        if group and group.strip():
            return group.strip()
    return match.group(0).strip()


def detect_question(transcript: str, question_regex: str) -> QuestionDetection:
    try:
        matches = list(re.finditer(question_regex, transcript, re.MULTILINE))
    except re.error:
        return QuestionDetection(status="regex_error", question="")
    if not matches:
        return QuestionDetection(status="missing", question="")
    return QuestionDetection(
        status="found",
        question=_first_non_empty_group(matches[-1]),
    )
