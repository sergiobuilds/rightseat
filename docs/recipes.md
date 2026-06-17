---
doc_kind: procedure
status: canonical
version: 2026-06-16_v7
canonical_path: self
---

# RightSeat Recipes

## Start

Use this first.

```bash
rightseat
```

Always choose the worker by number in the prompt. RightSeat does not auto-pick a worker.

Long-lived service sessions, such as `agent-discord`, are hidden from the normal worker list.

## Stop, Pause, Resume

```bash
rightseat status
rightseat pause
rightseat resume
rightseat off
rightseat reset
```

`rightseat off` stops only the RightSeat seat pane. It does not kill the worker.
`rightseat reset` removes stale RightSeat seat panes. It also keeps workers running.

## Choose A Worker Explicitly

Only use this when you need to name a pane directly.

```bash
rightseat targets
rightseat %0
```

## Backend Check

```bash
rightseat doctor --backend codex --model gpt-5.4-mini --effort low
```

The backend is a CLI OAuth LLM backend. RightSeat calls it only when the current screen needs judgment.

## Backend Choice

```bash
rightseat --backend codex --model gpt-5.4-mini --effort low
rightseat --backend claude --model sonnet --effort medium
```

## Read The Log

```bash
rightseat log --log runtime/attach-runs/<run-id>/ledger.jsonl --tail 20
```

## OOO / looprun / ralph / Superpowers

Run the worker inside tmux first. Then run:

```bash
rightseat
```

If several workers are open:

```bash
rightseat
```

Choose the worker by number. Do this even when only one worker candidate is shown.

RightSeat treats the worker's own completion claim as untrusted. The seat exists to keep returning to user's goal, not to let the worker approve itself.

## Compatibility

`clone-driver` remains as a deprecated compatibility command for lower-level internals. New public docs and examples should use `rightseat`.
