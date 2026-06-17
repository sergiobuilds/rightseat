import unittest

from clone_driver.quick_reply import quick_skippable


class QuickReplyTests(unittest.TestCase):
    def test_quick_rule_never_authors_input(self):
        result = quick_skippable(transcript="계속할까요?", quick_regex="계속")

        self.assertIsInstance(result, bool)
        self.assertTrue(result)

    def test_quick_rule_returns_false_without_regex(self):
        self.assertFalse(quick_skippable(transcript="x", quick_regex=""))

    def test_quick_rule_returns_false_without_match(self):
        self.assertFalse(quick_skippable(transcript="복잡한 판단 질문입니다.", quick_regex="계속"))


if __name__ == "__main__":
    unittest.main()
