import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from clone_driver.cli import main


class E2ETests(unittest.TestCase):
    def run_gate(self, force: str) -> tuple[int, str, str]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            packet = root / "packet.json"
            ledger = root / "ledger.jsonl"
            packet.write_text(json.dumps({"force": force}), encoding="utf-8")
            out = io.StringIO()
            with redirect_stdout(out):
                code = main(
                    [
                        "gate",
                        "--packet",
                        str(packet),
                        "--ledger",
                        str(ledger),
                        "--verifier-cmd",
                        f"{sys.executable} tests/fixtures/fake_verifier.py",
                        "--dry-run",
                    ]
                )
            return code, ledger.read_text(encoding="utf-8"), out.getvalue().strip()

    def test_pass_records_pass(self):
        code, ledger, stdout = self.run_gate("PASS")
        self.assertEqual(code, 0)
        self.assertEqual(stdout, "hold")
        self.assertIn('"verdict": "PASS"', ledger)
        self.assertIn('"action": "hold"', ledger)

    def test_fail_records_fail_but_returns_zero_for_injected_fix(self):
        code, ledger, stdout = self.run_gate("FAIL")
        self.assertEqual(code, 0)
        self.assertEqual(stdout, "inject")
        self.assertIn('"verdict": "FAIL"', ledger)
        self.assertIn('"action": "inject"', ledger)

    def test_escalate_records_stop(self):
        code, ledger, stdout = self.run_gate("ESCALATE")
        self.assertEqual(code, 4)
        self.assertEqual(stdout, "escalated")
        self.assertIn('"verdict": "ESCALATE"', ledger)
        self.assertIn('"action": "escalate"', ledger)
