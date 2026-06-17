---
doc_kind: explanation
status: canonical
version: 2026-06-16_v7
canonical_path: self
---

# RightSeat

RightSeat puts a visible AI operator beside any terminal AI worker.

It is for the moment when Claude, Codex, or another terminal agent is already open in tmux and you want a second AI seat to watch it, answer prompts, submit drafts, or stop before the worker runs ahead.

## Why This Exists

Terminal AI agents are powerful, but their control loop is usually lonely: one worker reads the screen, makes a judgment, types, and later claims it is done.

RightSeat explores a different default: put another visible seat next to the worker.

- one pane runs the worker;
- another pane watches the worker;
- the seat can answer prompts, submit drafts, request evidence, or stop;
- decisions are written to an audit log and transcript;
- the worker's own "done" claim is never treated as proof.

The core idea is not tied to one agent framework. RightSeat is useful anywhere a terminal AI worker needs an inspectable operator, reviewer, verifier, or co-driver instead of another hidden subprocess.

## What It Is Good For

- keeping a long-running AI worker from answering prompts blindly;
- making review and verification visible in a separate pane;
- collecting a ledger of what the operator saw and decided;
- experimenting with human-inspectable agent supervision;
- using one agent as a visible operator for another agent without modifying the worker.

RightSeat is intentionally small. It currently targets tmux panes and keeps the control surface plain enough to inspect.

## The Whole Thing

```bash
rightseat
```

That is the normal command.

RightSeat always asks you to choose by number. It does not auto-pick a worker, even when there is only one visible worker candidate.

Always choose the worker by number in the prompt. Long-lived service sessions, such as `agent-discord`, are hidden from the normal worker list so RightSeat does not attach to them by accident.

After it is on:

```bash
rightseat status
rightseat pause
rightseat resume
rightseat off
rightseat reset
```

RightSeat calls the selected backend LLM only when it needs judgment. It does not call the LLM every polling tick.

It creates this layout:

```text
before

┌──────────────────────────────┐
│ worker                        │
│ Claude / Codex / OOO / etc.   │
└──────────────────────────────┘
```

```text
after

┌──────────── worker ────────────┬─────────── rightseat ───────────┐
│ Claude / Codex / OOO / etc.     │ RightSeat ON                     │
│ › Run /review on my changes      │ state: draft_ready               │
│                                  │ action: SUBMIT                   │
└────────────────────────────────┴─────────────────────────────────┘
```

## Common Commands

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

Advanced explicit target mode still exists:

```bash
rightseat targets
rightseat %0
```

## Integrations and Design Notes

- [Ouroboros integration note](docs/integrations/ouroboros.md): how RightSeat's visible external seat idea could apply to Ouroboros verification UX.

## Words

Use these public words:

- `RightSeat`: the product.
- `rightseat`: the command.
- `worker`: the AI TUI doing the work.
- `seat`: the visible operator pane created beside the worker.
- `session`: one worker plus one seat.
- `log`: the audit trail.
- `--model`, `--effort`, `--backend`: the public model controls.

These are internal compatibility words:

- `clone-driver`: old CLI name, kept as a deprecated compatibility alias.
- `pair`: internal command behind `rightseat`.
- `attach`: lower-level input engine.
- `ledger`: internal JSONL log file.
- `--advisor-model`, `--advisor-effort`: internal option names; use `--model` and `--effort` with `rightseat`.

## Boundaries

RightSeat currently supports tmux panes.

It does not drive arbitrary GUI terminal windows, change Linux users, create VMs, modify OOO/looprun/ralph/Superpowers, or treat a worker's own "done" claim as proof.

## Install

From this repo:

```bash
python3 -m pip install -e .
```

## License

MIT. See [LICENSE](LICENSE).
