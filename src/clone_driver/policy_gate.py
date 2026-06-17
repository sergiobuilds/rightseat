from __future__ import annotations

from dataclasses import dataclass


ALLOW = "ALLOW"
DOWNGRADE_SUGGEST = "DOWNGRADE_SUGGEST"
ESCALATE = "ESCALATE"

_ACTING_KINDS = {"TYPE", "SUBMIT", "KEYS"}
_TIER_ALLOWS = {
    "OBSERVE": frozenset(),
    "SUGGEST": frozenset(),
    "ACT_ON_SAFE": frozenset({"SUBMIT", "KEYS"}),
    "ACT_BROAD": frozenset({"TYPE", "SUBMIT", "KEYS"}),
}


@dataclass(frozen=True)
class GateContext:
    action_kind: str
    action_source: str
    contract_loaded: bool
    seed_measurable: bool
    tier: str
    draft_author: str
    worker_claim: str
    hard_stop: bool
    readback_capable: bool


@dataclass(frozen=True)
class GateResult:
    decision: str
    reason: str


def evaluate_policy_gate(ctx: GateContext) -> GateResult:
    """Deterministic fail-closed firewall immediately before worker input."""
    if ctx.action_kind not in _ACTING_KINDS:
        return GateResult(ALLOW, "non-acting action")
    if not ctx.contract_loaded:
        return GateResult(ESCALATE, "no contract loaded: OBSERVE_ONLY (E-2)")
    if not ctx.seed_measurable:
        return GateResult(ESCALATE, "seed not measurable: cannot judge distance")
    if ctx.hard_stop:
        return GateResult(ESCALATE, "hard-stop affordance")
    if ctx.worker_claim in {"done", "passed"}:
        return GateResult(ESCALATE, "completion claim is not a go-signal (E-3)")
    if ctx.action_kind == "SUBMIT" and ctx.draft_author == "FOREIGN":
        return GateResult(ESCALATE, "foreign draft must not be submitted")
    if not ctx.readback_capable:
        return GateResult(ESCALATE, "no readback path for this action")
    if ctx.action_source == "quick":
        return GateResult(ESCALATE, "quick rule cannot author input (E-3, AC-10)")
    if ctx.action_kind not in _TIER_ALLOWS.get(ctx.tier, frozenset()):
        return GateResult(DOWNGRADE_SUGGEST, f"tier {ctx.tier} disallows {ctx.action_kind}")
    return GateResult(ALLOW, "all gates passed")
