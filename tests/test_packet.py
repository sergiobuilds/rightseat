import json
import tempfile
import unittest
from pathlib import Path

from clone_driver.packet import PacketBuilder


class PacketTests(unittest.TestCase):
    def test_packet_contains_contract_and_artifacts_without_worker_claims(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed = root / "seed.md"
            wiw = root / "wiw.md"
            not_to_do = root / "not-to-do.md"
            final_artifact = root / "final.md"
            diff = root / "diff.txt"
            test_output = root / "test-output.txt"
            for path, text in [
                (seed, "seed text"),
                (wiw, "wiw text"),
                (not_to_do, "do not trust worker claims"),
                (final_artifact, "CLI tool"),
                (diff, "diff --git"),
                (test_output, "OK"),
            ]:
                path.write_text(text, encoding="utf-8")

            packet = PacketBuilder().build(
                seed=seed,
                wiw=wiw,
                not_to_do=not_to_do,
                final_artifact=final_artifact,
                diff=diff,
                test_output=test_output,
            )

            self.assertEqual(packet["contract"]["seed"], "seed text")
            self.assertEqual(packet["contract"]["wiw"], "wiw text")
            self.assertEqual(packet["contract"]["final_artifact"], "CLI tool")
            self.assertEqual(packet["artifacts"]["test_output"], "OK")
            self.assertIn("Worker self-grading", packet["instruction"])
            self.assertEqual(
                packet["source_policy"]["worker_self_grading"], "untrusted"
            )
            self.assertEqual(
                packet["source_policy"]["verifier_input"],
                "contract_and_artifacts_only",
            )
            self.assertNotIn("worker_claim", json.dumps(packet))

    def test_packet_reads_artifact_manifest_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed = root / "seed.md"
            wiw = root / "wiw.md"
            not_to_do = root / "not-to-do.md"
            final_artifact = root / "final.md"
            git_status = root / "git-status.txt"
            test_stdout = root / "test-stdout.txt"
            manifest = root / "manifest.json"
            for path, text in [
                (seed, "seed text"),
                (wiw, "wiw text"),
                (not_to_do, "do not trust worker claims"),
                (final_artifact, "CLI tool"),
                (git_status, "?? example.txt"),
                (test_stdout, "OK"),
            ]:
                path.write_text(text, encoding="utf-8")
            manifest.write_text(
                json.dumps(
                    {
                        "git_status": str(git_status),
                        "test_stdout": str(test_stdout),
                        "test_exit_code": 0,
                    }
                ),
                encoding="utf-8",
            )

            packet = PacketBuilder().build(
                seed=seed,
                wiw=wiw,
                not_to_do=not_to_do,
                final_artifact=final_artifact,
                artifact_manifest=manifest,
            )

            self.assertEqual(packet["artifacts"]["git_status"], "?? example.txt")
            self.assertEqual(packet["artifacts"]["test_stdout"], "OK")
            self.assertEqual(packet["artifacts"]["test_exit_code"], 0)
