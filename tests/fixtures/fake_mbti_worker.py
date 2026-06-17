#!/usr/bin/env python3
import sys


QUESTIONS = [
    "질문: 사람들과 있을 때 에너지가 생기나요?",
    "Q2: 혼자 정리하는 시간이 꼭 필요한가요?",
    "Q3: 계획을 먼저 세우는 편인가요?",
]


def main() -> int:
    print("MBTI_READY", flush=True)
    answers: list[str] = []
    for question in QUESTIONS:
        print(question, flush=True)
        answer = input()
        answers.append(answer)
        print(f"worker_received={answer}", flush=True)
    print("MBTI_DONE", flush=True)
    print("answers_count=" + str(len(answers)), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
