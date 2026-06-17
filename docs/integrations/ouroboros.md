---
doc_kind: explanation
status: working
version: 2026-06-17_v1
canonical_path: self
---

# Ouroboros Integration Note

RightSeat is not an Ouroboros plugin and is not specific to Ouroboros. It is a standalone open-source experiment in visible AI operation: one terminal AI worker is doing the work, while another visible seat watches, answers prompts, submits drafts, stops, and leaves an audit trail.

This note explains why that shape may be useful for Ouroboros as one possible integration direction.

## Context

Ouroboros already has strong internal trust-building pieces: Socratic interview, ambiguity gates, refine/restate gates, fat harnesses, typed evidence, verifier PASS, and TraceGuard-style evidence discipline.

The remaining issue is mostly at the product boundary. Even when verification is logically external inside the engine, the user may still experience it as hidden because it happens behind a final status line, internal function, or subprocess.

RightSeat demonstrates a more visible trust boundary. The verifier or operator becomes a separate inspectable seat.

## 1. Easier selectable interviews

Related issue: [Q00/ouroboros#1239](https://github.com/Q00/ouroboros/issues/1239).

The next improvement is not only "ask better questions." The default interview UX should become easier to answer.

Useful interview questions should often be shaped as:

- 2-4 selectable answers;
- one custom free-text option;
- a short explanation of why this choice matters;
- a visible statement of what will change downstream depending on the answer.

This makes ambiguity gates feel less like friction. The system exposes the structure it already knows, while still leaving a path for unusual cases.

## 2. Visible external verification

Related issues:

- [Q00/ouroboros#830](https://github.com/Q00/ouroboros/issues/830)
- [Q00/ouroboros#920](https://github.com/Q00/ouroboros/issues/920)
- [Q00/ouroboros#978](https://github.com/Q00/ouroboros/issues/978)

The core already points in the right direction: fat harness, typed evidence, verifier PASS, and TraceGuard all reduce reliance on worker self-reporting.

The UX proposal is to make that verifier feel visibly external:

- it has its own pane or session;
- it observes the worker's output;
- it can ask for more evidence, fail, pass, or stop;
- it writes a ledger or transcript;
- it does not accept the worker's own "done" claim as proof;
- the user can inspect what it saw and why it decided.

RightSeat is a concrete reference for this visible-seat shape. The exact tmux implementation is not the important part. The important part is that the verifier becomes an inspectable participant, not only a hidden judgment.

Possible Ouroboros experiment:

- add an optional visible verifier/operator mode for local runs;
- display the verifier in a separate tmux pane or session;
- persist the verifier transcript as typed evidence;
- let the verifier request missing evidence instead of only returning a hidden pass/fail;
- keep the current harness semantics, but make the trust boundary easier to see.

## 3. Large project maps or Seed shards

Related issues:

- [Q00/ouroboros#1389](https://github.com/Q00/ouroboros/issues/1389)
- [Q00/ouroboros#1400](https://github.com/Q00/ouroboros/issues/1400)

For small tasks, one Seed and one run can be enough. For larger projects, a single Seed often becomes too large to reason about. Failures become hard to classify: weak execution, overbroad acceptance criteria, hidden dependencies, or a Seed that should have been split.

A larger project likely needs one of these shapes:

- a first-class project map above individual runs;
- or a master Seed that decomposes into smaller Seed shards.

The project map could be a living read model over runs:

- what the project is trying to become;
- which Seeds exist;
- which acceptance criteria are done, blocked, flaky, or deferred;
- which files or modules each Seed touched;
- which failures bounced repeatedly;
- where trace-informed splitting is recommended.

This connects to bounded attempts and trace-informed splitting. When a large Seed fails, the system should be able to say, "This is a decomposition problem," instead of retrying the same shape.

## 4. Persona-driven workflow checks around Seed creation

This is the implicit-knowledge problem. Builders often describe what they built, but users experience what they were trying to do.

A useful companion step is a UX workflow check around Seed creation. The core idea is to generate multiple user perspectives and walk through the workflow in first person, looking for things that "obviously should exist" from the user's perspective but were never written down.

This can run before or after Seed creation.

Before Seed creation, it can reveal missing acceptance criteria:

- a first-time user who does not know the vocabulary;
- a power user trying to move quickly;
- a skeptical user who wants proof;
- a user who failed once and came back later;
- a user under deadline pressure;
- a user on a constrained environment.

After Seed creation or execution, it can reveal missing product requirements:

- empty states;
- recovery paths;
- proof surfaces;
- handoff artifacts;
- "why this matters" explanations;
- controls that a real user would expect.

The important part is that this is not a generic UX checklist. It starts from the user's intent and follows the actual first-person chain: enter, decide, act, fail, recover, verify, leave, and return later.

Possible Ouroboros companion steps:

- `pre-seed workflow check`: find implicit requirements before the Seed is locked;
- `post-seed workflow check`: find missing user-facing acceptance criteria after a draft Seed exists;
- `post-run workflow check`: compare the produced artifact against the user's real workflow, not only the written ACs.

## Summary

RightSeat's general open-source value is the visible operator model for terminal AI workers.

For Ouroboros specifically, the same model suggests four product-level improvements:

1. interview questions default to selectable choices plus free text;
2. verification can run as a visible external seat;
3. large projects get a project map or master Seed that decomposes into smaller shards;
4. persona-driven workflow checks run around Seed creation to expose implicit requirements.

The broader principle is simple: trust improves when the workflow's critical actors are visible, inspectable, and accountable to evidence.
