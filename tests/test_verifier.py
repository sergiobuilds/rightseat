import json
import sys
import tempfile
import unittest
from pathlib import Path

from clone_driver.verifier import ExternalVerifier


class VerifierTests(unittest.TestCase):
    def test_external_verifier_reads_structured_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            packet = Path(tmp) / "packet.json"
            packet.write_text(json.dumps({"force": "PASS"}), encoding="utf-8")
            verifier = ExternalVerifier([sys.executable, "tests/fixtures/fake_verifier.py"])

            verdict = verifier.verify(packet)

            self.assertEqual(verdict.status, "PASS")
            self.assertEqual(verdict.reason, "forced PASS")

    def test_external_verifier_reads_structured_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            packet = Path(tmp) / "packet.json"
            packet.write_text(json.dumps({"force": "FAIL"}), encoding="utf-8")
            verifier = ExternalVerifier([sys.executable, "tests/fixtures/fake_verifier.py"])

            verdict = verifier.verify(packet)

            self.assertEqual(verdict.status, "FAIL")
            self.assertEqual(verdict.reason, "forced FAIL")

    def test_invalid_verdict_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            packet = Path(tmp) / "packet.json"
            packet.write_text(json.dumps({"force": "BAD"}), encoding="utf-8")
            verifier = ExternalVerifier([sys.executable, "tests/fixtures/fake_verifier.py"])

            with self.assertRaises(ValueError):
                verifier.verify(packet)
