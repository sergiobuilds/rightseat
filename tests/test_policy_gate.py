import unittest

from clone_driver.policy_gate import GateContext, evaluate_policy_gate


def _ctx(**kw):
    base = dict(
        action_kind="SUBMIT",
        action_source="llm",
        contract_loaded=True,
        seed_measurable=True,
        tier="ACT_ON_SAFE",
        draft_author="SELF",
        worker_claim="none",
        hard_stop=False,
        readback_capable=True,
    )
    base.update(kw)
    return GateContext(**base)


class PolicyGateTests(unittest.TestCase):
    def test_no_contract_escalates(self):
        self.assertEqual(evaluate_policy_gate(_ctx(contract_loaded=False)).decision, "ESCALATE")

    def test_unmeasurable_seed_escalates(self):
        self.assertEqual(evaluate_policy_gate(_ctx(seed_measurable=False)).decision, "ESCALATE")

    def test_hard_stop_escalates(self):
        self.assertEqual(evaluate_policy_gate(_ctx(hard_stop=True)).decision, "ESCALATE")

    def test_completion_claim_escalates(self):
        self.assertEqual(evaluate_policy_gate(_ctx(worker_claim="passed")).decision, "ESCALATE")

    def test_foreign_draft_submit_escalates(self):
        self.assertEqual(
            evaluate_policy_gate(_ctx(action_kind="SUBMIT", draft_author="FOREIGN")).decision,
            "ESCALATE",
        )

    def test_no_readback_escalates(self):
        self.assertEqual(evaluate_policy_gate(_ctx(readback_capable=False)).decision, "ESCALATE")

    def test_quick_source_escalates(self):
        self.assertEqual(evaluate_policy_gate(_ctx(action_source="quick")).decision, "ESCALATE")

    def test_tier_too_low_downgrades_to_suggest(self):
        self.assertEqual(
            evaluate_policy_gate(_ctx(tier="SUGGEST")).decision,
            "DOWNGRADE_SUGGEST",
        )

    def test_free_form_type_blocked_below_act_broad(self):
        self.assertEqual(
            evaluate_policy_gate(_ctx(action_kind="TYPE", tier="ACT_ON_SAFE")).decision,
            "DOWNGRADE_SUGGEST",
        )

    def test_all_gates_pass_allows(self):
        self.assertEqual(evaluate_policy_gate(_ctx()).decision, "ALLOW")

    def test_non_acting_always_allows(self):
        self.assertEqual(
            evaluate_policy_gate(_ctx(action_kind="WAIT", contract_loaded=False)).decision,
            "ALLOW",
        )


if __name__ == "__main__":
    unittest.main()
