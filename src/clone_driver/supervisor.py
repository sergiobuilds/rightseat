from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from .advisor import AdvisorRequest, ExternalAdvisor
from .ledger import JsonlLedger
from .pty_session import PtyWorker
from .question import detect_question


@dataclass(frozen=True)
class SupervisorConfig:
    worker_command: list[str]
    advisor_command: list[str]
    ledger_path: Path
    profile_path: Path
    answer_policy_path: Path
    ready_regex: str
    question_regex: str
    max_turns: int
    read_timeout_seconds: float = 5.0


class SupervisorLoop:
    def __init__(self, config: SupervisorConfig):
        self.config = config
        self.ledger = JsonlLedger(config.ledger_path)

    def run(self) -> dict[str, object]:
        profile = self.config.profile_path.read_text(encoding="utf-8")
        answer_policy = self.config.answer_policy_path.read_text(encoding="utf-8")
        advisor = ExternalAdvisor(self.config.advisor_command)
        worker = PtyWorker(self.config.worker_command)
        answered_questions: set[str] = set()
        processed_transcript_len = 0

        self.ledger.write(
            "supervise_started",
            {
                "worker_command": self.config.worker_command,
                "advisor_command": self.config.advisor_command,
                "ready_regex": self.config.ready_regex,
                "question_regex": self.config.question_regex,
                "max_turns": self.config.max_turns,
            },
        )

        try:
            turns = 0
            while turns < self.config.max_turns:
                transcript = worker.read_until("", self.config.read_timeout_seconds)

                if not worker.is_running():
                    status = "completed" if turns > 0 else "worker_exited"
                    self.ledger.write(
                        "supervise_finished",
                        {"status": status, "turns": turns},
                    )
                    return {"status": status, "turns": turns}

                new_transcript = transcript[processed_transcript_len:]
                detection = detect_question(new_transcript, self.config.question_regex)
                if detection.status != "found":
                    processed_transcript_len = len(transcript)
                    self.ledger.write(
                        "supervise_waiting",
                        {"status": detection.status, "turns": turns},
                    )
                    continue

                if detection.question in answered_questions:
                    self.ledger.write(
                        "supervise_finished",
                        {"status": "stalled", "turns": turns},
                    )
                    return {"status": "stalled", "turns": turns}

                request = AdvisorRequest(
                    question=detection.question,
                    screen_tail=transcript[-4000:],
                    profile=profile,
                    answer_policy=answer_policy,
                    turn_index=turns + 1,
                )
                response = advisor.ask(request)
                if response.action == "ESCALATE":
                    self.ledger.write(
                        "advisor_escalated",
                        {
                            "question": detection.question,
                            "reason": response.reason,
                            "confidence": response.confidence,
                            "injected": False,
                        },
                    )
                    return {"status": "escalated", "turns": turns}

                worker.send_line(response.answer)
                answered_questions.add(detection.question)
                processed_transcript_len = len(transcript)
                turns += 1
                self.ledger.write(
                    "advisor_turn",
                    {
                        "turn_index": turns,
                        "question": detection.question,
                        "action": response.action,
                        "confidence": response.confidence,
                        "reason": response.reason,
                        "answer_hash": sha256(response.answer.encode("utf-8")).hexdigest(),
                        "answer_preview": response.answer[:120],
                        "screen_tail_hash": sha256(transcript[-4000:].encode("utf-8")).hexdigest(),
                        "injected": True,
                    },
                )

            self.ledger.write(
                "supervise_finished",
                {"status": "max_turns_reached", "turns": turns},
            )
            return {"status": "max_turns_reached", "turns": turns}
        finally:
            worker.close()
