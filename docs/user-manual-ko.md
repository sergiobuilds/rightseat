---
doc_kind: procedure
status: canonical
version: 2026-06-16_v7
canonical_path: self
---

# RightSeat 사용설명서

한 줄로 말하면 이겁니다.

```text
RightSeat는 worker 옆에 보이는 AI 조종석을 하나 더 띄우고,
그 조종석이 worker 화면을 보고 실제로 대신 입력하게 합니다.
```

## 제일 쉬운 사용법

```bash
rightseat
```

그러면 RightSeat가 붙을 worker 목록을 보여줍니다. 항상 번호로 고릅니다.

worker 후보가 하나처럼 보여도 자동으로 붙지 않습니다. user가 번호를 눌러야 시작합니다.

항상 떠 있는 서비스용 tmux, 예를 들어 `agent-discord`, 는 기본 worker 목록에서 빠집니다. 거기에 실수로 붙지 않게 하기 위한 규칙입니다.

켜진 뒤에는 이것만 기억하면 됩니다.

```bash
rightseat status
rightseat pause
rightseat resume
rightseat off
rightseat reset
```

## 화면에서 일어나는 일

```text
실행 전

┌──────────────────────────────┐
│ worker                        │
│ Claude / Codex / OOO          │
│ 질문: 계속할까요?             │
└──────────────────────────────┘
```

```text
실행 후

┌──────────── worker ────────────┬─────────── rightseat ───────────┐
│ Claude / Codex / OOO            │ RightSeat ON                    │
│ 질문: 계속할까요?               │ 보고 있음                       │
│ 진행해.                         │ 답을 넣음                       │
└────────────────────────────────┴─────────────────────────────────┘
```

user가 rightseat 창에 뭘 칠 필요는 없습니다.

```text
user가 `rightseat`를 한 번 실행한다.
RightSeat가 옆 창을 만든다.
옆 창이 worker를 본다.
옆 창이 필요할 때만 backend LLM에게 판단을 묻는다.
옆 창이 worker에 실제로 입력하고 Enter를 누른다.
```

## 자주 쓰는 명령

```bash
rightseat
rightseat status
rightseat pause
rightseat resume
rightseat off
rightseat reset
rightseat doctor --backend codex --model gpt-5.4-mini --effort low
rightseat log --log runtime/attach-runs/<run-id>/ledger.jsonl --tail 20
```

대상을 직접 지정해야 할 때만 씁니다.

```bash
rightseat targets
rightseat %0
```

## 용어

- `RightSeat`: 제품 이름입니다.
- `rightseat`: 사람이 치는 명령입니다.
- `worker`: 실제 일하는 AI TUI입니다.
- `seat`: worker 옆에 생기는 보이는 조종석입니다.
- `session`: worker 하나와 seat 하나가 붙은 실행입니다.
- `log`: 나중에 확인하는 기록입니다.
- `--model`, `--effort`, `--backend`: 공개 모델 설정입니다.

옛 이름도 남아 있습니다.

- `clone-driver`: deprecated 호환 명령입니다.
- `pair`: 내부 구현 명령입니다.
- `attach`: 내부 입력 엔진입니다.
- `ledger`: 내부 JSONL log입니다.
- `--advisor-model`, `--advisor-effort`: 내부 옵션명입니다. `rightseat`에서는 `--model`, `--effort`를 씁니다.

## 안 되는 것

RightSeat는 지금 tmux pane만 조작합니다.

임의 GUI 터미널 창을 조작하지 않습니다. Linux 계정 분리, VM 생성, systemd 배포도 하지 않습니다. OOO, looprun, ralph, Superpowers 원본도 수정하지 않습니다.
