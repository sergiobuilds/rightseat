import tempfile
import unittest
import subprocess
import uuid
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from clone_driver.ledger import JsonlLedger
from clone_driver.terminal import (
    FakeTerminalBroker,
    InjectionResult,
    NudgeRunner,
    TmuxTerminalBroker,
)


class TerminalTests(unittest.TestCase):
    def test_fake_terminal_capture_returns_transcript(self):
        terminal = FakeTerminalBroker(idle=True)
        terminal.transcript = "질문: 다음에 뭘 할까요?"

        result = terminal.capture("work")

        self.assertEqual(result.status, "captured")
        self.assertEqual(result.canonical_target, "work")
        self.assertIn("질문:", result.transcript)

    def test_fake_terminal_send_keys_records_key_sequence(self):
        terminal = FakeTerminalBroker(idle=True)

        result = terminal.send_keys("work", ["Down", "Enter"])

        self.assertEqual(result.status, "sent")
        self.assertTrue(result.enter_sent)
        self.assertEqual(result.readback_status, "key_sequence_sent")
        self.assertEqual(terminal.sent, [("work", "Down Enter")])

    def test_nudge_sends_message_and_records_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger_path = Path(tmp) / "ledger.jsonl"
            terminal = FakeTerminalBroker(idle=True)
            runner = NudgeRunner(terminal=terminal, ledger=JsonlLedger(ledger_path))

            result = runner.run(session="work", message="계속해.")

            self.assertEqual(result["status"], "sent")
            self.assertTrue(result["enter_sent"])
            self.assertEqual(terminal.sent, [("work", "계속해.")])
            record = json.loads(ledger_path.read_text(encoding="utf-8"))
            self.assertEqual(record["event"], "nudge")
            self.assertEqual(record["status"], "sent")
            self.assertEqual(record["target"], "work")
            self.assertEqual(record["canonical_target"], "work")
            self.assertEqual(record["readiness_evidence"], "fake_idle")
            self.assertEqual(record["readback_status"], "fake")
            self.assertTrue(record["enter_sent"])
            self.assertEqual(
                record["message_hash"],
                "9165898254c12b1f5adff74528707bc5e28f7c592f7023b1dc706bf4a0620c1f",
            )

    def test_nudge_does_not_send_when_not_idle(self):
        with tempfile.TemporaryDirectory() as tmp:
            terminal = FakeTerminalBroker(idle=False)
            runner = NudgeRunner(
                terminal=terminal, ledger=JsonlLedger(Path(tmp) / "ledger.jsonl")
            )

            result = runner.run(session="work", message="계속해.")

            self.assertEqual(result["status"], "not_idle")
            self.assertEqual(terminal.sent, [])
            record = json.loads((Path(tmp) / "ledger.jsonl").read_text(encoding="utf-8"))
            self.assertEqual(record["target"], "work")
            self.assertEqual(record["canonical_target"], "work")
            self.assertEqual(record["readiness_evidence"], "missing")
            self.assertEqual(record["readback_status"], "not_attempted")
            self.assertFalse(record["enter_sent"])

    def test_nudge_sends_to_readiness_canonical_target(self):
        class AliasChangingTerminal:
            def __init__(self):
                self.sent_to = []

            def readiness(self, session: str):
                return SimpleNamespace(
                    idle=True,
                    evidence="idle_marker:READY",
                    canonical_target="%7",
                )

            def is_idle(self, session: str) -> bool:
                return True

            def send(self, session: str, message: str) -> InjectionResult:
                self.sent_to.append(session)
                return InjectionResult(
                    status="sent",
                    enter_sent=True,
                    readback_status="matched",
                    canonical_target=session,
                )

        with tempfile.TemporaryDirectory() as tmp:
            terminal = AliasChangingTerminal()
            runner = NudgeRunner(
                terminal=terminal, ledger=JsonlLedger(Path(tmp) / "ledger.jsonl")
            )

            result = runner.run(session="work", message="계속해.")

            self.assertEqual(terminal.sent_to, ["%7"])
            self.assertEqual(result["target"], "work")
            self.assertEqual(result["canonical_target"], "%7")


