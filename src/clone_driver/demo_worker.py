from __future__ import annotations


def main() -> int:
    print("READY", flush=True)
    print("질문: user는 어떤 답변을 선호하나요?", flush=True)
    answer = input()
    print("worker_received=" + answer, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
