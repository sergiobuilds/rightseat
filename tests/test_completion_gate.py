import json
import tempfile
import unittest
from pathlib import Path

from clone_driver.completion_gate import run_completion_gate
from clone_driver.verifier import Verdict


class FakeCollector:
    """manifest와 참조 파일을 실제처럼 써 주는 가짜 수집기."""

    def __init__(self, exit_code):
        self.exit_code = exit_code

    def collect(self, *, workdir, out_dir, test_cmd):
        out_dir.mkdir(parents=True, exist_ok=True)
        files = {}
        for key, name in [
            ("git_diff", "d.txt"),
            ("git_diff_staged", "ds.txt"),
            ("git_status", "s.txt"),
            ("untracked_files", "u.txt"),
            ("test_stdout", "o.txt"),
            ("test_stderr", "e.txt"),
        ]:
            p = out_dir / name
            p.write_text("", encoding="utf-8")
            files[key] = str(p)
        files["test_exit_code"] = self.exit_code
        manifest = out_dir / "manifest.json"
        manifest.write_text(json.dumps(files), encoding="utf-8")
        return manifest


class FakeVerifier:
    def __init__(self, status, reason=""):
        self.status = status
        self.reason = reason
        self.called = False

    def verify(self, packet_path):
        self.called = True
        return Verdict(self.status, self.reason)


class CompletionGateTests(unittest.TestCase):
    def _paths(self, root):
        for name in ("seed.md", "wiw.md", "ntd.md", "final.md"):
            (root / name).write_text("x", encoding="utf-8")
        return dict(
            seed_path=root / "seed.md",
            wiw_path=root / "wiw.md",
            not_to_do_path=root / "ntd.md",
            final_artifact_path=root / "final.md",
            workdir=root,
            test_cmd=["true"],
            out_dir=root / "out",
        )

    def _run(self, root, *, ac, exit_code, status, regressed=False):
        verifier = FakeVerifier(status)
        outcome = run_completion_gate(
            acceptance_criteria=ac,
            verifier=verifier,
            collector=FakeCollector(exit_code),
            regressed=regressed,
            **self._paths(root),
        )
        return outcome, verifier

    def test_no_acceptance_criteria_escalates_without_verifier(self):
        with tempfile.TemporaryDirectory() as tmp:
            outcome, verifier = self._run(
                Path(tmp), ac=[], exit_code=0, status="PASS"
            )
            self.assertEqual(outcome.verdict, "escalate")
            self.assertFalse(verifier.called)

    def test_failing_tests_inject_without_calling_verifier(self):
        with tempfile.TemporaryDirectory() as tmp:
            outcome, verifier = self._run(
                Path(tmp), ac=["builds"], exit_code=1, status="PASS"
            )
            self.assertEqual(outcome.verdict, "inject")
            self.assertEqual(outcome.verifier_status, "skipped")
            self.assertFalse(verifier.called)

    def test_pass_with_runtime_evidence_completes(self):
        with tempfile.TemporaryDirectory() as tmp:
            outcome, verifier = self._run(
                Path(tmp), ac=["builds"], exit_code=0, status="PASS"
            )
            self.assertEqual(outcome.verdict, "complete")
            self.assertTrue(verifier.called)

    def test_verifier_fail_injects_fix_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            outcome, verifier = self._run(
                Path(tmp), ac=["builds"], exit_code=0, status="FAIL"
            )
            self.assertEqual(outcome.verdict, "inject")
            self.assertTrue(verifier.called)

    def test_verifier_escalate_escalates(self):
        with tempfile.TemporaryDirectory() as tmp:
            outcome, _ = self._run(
                Path(tmp), ac=["builds"], exit_code=0, status="ESCALATE"
            )
            self.assertEqual(outcome.verdict, "escalate")

    def test_regression_injects_without_verifier(self):
        with tempfile.TemporaryDirectory() as tmp:
            outcome, verifier = self._run(
                Path(tmp), ac=["builds"], exit_code=0, status="PASS", regressed=True
            )
            self.assertEqual(outcome.verdict, "inject")
            self.assertFalse(verifier.called)


if __name__ == "__main__":
    unittest.main()
