import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from clone_driver.artifacts import ArtifactCollector


class ArtifactCollectorTests(unittest.TestCase):
    def test_collect_writes_diff_test_outputs_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp) / "repo"
            out_dir = Path(tmp) / "artifacts"
            workdir.mkdir()
            subprocess.run(
                ["git", "init"],
                cwd=workdir,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            (workdir / "example.txt").write_text("changed\n", encoding="utf-8")

            manifest = ArtifactCollector().collect(
                workdir=workdir,
                out_dir=out_dir,
                test_cmd=[sys.executable, "-c", "print('OK')"],
            )

            manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(manifest_data["schema"], "clone-driver.artifacts.v1")
            self.assertEqual(manifest_data["test_exit_code"], 0)
            self.assertIn("OK", Path(manifest_data["test_stdout"]).read_text(encoding="utf-8"))
            self.assertTrue(Path(manifest_data["git_diff"]).exists())
            self.assertTrue(Path(manifest_data["git_diff_staged"]).exists())
            self.assertIn("example.txt", Path(manifest_data["git_status"]).read_text(encoding="utf-8"))
            self.assertIn("example.txt", Path(manifest_data["untracked_files"]).read_text(encoding="utf-8"))

    def test_collect_records_failing_test_exit_code_and_stderr(self):
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp) / "repo"
            out_dir = Path(tmp) / "artifacts"
            workdir.mkdir()
            subprocess.run(
                ["git", "init"],
                cwd=workdir,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            manifest = ArtifactCollector().collect(
                workdir=workdir,
                out_dir=out_dir,
                test_cmd=[
                    sys.executable,
                    "-c",
                    "import sys; print('bad', file=sys.stderr); raise SystemExit(7)",
                ],
            )

            manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(manifest_data["test_exit_code"], 7)
            self.assertIn("bad", Path(manifest_data["test_stderr"]).read_text(encoding="utf-8"))