class SafeTmuxTerminalTests(unittest.TestCase):
    def test_tmux_capture_returns_canonical_target_and_transcript(self):
        def fake_run(args, **kwargs):
            if args[:4] == ["tmux", "display-message", "-p", "-t"]:
                return SimpleNamespace(returncode=0, stdout="%7\n", stderr="")
            if args[:2] == ["tmux", "capture-pane"]:
                return SimpleNamespace(returncode=0, stdout="READY\n질문: 계속할까요?\n", stderr="")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        broker = TmuxTerminalBroker()

        with patch("clone_driver.terminal.subprocess.run", side_effect=fake_run):
            result = broker.capture("work")

        self.assertEqual(result.status, "captured")
        self.assertEqual(result.canonical_target, "%7")
        self.assertIn("질문: 계속할까요?", result.transcript)

    def test_tmux_without_idle_marker_is_not_idle(self):
        broker = TmuxTerminalBroker(idle_marker="")

        self.assertFalse(broker.is_idle("work"))

    def test_tmux_idle_regex_marks_ready_and_records_evidence(self):
        def fake_run(args, **kwargs):
            if args[:4] == ["tmux", "display-message", "-p", "-t"]:
                return SimpleNamespace(returncode=0, stdout="%7\n", stderr="")
            if args[:2] == ["tmux", "capture-pane"]:
                return SimpleNamespace(returncode=0, stdout="status: READY\n", stderr="")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        broker = TmuxTerminalBroker(idle_regex=r"status: READY")

        with patch("clone_driver.terminal.subprocess.run", side_effect=fake_run):
            readiness = broker.readiness("work")

        self.assertTrue(readiness.idle)
        self.assertEqual(readiness.canonical_target, "%7")
        self.assertEqual(readiness.evidence, "idle_regex:status: READY")

    def test_tmux_invalid_idle_regex_is_not_idle(self):
        def fake_run(args, **kwargs):
            if args[:4] == ["tmux", "display-message", "-p", "-t"]:
                return SimpleNamespace(returncode=0, stdout="%7\n", stderr="")
            if args[:2] == ["tmux", "capture-pane"]:
                return SimpleNamespace(returncode=0, stdout="READY", stderr="")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        broker = TmuxTerminalBroker(idle_regex="[")

        with patch("clone_driver.terminal.subprocess.run", side_effect=fake_run):
            readiness = broker.readiness("work")

        self.assertFalse(readiness.idle)
        self.assertEqual(readiness.canonical_target, "%7")
        self.assertTrue(readiness.evidence.startswith("idle_regex_error:"))

    def test_readback_failure_does_not_send_enter(self):
        class NoEchoTerminal(FakeTerminalBroker):
            def send(self, session: str, message: str) -> InjectionResult:
                return InjectionResult(
                    status="readback_failed",
                    enter_sent=False,
                    readback_status="missing",
                    canonical_target=session,
                )

        with tempfile.TemporaryDirectory() as tmp:
            runner = NudgeRunner(
                terminal=NoEchoTerminal(idle=True),
                ledger=JsonlLedger(Path(tmp) / "ledger.jsonl"),
            )

            result = runner.run(session="work", message="계속해.")

            self.assertEqual(result["status"], "readback_failed")
            self.assertFalse(result["enter_sent"])
            self.assertEqual(result["readback_status"], "missing")

    def test_tmux_send_stops_before_enter_when_readback_missing(self):
        calls = []

        def fake_run(args, **kwargs):
            calls.append(args)
            if args[:4] == ["tmux", "display-message", "-p", "-t"]:
                return SimpleNamespace(returncode=0, stdout="%7\n", stderr="")
            if args[:2] == ["tmux", "capture-pane"]:
                return SimpleNamespace(returncode=0, stdout="prompt only", stderr="")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        broker = TmuxTerminalBroker(idle_marker="READY")

        with patch("clone_driver.terminal.subprocess.run", side_effect=fake_run):
            result = broker.send("work", "계속해.")

        self.assertEqual(result.status, "readback_failed")
        self.assertFalse(result.enter_sent)
        self.assertEqual(result.canonical_target, "%7")
        self.assertNotIn(["tmux", "send-keys", "-t", "%7", "Enter"], calls)

    def test_tmux_send_pastes_then_sends_enter_after_readback_match(self):
        calls = []

        def fake_run(args, **kwargs):
            calls.append(args)
            if args[:4] == ["tmux", "display-message", "-p", "-t"]:
                return SimpleNamespace(returncode=0, stdout="%7\n", stderr="")
            if args[:2] == ["tmux", "capture-pane"]:
                return SimpleNamespace(returncode=0, stdout="계속해.", stderr="")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        broker = TmuxTerminalBroker(idle_marker="READY")

        with patch("clone_driver.terminal.subprocess.run", side_effect=fake_run):
            with patch("clone_driver.terminal.uuid.uuid4", return_value=uuid.UUID(int=1)):
                result = broker.send("work", "계속해.")

        self.assertEqual(result.status, "sent")
        self.assertTrue(result.enter_sent)
        self.assertEqual(result.canonical_target, "%7")
        buffer_name = "clone-driver-input-00000000000000000000000000000001"
        self.assertIn(["tmux", "load-buffer", "-b", buffer_name, "-"], calls)
        self.assertIn(["tmux", "paste-buffer", "-b", buffer_name, "-t", "%7"], calls)
        self.assertIn(["tmux", "delete-buffer", "-b", buffer_name], calls)
        self.assertEqual(calls[-2], ["tmux", "send-keys", "-t", "%7", "Enter"])

    def test_tmux_send_keys_sends_navigation_only_sequence_to_canonical_target(self):
        calls = []

        def fake_run(args, **kwargs):
            calls.append(args)
            if args[:4] == ["tmux", "display-message", "-p", "-t"]:
                return SimpleNamespace(returncode=0, stdout="%7\n", stderr="")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        broker = TmuxTerminalBroker(idle_marker="READY")

        with patch("clone_driver.terminal.subprocess.run", side_effect=fake_run):
            result = broker.send_keys("work", ["Down"])

        self.assertEqual(result.status, "sent")
        self.assertFalse(result.enter_sent)
        self.assertEqual(result.canonical_target, "%7")
        self.assertIn(["tmux", "send-keys", "-t", "%7", "Down"], calls)

    def test_tmux_send_keys_blocks_enter_without_readback(self):
        calls = []

        def fake_run(args, **kwargs):
            calls.append(args)
            if args[:4] == ["tmux", "display-message", "-p", "-t"]:
                return SimpleNamespace(returncode=0, stdout="%7\n", stderr="")
            if args[:2] == ["tmux", "capture-pane"]:
                return SimpleNamespace(returncode=0, stdout="same screen", stderr="")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        broker = TmuxTerminalBroker(idle_marker="READY")

        with patch("clone_driver.terminal.subprocess.run", side_effect=fake_run):
            result = broker.send_keys("work", ["Down", "Enter"])

        self.assertEqual(result.status, "readback_failed")
        self.assertFalse(result.enter_sent)
        self.assertNotIn(["tmux", "send-keys", "-t", "%7", "Enter"], calls)

    def test_tmux_send_keys_sends_enter_after_readback_changes(self):
        calls = []
        captures = iter(["before", "after"])

        def fake_run(args, **kwargs):
            calls.append(args)
            if args[:4] == ["tmux", "display-message", "-p", "-t"]:
                return SimpleNamespace(returncode=0, stdout="%7\n", stderr="")
            if args[:2] == ["tmux", "capture-pane"]:
                return SimpleNamespace(returncode=0, stdout=next(captures), stderr="")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        broker = TmuxTerminalBroker(idle_marker="READY")

        with patch("clone_driver.terminal.subprocess.run", side_effect=fake_run):
            result = broker.send_keys("work", ["Down", "Enter"])

        self.assertEqual(result.status, "sent")
        self.assertTrue(result.enter_sent)
        self.assertIn(["tmux", "send-keys", "-t", "%7", "Down"], calls)
        self.assertIn(["tmux", "send-keys", "-t", "%7", "Enter"], calls)

    def test_tmux_send_returns_error_without_exception_when_tmux_command_fails(self):
        def fake_run(args, **kwargs):
            if args[:4] == ["tmux", "display-message", "-p", "-t"]:
                return SimpleNamespace(returncode=0, stdout="%7\n", stderr="")
            if args[:2] == ["tmux", "paste-buffer"]:
                raise subprocess.CalledProcessError(returncode=1, cmd=args, stderr="gone")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        broker = TmuxTerminalBroker(idle_marker="READY")

        with patch("clone_driver.terminal.subprocess.run", side_effect=fake_run):
            result = broker.send("work", "계속해.")

        self.assertEqual(result.status, "tmux_error")
        self.assertFalse(result.enter_sent)
        self.assertEqual(result.readback_status, "error")
        self.assertEqual(result.canonical_target, "%7")
