import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from clone_driver.target_registry import (
    TargetLock,
    default_run_paths,
    fingerprint_transcript,
    list_tmux_targets,
    show_tmux_pane,
)


class TargetRegistryTests(unittest.TestCase):
    def test_fingerprint_is_stable_and_short(self):
        self.assertEqual(
            fingerprint_transcript("READY\n질문: 계속할까요?\n"),
            fingerprint_transcript("READY\n질문: 계속할까요?\n"),
        )
        self.assertEqual(len(fingerprint_transcript("abc")), 16)

    def test_list_tmux_targets_returns_preview_and_fingerprint(self):
        output = "%7\twork:0.0\tcodex\tCodex Worker\n%8\tops:0.0\tbash\tShell\n"

        def fake_run(args, **kwargs):
            if args[:3] == ["tmux", "list-panes", "-a"]:
                return SimpleNamespace(returncode=0, stdout=output, stderr="")
            if args[:2] == ["tmux", "capture-pane"]:
                target = args[-1]
                return SimpleNamespace(returncode=0, stdout=f"READY from {target}\n", stderr="")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        with patch("clone_driver.target_registry.subprocess.run", side_effect=fake_run):
            targets = list_tmux_targets()

        self.assertEqual(targets[0].pane_id, "%7")
        self.assertEqual(targets[0].pane_ref, "work:0.0")
        self.assertEqual(targets[0].command, "codex")
        self.assertIn("READY", targets[0].preview)
        self.assertEqual(len(targets[0].fingerprint), 16)

    def test_list_tmux_targets_hides_rightseat_seat_panes(self):
        output = "%7\tworker1:0.0\tcodex\tCodex Worker\n%8\tworker1:0.1\tbash\tRightSeat\n"

        def fake_run(args, **kwargs):
            if args[:3] == ["tmux", "list-panes", "-a"]:
                return SimpleNamespace(returncode=0, stdout=output, stderr="")
            if args[:2] == ["tmux", "capture-pane"] and args[-1] == "%8":
                return SimpleNamespace(
                    returncode=0,
                    stdout="RightSeat ON\n\nworker: %7\nstate: watching\n",
                    stderr="",
                )
            if args[:2] == ["tmux", "capture-pane"]:
                return SimpleNamespace(returncode=0, stdout="› Run /review\n", stderr="")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        with patch("clone_driver.target_registry.subprocess.run", side_effect=fake_run):
            targets = list_tmux_targets()

        self.assertEqual([target.pane_id for target in targets], ["%7"])

    def test_list_tmux_targets_hides_advisor_targets_from_active_sessions(self):
        output = "%7\tworker1:0.0\tcodex\tCodex Worker\n%8\tworker1:0.1\tbash\tShell\n"

        def fake_run(args, **kwargs):
            if args[:3] == ["tmux", "list-panes", "-a"]:
                return SimpleNamespace(returncode=0, stdout=output, stderr="")
            if args[:2] == ["tmux", "capture-pane"]:
                return SimpleNamespace(returncode=0, stdout="", stderr="")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        active_seat = SimpleNamespace(advisor_target="%8")

        with patch("clone_driver.target_registry.subprocess.run", side_effect=fake_run):
            with patch("clone_driver.target_registry.list_rightseat_sessions", return_value=[active_seat]):
                targets = list_tmux_targets()

        self.assertEqual([target.pane_id for target in targets], ["%7"])

    def test_list_tmux_targets_hides_reserved_service_channel_panes(self):
        output = (
            "%0\tagent-discord:0.0\tclaude\tService Agent\n"
            "%152\tworker1:0.0\tcodex\tCodex Worker\n"
        )

        def fake_run(args, **kwargs):
            if args[:3] == ["tmux", "list-panes", "-a"]:
                return SimpleNamespace(returncode=0, stdout=output, stderr="")
            if args[:2] == ["tmux", "capture-pane"] and args[-1] == "%0":
                return SimpleNamespace(
                    returncode=0,
                    stdout="⏵⏵ bypass permissions on · for agents\n",
                    stderr="",
                )
            if args[:2] == ["tmux", "capture-pane"]:
                return SimpleNamespace(returncode=0, stdout="› Implement feature\n", stderr="")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        with patch("clone_driver.target_registry.subprocess.run", side_effect=fake_run):
            targets = list_tmux_targets()

        self.assertEqual([target.pane_id for target in targets], ["%152"])

    def test_show_tmux_pane_attaches_when_called_outside_tmux(self):
        calls = []

        def fake_run(args, **kwargs):
            calls.append(list(args))
            if args[:4] == ["tmux", "display-message", "-p", "-t"]:
                return SimpleNamespace(returncode=0, stdout="worker1\t0\t%153\n", stderr="")
            if args[:2] == ["tmux", "attach-session"]:
                return SimpleNamespace(returncode=0, stdout="", stderr="")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        with patch("clone_driver.target_registry.subprocess.run", side_effect=fake_run):
            with patch.dict("clone_driver.target_registry.os.environ", {}, clear=True):
                self.assertTrue(show_tmux_pane("%153"))

        self.assertIn(["tmux", "attach-session", "-t", "worker1:0"], calls)

    def test_show_tmux_pane_switches_client_when_called_inside_tmux(self):
        calls = []

        def fake_run(args, **kwargs):
            calls.append(list(args))
            if args[:4] == ["tmux", "display-message", "-p", "-t"]:
                return SimpleNamespace(returncode=0, stdout="worker1\t0\t%153\n", stderr="")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        with patch("clone_driver.target_registry.subprocess.run", side_effect=fake_run):
            with patch.dict("clone_driver.target_registry.os.environ", {"TMUX": "/tmp/tmux"}):
                self.assertTrue(show_tmux_pane("%153"))

        self.assertIn(["tmux", "switch-client", "-t", "worker1:0"], calls)
        self.assertIn(["tmux", "select-pane", "-t", "%153"], calls)

    def test_target_lock_blocks_duplicate_driver(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock = TargetLock(Path(tmp), "%7", run_id="run-a")

            self.assertTrue(lock.acquire())
            self.assertFalse(TargetLock(Path(tmp), "%7", run_id="run-b").acquire())

    def test_default_run_paths_are_unique(self):
        first = default_run_paths("run-a")
        second = default_run_paths("run-b")

        self.assertNotEqual(first.ledger_path, second.ledger_path)
        self.assertIn("run-a", str(first.ledger_path))
        self.assertIn("run-b", str(second.ledger_path))


if __name__ == "__main__":
    unittest.main()
