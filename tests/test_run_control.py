import tempfile
import unittest
from pathlib import Path

from clone_driver.operator_console import format_attach_status
from clone_driver.run_control import read_control_state, write_control_state


class RunControlTests(unittest.TestCase):
    def test_write_and_read_control_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "control.json"

            write_control_state(path, mode="paused")
            state = read_control_state(path)

            self.assertEqual(state.mode, "paused")

    def test_missing_control_defaults_to_auto(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = read_control_state(Path(tmp) / "missing.json")

            self.assertEqual(state.mode, "auto")

    def test_operator_console_line_contains_action_context(self):
        line = format_attach_status(
            run_id="night-run",
            target="%7",
            mode="auto",
            backend="codex",
            model="gpt-5.4-mini",
            effort="low",
            answer_source="quick_reply",
            input_mode="text",
            status="sent",
        )

        self.assertIn("run=night-run", line)
        self.assertIn("target=%7", line)
        self.assertIn("backend=codex", line)
        self.assertIn("source=quick_reply", line)
        self.assertIn("status=sent", line)


if __name__ == "__main__":
    unittest.main()
