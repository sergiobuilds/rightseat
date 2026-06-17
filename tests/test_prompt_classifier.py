import unittest

from clone_driver.prompt_classifier import classify_prompt


class PromptClassifierTests(unittest.TestCase):
    def test_classifies_question(self):
        prompt = classify_prompt("질문: 계속할까요?", question_regex=r"질문[:：]\s*(.+)")

        self.assertEqual(prompt.prompt_class, "question")
        self.assertEqual(prompt.question, "계속할까요?")

    def test_classifies_enter_only(self):
        prompt = classify_prompt(
            "Press Enter to continue",
            question_regex=r"질문[:：]\s*(.+)",
        )

        self.assertEqual(prompt.prompt_class, "enter_only")

    def test_classifies_yes_no(self):
        prompt = classify_prompt("Proceed? [y/N]", question_regex=r"질문[:：]\s*(.+)")

        self.assertEqual(prompt.prompt_class, "yes_no")

    def test_classifies_typed_choice(self):
        prompt = classify_prompt(
            "선택하세요\n1) 진행\n2) 중단\n번호:",
            question_regex=r"질문[:：]\s*(.+)",
        )

        self.assertEqual(prompt.prompt_class, "typed_choice")

    def test_unknown_prompt_is_not_actionable(self):
        prompt = classify_prompt(
            "worker is still thinking",
            question_regex=r"질문[:：]\s*(.+)",
        )

        self.assertEqual(prompt.prompt_class, "unknown")
        self.assertEqual(prompt.question, "")


if __name__ == "__main__":
    unittest.main()
