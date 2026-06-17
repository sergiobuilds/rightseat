import unittest

from clone_driver.session import CommandResult, TmuxSessionManager


class FakeRunner:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def __call__(self, args, **kwargs):
        self.calls.append(args)
        return self.results.pop(0)


class SessionManagerTests(unittest.TestCase):
    def test_start_creates_tmux_session_and_returns_target(self):
        runner = FakeRunner(
            [
                CommandResult(returncode=0, stdout="", stderr=""),
                CommandResult(returncode=0, stdout="%7\n", stderr=""),
            ]
        )
        manager = TmuxSessionManager(run_command=runner)

        target = manager.start(session="work", command=["python", "-q"])

        self.assertEqual(target.session, "work")
        self.assertEqual(target.target, "%7")
        self.assertEqual(target.canonical_target, "%7")
        self.assertEqual(runner.calls[0][:5], ["tmux", "new-session", "-d", "-s", "work"])
        self.assertEqual(
            runner.calls[1],
            ["tmux", "display-message", "-p", "-t", "work", "#{pane_id}"],
        )

    def test_probe_rejects_missing_target(self):
        runner = FakeRunner([CommandResult(returncode=1, stdout="", stderr="missing")])
        manager = TmuxSessionManager(run_command=runner)

        probe = manager.probe(target="missing")

        self.assertFalse(probe.available)
        self.assertIn("missing", probe.stderr)
        self.assertEqual(probe.canonical_target, "")
        self.assertEqual(
            runner.calls,
            [["tmux", "display-message", "-p", "-t", "missing", "#{pane_id}"]],
        )

    def test_probe_canonicalizes_target_then_captures_pane(self):
        runner = FakeRunner(
            [
                CommandResult(returncode=0, stdout="%7\n", stderr=""),
                CommandResult(returncode=0, stdout="READY", stderr=""),
            ]
        )
        manager = TmuxSessionManager(run_command=runner)

        probe = manager.probe(target="work")

        self.assertTrue(probe.available)
        self.assertEqual(probe.canonical_target, "%7")
        self.assertEqual(probe.stdout, "READY")
        self.assertEqual(
            runner.calls,
            [
                ["tmux", "display-message", "-p", "-t", "work", "#{pane_id}"],
                ["tmux", "capture-pane", "-pt", "%7"],
            ],
        )
