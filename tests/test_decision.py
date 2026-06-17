import unittest

from clone_driver.decision import decide_next_input
from clone_driver.verifier import Verdict


class DecisionTests(unittest.TestCase):
    def test_pass_does_not_inject_go_signal(self):
        action = decide_next_input(Verdict(status="PASS", reason="ok"))
        self.assertNotEqual(action.status, "inject")
        self.assertEqual(action.status, "hold")
        self.assertEqual(action.message, "")

    def test_fail_fixes_without_trusting_worker_self_grading(self):
        action = decide_next_input(Verdict(status="FAIL", reason="missing tests"))
        self.assertEqual(action.status, "inject")
        self.assertIn("missing tests", action.message)
        self.assertIn("worker 자기평가를 믿지 말고", action.message)

    def test_escalate_holds(self):
        action = decide_next_input(Verdict(status="ESCALATE", reason="ambiguous"))
        self.assertEqual(action.status, "escalate")
        self.assertEqual(action.message, "ambiguous")
