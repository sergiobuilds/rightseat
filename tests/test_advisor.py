import json
import sys
import unittest

from clone_driver.advisor import AdvisorRequest, AdvisorResponse, ExternalAdvisor


class AdvisorTests(unittest.TestCase):
    def test_fake_advisor_returns_structured_answer(self):
        advisor = ExternalAdvisor([sys.executable, "tests/fixtures/fake_advisor.py"])
        request = AdvisorRequest(
            question="질문: 사람들과 있을 때 에너지가 생기나요?",
            screen_tail="MBTI_READY\n질문: 사람들과 있을 때 에너지가 생기나요?",
            profile="user prefers direct practical answers.",
            answer_policy="Answer in Korean as user. Keep it short.",
            turn_index=1,
        )

        response = advisor.ask(request)

        self.assertEqual(response.action, "ANSWER")
        self.assertEqual(response.confidence, "high")
        self.assertIn("대체로 그렇습니다", response.answer)
        self.assertIn("MBTI", response.reason)

    def test_escalate_response_is_allowed_without_answer(self):
        advisor = ExternalAdvisor([sys.executable, "tests/fixtures/fake_advisor.py"])
        request = AdvisorRequest(
            question="질문: FORCE_ESCALATE",
            screen_tail="질문: FORCE_ESCALATE",
            profile="profile",
            answer_policy="policy",
            turn_index=1,
        )

        response = advisor.ask(request)

        self.assertEqual(response.action, "ESCALATE")
        self.assertEqual(response.answer, "")
        self.assertEqual(response.confidence, "low")

    def test_answer_response_accepts_key_action_fields(self):
        response = AdvisorResponse.from_json(
            json.dumps(
                {
                    "action": "ANSWER",
                    "answer": "",
                    "reason": "Select the safe option.",
                    "confidence": "medium",
                    "input_mode": "keys",
                    "keys": ["Down", "Enter"],
                    "choice_label": "Proceed",
                    "answer_source": "llm",
                }
            )
        )

        self.assertEqual(response.input_mode, "keys")
        self.assertEqual(response.keys, ["Down", "Enter"])
        self.assertEqual(response.choice_label, "Proceed")
        self.assertEqual(response.answer_source, "llm")

    def test_submit_operator_action_is_allowed(self):
        response = AdvisorResponse.from_json(
            json.dumps(
                {
                    "action": "SUBMIT",
                    "text": "",
                    "keys": ["Enter"],
                    "reason": "Draft is already present.",
                    "confidence": "high",
                }
            )
        )

        self.assertEqual(response.action, "SUBMIT")
        self.assertEqual(response.input_mode, "keys")
        self.assertEqual(response.keys, ["Enter"])

    def test_unknown_answer_source_defaults_to_llm(self):
        response = AdvisorResponse.from_json(
            json.dumps(
                {
                    "action": "ANSWER",
                    "answer": "진행해.",
                    "reason": "Answered from profile context.",
                    "confidence": "high",
                    "answer_source": "profile",
                },
                ensure_ascii=False,
            )
        )

        self.assertEqual(response.answer_source, "llm")

    def test_key_response_requires_key_list(self):
        with self.assertRaises(ValueError):
            AdvisorResponse.from_json(
                json.dumps(
                    {
                        "action": "ANSWER",
                        "answer": "",
                        "reason": "bad",
                        "confidence": "medium",
                        "input_mode": "keys",
                        "keys": "Enter",
                    }
                )
            )

    def test_invalid_action_raises_value_error(self):
        response = {
            "action": "CONTINUE",
            "answer": "x",
            "reason": "bad action",
            "confidence": "high",
        }

        with self.assertRaises(ValueError):
            AdvisorResponse.from_json(json.dumps(response))

    def test_answer_action_requires_non_empty_answer(self):
        response = {
            "action": "ANSWER",
            "answer": "",
            "reason": "missing answer",
            "confidence": "high",
        }

        with self.assertRaises(ValueError):
            AdvisorResponse.from_json(json.dumps(response))

    def test_invalid_confidence_raises_value_error(self):
        response = {
            "action": "ANSWER",
            "answer": "네.",
            "reason": "valid answer",
            "confidence": "certain",
        }

        with self.assertRaises(ValueError):
            AdvisorResponse.from_json(json.dumps(response))


if __name__ == "__main__":
    unittest.main()
