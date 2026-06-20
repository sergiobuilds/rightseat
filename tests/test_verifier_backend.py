import unittest

from clone_driver.verifier_backend import build_verifier_backend
from clone_driver.verifier_prompt import build_verifier_prompt


class VerifierBackendTests(unittest.TestCase):
    def test_claude_backend_targets_claude_verifier_module(self):
        backend = build_verifier_backend(backend="claude")
        self.assertEqual(backend.name, "claude")
        self.assertIn("clone_driver.claude_verifier", backend.command)
        self.assertEqual(backend.source, "builtin")

    def test_codex_backend_targets_codex_verifier_module(self):
        backend = build_verifier_backend(backend="codex", effort="low")
        self.assertIn("clone_driver.codex_verifier", backend.command)
        self.assertIn("--effort", backend.command)
        self.assertIn("low", backend.command)

    def test_custom_backend_uses_given_command(self):
        backend = build_verifier_backend(
            backend="custom", custom_command="my-verifier --flag"
        )
        self.assertEqual(backend.command, ["my-verifier", "--flag"])

    def test_custom_backend_requires_command(self):
        with self.assertRaises(ValueError):
            build_verifier_backend(backend="custom", custom_command="")

    def test_custom_backend_rejects_model_effort(self):
        with self.assertRaises(ValueError):
            build_verifier_backend(
                backend="custom", custom_command="x", model="opus"
            )

    def test_invalid_backend_raises(self):
        with self.assertRaises(ValueError):
            build_verifier_backend(backend="nope")


class VerifierPromptTests(unittest.TestCase):
    def test_prompt_embeds_packet_and_demands_matching(self):
        prompt = build_verifier_prompt('{"artifacts": {"test_exit_code": 0}}')
        self.assertIn('{"artifacts": {"test_exit_code": 0}}', prompt)
        self.assertIn("MATCHING, not judgment", prompt)
        self.assertIn("untrusted", prompt)
        self.assertIn("PASS|FAIL|ESCALATE", prompt)

    def test_prompt_marks_worker_self_grading_ignored(self):
        prompt = build_verifier_prompt("{}")
        self.assertIn("Ignore worker self-grading", prompt)


if __name__ == "__main__":
    unittest.main()
