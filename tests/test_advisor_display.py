import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from clone_driver.advisor_display import AdvisorDisplay
from clone_driver.ledger import read_jsonl_records


class AdvisorDisplayTests(unittest.TestCase):
    def test_transcript_records_reason_and_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "advisor-transcript.jsonl"
            display = AdvisorDisplay(mode="inline", transcript_path=path)

            display.record_decision(
                run_id="run-a",
                target="%7",
                prompt_class="question",
                backend="codex",
                model="gpt-5.4-mini",
                effort="low",
                reason="matches WIW",
                proposed_input="진행해.",
                input_mode="text",
            )

            records = read_jsonl_records(path)
            self.assertEqual(records[0]["event"], "advisor_decision")
            self.assertEqual(records[0]["reason"], "matches WIW")
            self.assertEqual(records[0]["proposed_input"], "진행해.")

    def test_prompt_observed_status_records_without_polling_spam(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "advisor-transcript.jsonl"
            display = AdvisorDisplay(mode="inline", transcript_path=path)
            out = StringIO()

            with redirect_stdout(out):
                display.record_status(
                    status="prompt_observed",
                    run_id="run-a",
                    target="%7",
                    prompt_class="question",
                    message="질문: 계속할까요?",
                )

            self.assertEqual(out.getvalue(), "")
            records = read_jsonl_records(path)
            self.assertEqual(records[0]["event"], "advisor_status")
            self.assertEqual(records[0]["status"], "prompt_observed")

    def test_watching_status_prints_simple_panel(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "advisor-transcript.jsonl"
            display = AdvisorDisplay(mode="inline", transcript_path=path)
            out = StringIO()

            with redirect_stdout(out):
                display.record_status(
                    status="watching",
                    run_id="run-a",
                    target="%7",
                    prompt_class="",
                    message="watching %7",
                )

            visible = out.getvalue()
            self.assertIn("RightSeat ON", visible)
            self.assertIn("worker: %7", visible)
            self.assertIn("state: watching", visible)
            self.assertNotIn("advisor status=", visible)


if __name__ == "__main__":
    unittest.main()
