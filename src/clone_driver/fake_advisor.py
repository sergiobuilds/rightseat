from __future__ import annotations

import json
import sys


def main() -> int:
    request = json.loads(sys.stdin.read())
    question = request.get("question", "")
    screen_state = request.get("screen_state", "")
    current_input = request.get("current_input", "")

    if "FORCE_ESCALATE" in question:
        print(
            json.dumps(
                {
                    "action": "ESCALATE",
                    "answer": "",
                    "reason": "The fake advisor was instructed to escalate.",
                    "confidence": "low",
                },
                ensure_ascii=False,
            )
        )
        return 0

    if screen_state == "draft_ready" and current_input:
        print(
            json.dumps(
                {
                    "action": "SUBMIT",
                    "text": "",
                    "keys": ["Enter"],
                    "reason": "The fake advisor sees a current input draft.",
                    "confidence": "high",
                },
                ensure_ascii=False,
            )
        )
        return 0

    answer = "user는 직접적이고 실용적이며 증거 중심의 짧은 답을 선호합니다."
    print(
        json.dumps(
            {
                "action": "ANSWER",
                "answer": answer,
                "reason": "Answered from the bundled user profile example.",
                "confidence": "high",
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
