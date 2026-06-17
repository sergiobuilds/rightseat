import json
import unittest

from clone_driver.operator_decision import OperatorDecision, parse_operator_decision


class OperatorDecisionTests(unittest.TestCase):
    def test_submit_decision_becomes_enter_key_action(self):
        decision = parse_operator_decision(
            json.dumps(
                {
                    "action": "SUBMIT",
                    "text": "",
                    "keys": ["Enter"],
                    "reason": "Draft is ready.",
                    "confidence": "high",
                }
            )
        )

        self.assertEqual(decision.action, "SUBMIT")
        self.assertTrue(decision.executable_in_auto)
        self.assertEqual(decision.to_input_action().keys, ["Enter"])

    def test_type_decision_requires_text(self):
        with self.assertRaises(ValueError):
            parse_operator_decision(
                json.dumps(
                    {
                        "action": "TYPE",
                        "text": "",
                        "reason": "No text.",
                        "confidence": "high",
                    }
                )
            )

    def test_invalid_action_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_operator_decision(
                json.dumps(
                    {
                        "action": "APPROVE",
                        "text": "진행해.",
                        "reason": "Bad action.",
                        "confidence": "high",
                    }
                )
            )

    def test_low_confidence_does_not_execute_in_auto(self):
        decision = OperatorDecision(
            action="TYPE",
            text="진행해.",
            keys=[],
            reason="Maybe.",
            confidence="low",
        )

        self.assertFalse(decision.executable_in_auto)

    def test_unsafe_keys_are_rejected(self):
        with self.assertRaises(ValueError):
            parse_operator_decision(
                json.dumps(
                    {
                        "action": "KEYS",
                        "keys": ["C-z"],
                        "reason": "Unsafe.",
                        "confidence": "high",
                    }
                )
            )


if __name__ == "__main__":
    unittest.main()
