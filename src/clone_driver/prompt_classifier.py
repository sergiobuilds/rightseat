from __future__ import annotations

import re
from dataclasses import dataclass

from .question import detect_question


@dataclass(frozen=True)
class ClassifiedPrompt:
    prompt_class: str
    question: str


def classify_prompt(transcript: str, *, question_regex: str) -> ClassifiedPrompt:
    if re.search(r"Press Enter|계속하려면\s*Enter|Enter to continue", transcript, re.I):
        return ClassifiedPrompt(prompt_class="enter_only", question="")
    if re.search(r"\[[yYnN]/[yYnN]\]|\([yYnN]/[yYnN]\)|yes/no", transcript, re.I):
        return ClassifiedPrompt(prompt_class="yes_no", question="")
    if re.search(r"(^|\n)\s*[0-9A-Za-z][\).:]\s+.+", transcript):
        return ClassifiedPrompt(prompt_class="typed_choice", question="")
    detection = detect_question(transcript, question_regex)
    if detection.status == "found":
        return ClassifiedPrompt(prompt_class="question", question=detection.question)
    return ClassifiedPrompt(prompt_class="unknown", question="")
