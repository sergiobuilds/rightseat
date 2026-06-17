import sys
import unittest

from clone_driver.advisor_backend import build_advisor_backend


class AdvisorBackendTests(unittest.TestCase):
    def test_codex_backend_includes_model_and_effort(self):
        backend = build_advisor_backend(
            backend="codex",
            model="gpt-5.4-mini",
            effort="low",
            custom_command="",
        )

        self.assertEqual(backend.name, "codex")
        self.assertEqual(backend.model, "gpt-5.4-mini")
        self.assertEqual(backend.effort, "low")
        self.assertEqual(
            backend.command,
            [
                sys.executable,
                "-m",
                "clone_driver.codex_advisor",
                "--model",
                "gpt-5.4-mini",
                "--effort",
                "low",
            ],
        )

    def test_claude_backend_includes_model_and_effort(self):
        backend = build_advisor_backend(
            backend="claude",
            model="sonnet",
            effort="medium",
            custom_command="",
        )

        self.assertEqual(backend.name, "claude")
        self.assertEqual(
            backend.command,
            [
                sys.executable,
                "-m",
                "clone_driver.claude_advisor",
                "--model",
                "sonnet",
                "--effort",
                "medium",
            ],
        )

    def test_fake_backend_rejects_model_and_effort(self):
        with self.assertRaises(ValueError):
            build_advisor_backend(
                backend="fake",
                model="gpt-5.4-mini",
                effort="low",
                custom_command="",
            )

    def test_custom_backend_uses_custom_command(self):
        backend = build_advisor_backend(
            backend="custom",
            model="",
            effort="",
            custom_command="python3 tools/advisor.py --cheap",
        )

        self.assertEqual(backend.name, "custom")
        self.assertEqual(backend.command, ["python3", "tools/advisor.py", "--cheap"])
        self.assertEqual(backend.source, "custom_command")

    def test_custom_backend_requires_command(self):
        with self.assertRaises(ValueError):
            build_advisor_backend(
                backend="custom",
                model="",
                effort="",
                custom_command="",
            )


if __name__ == "__main__":
    unittest.main()
