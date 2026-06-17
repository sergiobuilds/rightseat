import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from clone_driver.ledger import read_jsonl_records
from clone_driver.pair import PairConfig, PairLauncher


class PairLauncherTests(unittest.TestCase):
    def test_pair_launcher_splits_visible_advisor_pane_and_records_ledger(self):
        calls: list[list[str]] = []

        def fake_run(args, **kwargs):
            calls.append(list(args))
            if args[:4] == ["tmux", "display-message", "-p", "-t"]:
                return SimpleNamespace(returncode=0, stdout="%7\n", stderr="")
            if args[:2] == ["tmux", "split-window"]:
                return SimpleNamespace(returncode=0, stdout="%8\n", stderr="")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = root / "ledger.jsonl"
            transcript = root / "advisor-transcript.jsonl"
            config = PairConfig(
                target="worker",
                run_id="pair-test",
                ledger_path=ledger,
                advisor_transcript_path=transcript,
                attach_args=[
                    "--backend",
                    "fake",
                    "--allow-missing-contract",
                    "--max-turns",
                    "1",
                ],
            )

            with patch("clone_driver.pair.subprocess.run", side_effect=fake_run):
                result = PairLauncher(config).launch()

            self.assertEqual(result.status, "started")
            self.assertEqual(result.worker_target, "%7")
            self.assertEqual(result.advisor_target, "%8")
            split_call = [call for call in calls if call[:2] == ["tmux", "split-window"]][0]
            self.assertIn("-h", split_call)
            self.assertIn("-t", split_call)
            self.assertIn("%7", split_call)
            shell_command = split_call[-1]
            self.assertIn("RightSeat ON", shell_command)
            self.assertIn("off: rightseat off", shell_command)
            self.assertIn("--target %7", shell_command)
            self.assertIn("--advisor-display inline", shell_command)
            self.assertIn(str(transcript), shell_command)

            records = read_jsonl_records(ledger)
            pair_started = [record for record in records if record["event"] == "pair_started"][0]
            self.assertEqual(pair_started["worker_target"], "%7")
            self.assertEqual(pair_started["advisor_target"], "%8")


if __name__ == "__main__":
    unittest.main()
