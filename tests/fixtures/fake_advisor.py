#!/usr/bin/env python3
import json
import sys


def main() -> int:
    request = json.loads(sys.stdin.read())
    question = request.get("question", "")

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

    if "혼자" in question:
        answer = "혼자 정리하는 시간도 필요하지만, 중요한 일은 사람들과 부딪치며 더 잘 풀립니다."
    elif "계획" in question:
        answer = "계획은 필요하지만, 실제 결과를 보면서 빠르게 고치는 쪽을 선호합니다."
    else:
        answer = "네, 대체로 그렇습니다."

    print(
        json.dumps(
            {
                "action": "ANSWER",
                "answer": answer,
                "reason": "MBTI-style question answered from the provided profile and policy.",
                "confidence": "high",
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
