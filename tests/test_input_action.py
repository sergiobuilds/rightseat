import unittest

from clone_driver.input_action import InputAction


class InputActionTests(unittest.TestCase):
    def test_text_action_allows_typed_choice(self):
        action = InputAction.from_parts(
            mode="text",
            text="1",
            keys=[],
            choice_label="1) 진행",
            source="quick_reply",
        )

        self.assertEqual(action.mode, "text")
        self.assertEqual(action.text, "1")
        self.assertEqual(action.keys, [])
        self.assertEqual(action.choice_label, "1) 진행")

    def test_key_action_allows_safe_tmux_keys(self):
        action = InputAction.from_parts(
            mode="keys",
            text="",
            keys=["Down", "Space", "Enter"],
            choice_label="Enable auto mode",
            source="llm",
        )

        self.assertEqual(action.mode, "keys")
        self.assertEqual(action.keys, ["Down", "Space", "Enter"])

    def test_key_action_allows_enter_only_prompt(self):
        action = InputAction.from_parts(
            mode="keys",
            text="",
            keys=["Enter"],
            choice_label="Press Enter",
            source="quick_reply",
        )

        self.assertEqual(action.mode, "keys")
        self.assertEqual(action.keys, ["Enter"])

    def test_key_action_rejects_shell_text(self):
        with self.assertRaises(ValueError):
            InputAction.from_parts(
                mode="keys",
                text="",
                keys=["rm -rf /"],
                choice_label="bad",
                source="llm",
            )

    def test_key_action_requires_keys(self):
        with self.assertRaises(ValueError):
            InputAction.from_parts(
                mode="keys",
                text="",
                keys=[],
                choice_label="empty",
                source="llm",
            )

    def test_text_action_requires_text(self):
        with self.assertRaises(ValueError):
            InputAction.from_parts(
                mode="text",
                text="",
                keys=[],
                choice_label="empty",
                source="llm",
            )


if __name__ == "__main__":
    unittest.main()
