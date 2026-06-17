import io
import json
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch

from clone_driver import claude_advisor, codex_advisor


class AdvisorWrapperTests(unittest.TestCase):
    def test_codex_advisor_passes_model_and_effort_to_codex_cli(self):
        calls = []

        def fake_run(args, **kwargs):
            calls.append((args, kwargs))
            output_path = args[args.index("-o") + 1]
            with open(output_path, "w", encoding="utf-8") as handle:
                handle.write(
                    json.dumps(
                        {
                            "action": "ANSWER",
                            "answer": "ok",
                            "reason": "test",
                            "confidence": "high",
                        }
                    )
                )
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        stdin = io.StringIO(
            json.dumps(
                {
                    "screen_state": "draft_ready",
                    "current_input": "Run /review on my current changes",
                    "question": "",
                    "screen_tail": "› Run /review on my current changes",
                }
            )
        )
        stdout = io.StringIO()

        with patch("clone_driver.codex_advisor.sys.stdin", stdin):
            with patch("clone_driver.codex_advisor.subprocess.run", side_effect=fake_run):
                with patch(
                    "clone_driver.codex_advisor.sys.argv",
                    [
                        "clone_driver.codex_advisor",
                        "--model",
                        "gpt-5.4-mini",
                        "--effort",
                        "low",
                    ],
                ):
                    with redirect_stdout(stdout):
                        code = codex_advisor.main()

        self.assertEqual(code, 0)
        command = calls[0][0]
        self.assertIn("--model", command)
        self.assertIn("gpt-5.4-mini", command)
        self.assertIn("-c", command)
        self.assertIn('model_reasoning_effort="low"', command)
        prompt = command[-1]
        self.assertIn("WAIT, TYPE, SUBMIT, KEYS, or ESCALATE", prompt)
        self.assertIn("Screen state:\ndraft_ready", prompt)
        self.assertIn("Current input:\nRun /review on my current changes", prompt)

    def test_claude_advisor_passes_model_and_effort_to_claude_cli(self):
        stdin = io.StringIO(
            json.dumps(
                {
                    "screen_state": "choice_waiting",
                    "current_input": "",
                    "question": "어떤 옵션을 선택할까요?",
                    "screen_tail": "❯ 1. 진행",
                },
                ensure_ascii=False,
            )
        )
        stdout = io.StringIO()

        with patch("clone_driver.claude_advisor.sys.stdin", stdin):
            with patch(
                "clone_driver.claude_advisor.subprocess.run",
                return_value=SimpleNamespace(
                    returncode=0,
                    stdout=json.dumps(
                        {
                            "action": "ANSWER",
                            "answer": "ok",
                            "reason": "test",
                            "confidence": "high",
                        }
                    ),
                    stderr="",
                ),
            ) as run:
                with patch(
                    "clone_driver.claude_advisor.sys.argv",
                    [
                        "clone_driver.claude_advisor",
                        "--model",
                        "sonnet",
                        "--effort",
                        "medium",
                    ],
                ):
                    with redirect_stdout(stdout):
                        code = claude_advisor.main()

        self.assertEqual(code, 0)
        command = run.call_args.args[0]
        self.assertEqual(command[:2], ["claude", "-p"])
        self.assertIn("--model", command)
        self.assertIn("sonnet", command)
        self.assertIn("--effort", command)
        self.assertIn("medium", command)
        prompt = command[-1]
        self.assertIn("WAIT, TYPE, SUBMIT, KEYS, or ESCALATE", prompt)
        self.assertIn("Screen state:\nchoice_waiting", prompt)
        self.assertIn("Question:\n어떤 옵션을 선택할까요?", prompt)


if __name__ == "__main__":
    unittest.main()
