from __future__ import annotations

import re
from dataclasses import dataclass


CODEX_PROMPT_RE = re.compile(r"^\s*›\s*(.*)$")
CHOICE_RE = re.compile(r"^\s*(?:❯\s*)?\d+[.)]\s+.+")
QUESTION_RE = re.compile(r"(?:\?|？|까요|나요|니|습니까|할까요)\s*$")
CODEX_PLACEHOLDERS = {"Implement {feature}"}
BUSY_RE = re.compile(
    r"[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏]|working\.\.\.|streaming|generating",
    re.IGNORECASE,
)
CLAIM_DONE_RE = re.compile(
    r"작업\s*완료|completed|\[COMPLETED\]|✅|all (?:tests? )?pass|passed\b|"
    r"모든\s*테스트\s*통과",
    re.IGNORECASE,
)
CLAIM_FAIL_RE = re.compile(r"failed\b|실패", re.IGNORECASE)
HARD_STOP_RE = re.compile(
    r"rm\s+-rf|git\s+push\s+--force|force-push|git\s+reset\s+--hard|"
    r"\bDROP\s+(TABLE|DATABASE)|\bTRUNCATE\b|deploy|publish|\bsudo\b|"
    r"\[y/N\]|\[Y/n\]|delete all",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ScreenModel:
    adapter: str
    state: str
    current_input: str
    question: str
    visible_tail: str
    confidence: str
    busy: bool = False
    worker_claim: str = "none"
    hard_stop: bool = False
    draft_author: str = "NONE"


def _visible_lines(transcript: str) -> list[str]:
    return [line.rstrip() for line in transcript.splitlines()]


def _find_last_codex_prompt(lines: list[str]) -> tuple[int, str] | None:
    for index in range(len(lines) - 1, -1, -1):
        match = CODEX_PROMPT_RE.match(lines[index])
        if match:
            return index, match.group(1).strip()
    return None


def _nearby_context(lines: list[str], prompt_index: int, *, limit: int = 8) -> list[str]:
    start = max(0, prompt_index - limit)
    return [line.strip() for line in lines[start:prompt_index] if line.strip()]


def _looks_like_question(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if stripped.startswith(("•", "-", "*")):
        stripped = stripped[1:].strip()
    if "질문" in stripped:
        return True
    return bool(QUESTION_RE.search(stripped))


def _choice_question(context: list[str]) -> str:
    option_lines = [line for line in context if CHOICE_RE.match(line)]
    if not option_lines:
        return ""
    lead_lines = [line for line in context if not CHOICE_RE.match(line)]
    lead = lead_lines[-1] if lead_lines else ""
    return "\n".join([lead, *option_lines]).strip()


def _current_question(context: list[str]) -> str:
    for line in reversed(context):
        if _looks_like_question(line):
            return line
    return ""


def _worker_claim(tail: str) -> str:
    if CLAIM_DONE_RE.search(tail):
        if re.search(r"pass|통과|✅", tail, re.IGNORECASE):
            return "passed"
        return "done"
    if CLAIM_FAIL_RE.search(tail):
        return "failed"
    return "none"


def _screen_flags(visible_tail: str, *, current_input: str = "") -> dict[str, object]:
    return {
        "busy": bool(BUSY_RE.search(visible_tail)),
        "worker_claim": _worker_claim(visible_tail),
        "hard_stop": bool(HARD_STOP_RE.search(visible_tail)),
        "draft_author": "FOREIGN" if current_input else "NONE",
    }


def analyze_screen(transcript: str) -> ScreenModel:
    lines = _visible_lines(transcript)
    visible_tail = "\n".join(lines[-40:])
    prompt = _find_last_codex_prompt(lines)
    flags = _screen_flags(visible_tail)

    if prompt is None:
        return ScreenModel(
            adapter="generic",
            state="unknown",
            current_input="",
            question="",
            visible_tail=visible_tail,
            confidence="low",
            **flags,
        )

    prompt_index, prompt_text = prompt
    current_input = "" if prompt_text in CODEX_PLACEHOLDERS else prompt_text
    if current_input:
        return ScreenModel(
            adapter="codex",
            state="draft_ready",
            current_input=current_input,
            question="",
            visible_tail=visible_tail,
            confidence="high",
            **_screen_flags(visible_tail, current_input=current_input),
        )

    context = _nearby_context(lines, prompt_index)
    choice = _choice_question(context)
    if choice:
        return ScreenModel(
            adapter="codex",
            state="choice_waiting",
            current_input="",
            question=choice,
            visible_tail=visible_tail,
            confidence="medium",
            **flags,
        )

    question = _current_question(context)
    if question:
        return ScreenModel(
            adapter="codex",
            state="question_waiting",
            current_input="",
            question=question,
            visible_tail=visible_tail,
            confidence="medium",
            **flags,
        )

    return ScreenModel(
        adapter="codex",
        state="input_empty",
        current_input="",
        question="",
        visible_tail=visible_tail,
        confidence="high",
        **flags,
    )
