import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from clone_driver.cli import build_parser, main, rightseat_main


class TtyStringIO(io.StringIO):
    def isatty(self):
        return True


class CliTests(unittest.TestCase):
    def test_version_prints(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["--version"])
        self.assertEqual(code, 0)
        self.assertIn("clone-driver", out.getvalue())

    def test_rightseat_version_prints_public_name(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = rightseat_main(["--version"])

        self.assertEqual(code, 0)
        self.assertIn("rightseat", out.getvalue())

    def test_rightseat_help_shows_simple_controls_not_quick_regex(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = rightseat_main(["--help"])

        visible = out.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("rightseat off", visible)
        self.assertIn("rightseat pause", visible)
        self.assertIn("rightseat resume", visible)
        self.assertIn("rightseat status", visible)
        self.assertNotIn("--quick-regex", visible)

    def test_pyproject_exposes_rightseat_console_script(self):
        pyproject = Path("pyproject.toml").read_text(encoding="utf-8")

        self.assertIn('name = "rightseat"', pyproject)
        self.assertIn('rightseat = "clone_driver.cli:rightseat_entrypoint"', pyproject)

    def test_rightseat_does_not_auto_select_single_target_without_tty_choice(self):
        launched = []

        class FakeLauncher:
            def __init__(self, config):
                launched.append(config)

            def launch(self):
                raise AssertionError("rightseat should not launch without manual choice")

        target = SimpleNamespace(
            pane_id="%7",
            pane_ref="demo:0.0",
            command="codex",
            title="Codex",
            preview="질문: 계속할까요?",
            fingerprint="abc123",
            locked=False,
        )
        out = io.StringIO()

        with patch("clone_driver.cli.list_tmux_targets", return_value=[target]):
            with patch("clone_driver.cli.PairLauncher", FakeLauncher):
                with redirect_stdout(out):
                    code = rightseat_main([], input_stream=io.StringIO())

        self.assertEqual(code, 2)
        self.assertEqual(launched, [])
        visible = out.getvalue()
        self.assertIn("[1] demo", visible)
        self.assertIn("Run rightseat in a terminal", visible)

    def test_rightseat_manual_choice_single_target_uses_easy_defaults(self):
        launched = []

        class FakeLauncher:
            def __init__(self, config):
                launched.append(config)

            def launch(self):
                config = launched[-1]
                return SimpleNamespace(
                    status="started",
                    worker_target=config.target,
                    advisor_target="%8",
                    run_id=config.run_id,
                    ledger_path=config.ledger_path,
                    error="",
                )

        target = SimpleNamespace(
            pane_id="%7",
            pane_ref="demo:0.0",
            command="codex",
            title="Codex",
            preview="질문: 계속할까요?",
            fingerprint="abc123",
            locked=False,
        )
        out = io.StringIO()

        with patch("clone_driver.cli.list_tmux_targets", return_value=[target]):
            with patch("clone_driver.cli.PairLauncher", FakeLauncher):
                with patch("clone_driver.cli._stop_rightseat_for_worker"):
                    with patch("clone_driver.cli.show_tmux_pane", return_value=True):
                        with redirect_stdout(out):
                            code = rightseat_main([], input_stream=TtyStringIO("1\n"))

        self.assertEqual(code, 0)
        self.assertEqual(launched[0].target, "%7")
        self.assertIn("--allow-missing-contract", launched[0].attach_args)
        self.assertIn("--advisor-model", launched[0].attach_args)
        self.assertIn("gpt-5.4-mini", launched[0].attach_args)
        self.assertIn("--advisor-effort", launched[0].attach_args)
        self.assertIn("low", launched[0].attach_args)
        self.assertIn("--max-turns", launched[0].attach_args)
        self.assertIn("20", launched[0].attach_args)
        self.assertIn("--timeout", launched[0].attach_args)
        self.assertIn("3600.0", launched[0].attach_args)
        self.assertIn("started", out.getvalue())

    def test_rightseat_accepts_direct_target_without_go(self):
        launched = []

        class FakeLauncher:
            def __init__(self, config):
                launched.append(config)

            def launch(self):
                config = launched[-1]
                return SimpleNamespace(
                    status="started",
                    worker_target=config.target,
                    advisor_target="%9",
                    run_id=config.run_id,
                    ledger_path=config.ledger_path,
                    error="",
                )

        out = io.StringIO()
        with patch("clone_driver.cli.PairLauncher", FakeLauncher):
            with patch("clone_driver.cli._stop_rightseat_for_worker"):
                with patch("clone_driver.cli.show_tmux_pane", return_value=True) as show:
                    with redirect_stdout(out):
                        code = rightseat_main(["%3", "--backend", "fake"])

        self.assertEqual(code, 0)
        self.assertEqual(launched[0].target, "%3")
        self.assertIn("--backend", launched[0].attach_args)
        self.assertIn("fake", launched[0].attach_args)
        show.assert_called_once_with("%9")

    def test_rightseat_accepts_public_model_effort_and_log_aliases(self):
        launched = []

        class FakeLauncher:
            def __init__(self, config):
                launched.append(config)

            def launch(self):
                config = launched[-1]
                return SimpleNamespace(
                    status="started",
                    worker_target=config.target,
                    advisor_target="%9",
                    run_id=config.run_id,
                    ledger_path=config.ledger_path,
                    error="",
                )

        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "rightseat.jsonl"
            out = io.StringIO()
            with patch("clone_driver.cli.PairLauncher", FakeLauncher):
                with patch("clone_driver.cli._stop_rightseat_for_worker"):
                    with patch("clone_driver.cli.show_tmux_pane", return_value=True):
                        with redirect_stdout(out):
                            code = rightseat_main(
                                [
                                    "%3",
                                    "--backend",
                                    "codex",
                                    "--model",
                                    "gpt-5.4-mini",
                                    "--effort",
                                    "low",
                                    "--log",
                                    str(log_path),
                                ]
                            )

        self.assertEqual(code, 0)
        self.assertEqual(launched[0].ledger_path, log_path)
        self.assertIn("--advisor-model", launched[0].attach_args)
        self.assertIn("gpt-5.4-mini", launched[0].attach_args)
        self.assertIn("--advisor-effort", launched[0].attach_args)
        self.assertIn("low", launched[0].attach_args)

    def test_rightseat_log_accepts_public_log_alias(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "rightseat.jsonl"
            log_path.write_text('{"event":"demo","status":"ok"}\n', encoding="utf-8")
            out = io.StringIO()

            with redirect_stdout(out):
                code = rightseat_main(["log", "--log", str(log_path)])

        self.assertEqual(code, 0)
        self.assertIn("events=1", out.getvalue())

    def test_rightseat_targets_prints_friendly_choices(self):
        target = SimpleNamespace(
            pane_id="%152",
            pane_ref="worker1:0.0",
            command="node",
            title="elite-HP-ProDesk",
            preview="› Run /review on my current changes",
            fingerprint="abc123",
            locked=False,
        )
        out = io.StringIO()

        with patch("clone_driver.cli.list_tmux_targets", return_value=[target]):
            with redirect_stdout(out):
                code = rightseat_main(["targets"])

        visible = out.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("RightSeat worker choices", visible)
        self.assertIn("[1] worker1", visible)
        self.assertIn("app: node", visible)
        self.assertIn("pane: %152", visible)
        self.assertIn("run: rightseat %152", visible)
        self.assertNotIn("fingerprint=", visible)

    def test_rightseat_status_prints_simple_active_session(self):
        session = SimpleNamespace(
            run_id="pair-123",
            worker_target="%152",
            advisor_target="%153",
            ledger_path=Path("runtime/attach-runs/pair-123/ledger.jsonl"),
            control_path=Path("runtime/attach-runs/pair-123/control.json"),
            mode="auto",
            active=True,
        )
        out = io.StringIO()

        with patch("clone_driver.cli.list_rightseat_sessions", return_value=[session]):
            with redirect_stdout(out):
                code = rightseat_main(["status"])

        visible = out.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("RightSeat status", visible)
        self.assertIn("worker: %152", visible)
        self.assertIn("seat: %153", visible)
        self.assertIn("mode: auto", visible)
        self.assertIn("off: rightseat off", visible)

    def test_rightseat_pause_and_resume_update_only_control_state(self):
        session = SimpleNamespace(
            run_id="pair-123",
            worker_target="%152",
            advisor_target="%153",
            ledger_path=Path("runtime/attach-runs/pair-123/ledger.jsonl"),
            control_path=Path("runtime/attach-runs/pair-123/control.json"),
            mode="auto",
            active=True,
        )
        writes = []

        with patch("clone_driver.cli.list_rightseat_sessions", return_value=[session]):
            with patch("clone_driver.cli.write_control_state", side_effect=lambda path, mode: writes.append((path, mode))):
                self.assertEqual(rightseat_main(["pause"]), 0)
                self.assertEqual(rightseat_main(["resume"]), 0)

        self.assertEqual(
            writes,
            [
                (Path("runtime/attach-runs/pair-123/control.json"), "paused"),
                (Path("runtime/attach-runs/pair-123/control.json"), "auto"),
            ],
        )

    def test_rightseat_off_kills_only_seat_pane(self):
        session = SimpleNamespace(
            run_id="pair-123",
            worker_target="%152",
            advisor_target="%153",
            ledger_path=Path("runtime/attach-runs/pair-123/ledger.jsonl"),
            control_path=Path("runtime/attach-runs/pair-123/control.json"),
            mode="auto",
            active=True,
        )
        killed = []

        with patch("clone_driver.cli.list_rightseat_sessions", return_value=[session]):
            def fake_kill(target):
                killed.append(target)
                return True

            with patch("clone_driver.cli.kill_rightseat_pane", side_effect=fake_kill):
                code = rightseat_main(["off"])

        self.assertEqual(code, 0)
        self.assertEqual(killed, ["%153"])

    def test_rightseat_off_kills_all_seat_panes_without_touching_workers(self):
        sessions = [
            SimpleNamespace(
                run_id="pair-1",
                worker_target="%152",
                advisor_target="%153",
                ledger_path=Path("runtime/attach-runs/pair-1/ledger.jsonl"),
                control_path=Path("runtime/attach-runs/pair-1/control.json"),
                mode="auto",
                active=True,
            ),
            SimpleNamespace(
                run_id="pair-2",
                worker_target="%200",
                advisor_target="%201",
                ledger_path=Path("runtime/attach-runs/pair-2/ledger.jsonl"),
                control_path=Path("runtime/attach-runs/pair-2/control.json"),
                mode="auto",
                active=True,
            ),
        ]
        killed = []

        with patch("clone_driver.cli.list_rightseat_sessions", return_value=sessions):
            with patch("clone_driver.cli.kill_rightseat_pane", side_effect=lambda target: killed.append(target) or True):
                code = rightseat_main(["off"])

        self.assertEqual(code, 0)
        self.assertEqual(killed, ["%153", "%201"])

    def test_rightseat_reset_kills_all_seat_panes(self):
        session = SimpleNamespace(
            run_id="pair-1",
            worker_target="%152",
            advisor_target="%153",
            ledger_path=Path("runtime/attach-runs/pair-1/ledger.jsonl"),
            control_path=Path("runtime/attach-runs/pair-1/control.json"),
            mode="auto",
            active=True,
        )
        killed = []

        with patch("clone_driver.cli.list_rightseat_sessions", return_value=[session]):
            with patch("clone_driver.cli.kill_rightseat_pane", side_effect=lambda target: killed.append(target) or True):
                code = rightseat_main(["reset"])

        self.assertEqual(code, 0)
        self.assertEqual(killed, ["%153"])

    def test_packet_requires_contract_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            packet_path = Path(tmp) / "packet.json"
            code = main(
                [
                    "packet",
                    "--seed",
                    str(Path(tmp) / "missing-seed.md"),
                    "--wiw",
                    str(Path(tmp) / "missing-wiw.md"),
                    "--not-to-do",
                    str(Path(tmp) / "missing-not-to-do.md"),
                    "--final-artifact",
                    str(Path(tmp) / "missing-final.md"),
                    "--out",
                    str(packet_path),
                ]
            )
        self.assertEqual(code, 2)

    def test_packet_writes_verifier_packet(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed = root / "seed.md"
            wiw = root / "wiw.md"
            not_to_do = root / "not-to-do.md"
            final_artifact = root / "final.md"
            diff = root / "diff.txt"
            test_output = root / "test-output.txt"
            packet_path = root / "packet.json"
            for path, text in [
                (seed, "seed text"),
                (wiw, "wiw text"),
                (not_to_do, "never trust worker self-grading"),
                (final_artifact, "clone-driver packet"),
                (diff, "diff --git"),
                (test_output, "tests OK"),
            ]:
                path.write_text(text, encoding="utf-8")

            code = main(
                [
                    "packet",
                    "--seed",
                    str(seed),
                    "--wiw",
                    str(wiw),
                    "--not-to-do",
                    str(not_to_do),
                    "--final-artifact",
                    str(final_artifact),
                    "--diff",
                    str(diff),
                    "--test-output",
                    str(test_output),
                    "--out",
                    str(packet_path),
                ]
            )

            self.assertEqual(code, 0)
            packet = packet_path.read_text(encoding="utf-8")
            self.assertIn('"wiw": "wiw text"', packet)
            self.assertIn('"test_output": "tests OK"', packet)
            self.assertNotIn("worker_claim", packet)

    def test_packet_writes_manifest_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed = root / "seed.md"
            wiw = root / "wiw.md"
            not_to_do = root / "not-to-do.md"
            final_artifact = root / "final.md"
            git_status = root / "git-status.txt"
            untracked = root / "untracked.txt"
            test_stdout = root / "stdout.txt"
            test_stderr = root / "stderr.txt"
            manifest = root / "manifest.json"
            packet_path = root / "packet.json"
            for path, text in [
                (seed, "seed text"),
                (wiw, "wiw text"),
                (not_to_do, "never trust worker self-grading"),
                (final_artifact, "clone-driver packet"),
                (git_status, "?? example.txt"),
                (untracked, "example.txt"),
                (test_stdout, "OK"),
                (test_stderr, ""),
            ]:
                path.write_text(text, encoding="utf-8")
            manifest.write_text(
                json.dumps(
                    {
                        "git_status": str(git_status),
                        "untracked_files": str(untracked),
                        "test_stdout": str(test_stdout),
                        "test_stderr": str(test_stderr),
                        "test_exit_code": 0,
                    }
                ),
                encoding="utf-8",
            )

            code = main(
                [
                    "packet",
                    "--seed",
                    str(seed),
                    "--wiw",
                    str(wiw),
                    "--not-to-do",
                    str(not_to_do),
                    "--final-artifact",
                    str(final_artifact),
                    "--artifact-manifest",
                    str(manifest),
                    "--out",
                    str(packet_path),
                ]
            )

            self.assertEqual(code, 0)
            packet = packet_path.read_text(encoding="utf-8")
            self.assertIn('"git_status": "?? example.txt"', packet)
            self.assertIn('"untracked_files": "example.txt"', packet)
            self.assertIn('"test_exit_code": 0', packet)

    def test_collect_cli_writes_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp) / "repo"
            out_dir = Path(tmp) / "artifacts"
            workdir.mkdir()
            import subprocess

            subprocess.run(
                ["git", "init"],
                cwd=workdir,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            out = io.StringIO()

            with redirect_stdout(out):
                code = main(
                    [
                        "collect",
                        "--workdir",
                        str(workdir),
                        "--out-dir",
                        str(out_dir),
                        "--test-cmd",
                        f"{sys.executable} -c \"print('OK')\"",
                    ]
                )

            self.assertEqual(code, 0)
            manifest = Path(out.getvalue().strip())
            self.assertTrue(manifest.exists())
            self.assertEqual(json.loads(manifest.read_text(encoding="utf-8"))["test_exit_code"], 0)

    def test_nudge_parser_accepts_required_fields(self):
        args = build_parser().parse_args(
            [
                "nudge",
                "--session",
                "worker",
                "--message",
                "계속해.",
                "--ledger",
                "run.jsonl",
            ]
        )

        self.assertEqual(args.command, "nudge")
        self.assertEqual(args.session, "worker")
        self.assertEqual(args.message, "계속해.")
        self.assertEqual(args.ledger, "run.jsonl")

    def test_nudge_parser_accepts_idle_regex(self):
        args = build_parser().parse_args(
            [
                "nudge",
                "--session",
                "worker",
                "--message",
                "계속해.",
                "--ledger",
                "run.jsonl",
                "--idle-regex",
                "READY|review_waiting",
            ]
        )

        self.assertEqual(args.idle_regex, "READY|review_waiting")

    def test_gate_parser_accepts_idle_regex(self):
        args = build_parser().parse_args(
            [
                "gate",
                "--packet",
                "packet.json",
                "--ledger",
                "run.jsonl",
                "--verifier-cmd",
                "verifier",
                "--session",
                "worker",
                "--idle-regex",
                "READY|review_waiting",
            ]
        )

        self.assertEqual(args.idle_regex, "READY|review_waiting")

    def test_gate_with_fake_pass_writes_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            packet = Path(tmp) / "packet.json"
            ledger = Path(tmp) / "ledger.jsonl"
            packet.write_text(json.dumps({"force": "PASS"}), encoding="utf-8")
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

            self.assertEqual(code, 0)
            self.assertEqual(out.getvalue().strip(), "hold")
            self.assertIn('"verdict": "PASS"', ledger.read_text(encoding="utf-8"))
            self.assertIn('"action": "hold"', ledger.read_text(encoding="utf-8"))

    def test_gate_with_fake_pass_non_dry_run_does_not_send(self):
        with tempfile.TemporaryDirectory() as tmp:
            packet = Path(tmp) / "packet.json"
            ledger = Path(tmp) / "ledger.jsonl"
            packet.write_text(json.dumps({"force": "PASS"}), encoding="utf-8")

            class Terminal:
                def readiness(self, session):
                    return SimpleNamespace(
                        idle=True,
                        evidence="fake_idle",
                        canonical_target="work-pane",
                    )

                def is_idle(self, session):
                    return True

                def send(self, session, message):
                    raise AssertionError("PASS hold must not send to the worker")

            out = io.StringIO()

            with patch("clone_driver.cli.TmuxTerminalBroker", return_value=Terminal()):
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
                            "--session",
                            "work",
                        ]
                    )

            self.assertEqual(code, 0)
            self.assertEqual(out.getvalue().strip(), "hold")
            records = [
                json.loads(line)
                for line in ledger.read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(records[-1]["event"], "gate")
            self.assertEqual(records[-1]["action"], "hold")

    def test_gate_non_dry_run_stops_on_readback_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            packet = Path(tmp) / "packet.json"
            ledger = Path(tmp) / "ledger.jsonl"
            packet.write_text(json.dumps({"force": "FAIL"}), encoding="utf-8")

            class Terminal:
                def readiness(self, session):
                    return SimpleNamespace(
                        idle=True,
                        evidence="fake_idle",
                        canonical_target="work-pane",
                    )

                def is_idle(self, session):
                    return True

                def send(self, session, message):
                    return SimpleNamespace(
                        status="readback_failed",
                        enter_sent=False,
                        readback_status="missing",
                        canonical_target="work-pane",
                    )

            terminal = Terminal()
            out = io.StringIO()

            with patch("clone_driver.cli.TmuxTerminalBroker", return_value=terminal):
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
                            "--session",
                            "work",
                            "--idle-marker",
                            "READY",
                        ]
                    )

            self.assertEqual(code, 6)
            self.assertEqual(out.getvalue().strip(), "readback_failed")
            records = [
                json.loads(line)
                for line in ledger.read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(records[-1]["event"], "gate_injection")
            self.assertEqual(records[-1]["target"], "work")
            self.assertEqual(records[-1]["canonical_target"], "work-pane")
            self.assertEqual(records[-1]["readiness_evidence"], "fake_idle")
            self.assertEqual(records[-1]["readback_status"], "missing")
            self.assertFalse(records[-1]["enter_sent"])

    def test_gate_non_dry_run_without_idle_evidence_does_not_send(self):
        with tempfile.TemporaryDirectory() as tmp:
            packet = Path(tmp) / "packet.json"
            ledger = Path(tmp) / "ledger.jsonl"
            packet.write_text(json.dumps({"force": "FAIL"}), encoding="utf-8")

            class Terminal:
                def __init__(self):
                    self.sent = False

                def readiness(self, session):
                    return SimpleNamespace(
                        idle=False,
                        evidence="missing",
                        canonical_target="work-pane",
                    )

                def is_idle(self, session):
                    return False

                def send(self, session, message):
                    self.sent = True
                    return SimpleNamespace(
                        status="sent",
                        enter_sent=True,
                        readback_status="fake",
                        canonical_target="work-pane",
                    )

            terminal = Terminal()
            out = io.StringIO()

            with patch("clone_driver.cli.TmuxTerminalBroker", return_value=terminal):
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
                            "--session",
                            "work",
                        ]
                    )

            self.assertEqual(code, 3)
            self.assertEqual(out.getvalue().strip(), "not_idle")
            self.assertFalse(terminal.sent)
            records = [
                json.loads(line)
                for line in ledger.read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(records[-1]["event"], "gate_injection")
            self.assertEqual(records[-1]["status"], "not_idle")
            self.assertEqual(records[-1]["target"], "work")
            self.assertEqual(records[-1]["canonical_target"], "work-pane")
            self.assertEqual(records[-1]["readiness_evidence"], "missing")
            self.assertEqual(records[-1]["readback_status"], "not_attempted")
            self.assertFalse(records[-1]["enter_sent"])

    def test_gate_invalid_verifier_output_writes_clean_stop_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            packet = Path(tmp) / "packet.json"
            ledger = Path(tmp) / "ledger.jsonl"
            packet.write_text(json.dumps({"force": "BROKEN"}), encoding="utf-8")
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
                        f"{sys.executable} -c \"print('not json')\"",
                        "--dry-run",
                    ]
                )

            self.assertEqual(code, 7)
            self.assertEqual(out.getvalue().strip(), "invalid_verdict")
            record = json.loads(ledger.read_text(encoding="utf-8"))
            self.assertEqual(record["event"], "invalid_verdict")
            self.assertIn("error", record)

    def test_gate_missing_verifier_executable_writes_clean_stop_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            packet = Path(tmp) / "packet.json"
            ledger = Path(tmp) / "ledger.jsonl"
            packet.write_text(json.dumps({"force": "PASS"}), encoding="utf-8")
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
                        "/definitely/missing/clone-driver-verifier",
                        "--dry-run",
                    ]
                )

            self.assertEqual(code, 7)
            self.assertEqual(out.getvalue().strip(), "verifier_error")
            record = json.loads(ledger.read_text(encoding="utf-8"))
            self.assertEqual(record["event"], "verifier_error")
            self.assertIn("error", record)

    def test_run_starts_session_and_writes_target_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "ledger.jsonl"
            manager = SimpleNamespace(
                start=lambda session, command: SimpleNamespace(
                    session=session,
                    target="work-pane",
                    canonical_target="work-pane",
                )
            )
            out = io.StringIO()

            with patch("clone_driver.cli.TmuxSessionManager", return_value=manager):
                with redirect_stdout(out):
                    code = main(
                        [
                            "run",
                            "--session",
                            "work",
                            "--ledger",
                            str(ledger),
                            "--",
                            "python",
                            "-q",
                        ]
                    )

            self.assertEqual(code, 0)
            self.assertEqual(out.getvalue().strip(), "work-pane")
            record = json.loads(ledger.read_text(encoding="utf-8"))
            self.assertEqual(record["event"], "session_started")
            self.assertEqual(record["session"], "work")
            self.assertEqual(record["target"], "work-pane")
            self.assertEqual(record["canonical_target"], "work-pane")

    def test_probe_rejects_unsupported_target_and_writes_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "ledger.jsonl"
            manager = SimpleNamespace(
                probe=lambda target: SimpleNamespace(
                    target=target,
                    canonical_target="",
                    available=False,
                    stdout="",
                    stderr="missing",
                )
            )
            out = io.StringIO()

            with patch("clone_driver.cli.TmuxSessionManager", return_value=manager):
                with redirect_stdout(out):
                    code = main(["probe", "--target", "missing", "--ledger", str(ledger)])

            self.assertEqual(code, 5)
            self.assertEqual(out.getvalue().strip(), "unsupported_target")
            log = ledger.read_text(encoding="utf-8")
            self.assertIn('"event": "session_probe"', log)
            self.assertIn('"available": false', log)
            self.assertIn('"canonical_target": ""', log)

    def test_ledger_command_prints_human_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "ledger.jsonl"
            ledger.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "event": "nudge",
                                "status": "sent",
                                "target": "work",
                                "canonical_target": "%7",
                                "readiness_evidence": "idle_marker:READY",
                                "readback_status": "matched",
                                "enter_sent": True,
                            }
                        ),
                        json.dumps(
                            {
                                "event": "gate",
                                "verdict": "FAIL",
                                "action": "inject",
                                "reason": "missing test",
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            out = io.StringIO()

            with redirect_stdout(out):
                code = main(["ledger", "--ledger", str(ledger)])

            self.assertEqual(code, 0)
            summary = out.getvalue()
            self.assertIn("events=2", summary)
            self.assertIn("nudge status=sent target=work canonical=%7", summary)
            self.assertIn("gate verdict=FAIL action=inject reason=missing test", summary)

    def test_ledger_command_prints_advisor_loop_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "ledger.jsonl"
            ledger.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "event": "advisor_turn",
                                "turn_index": 1,
                                "question": "사람들과 있을 때 에너지가 생기나요?",
                                "action": "ANSWER",
                                "confidence": "high",
                                "answer_preview": "네, 대체로 그렇습니다.",
                                "injected": True,
                            },
                            ensure_ascii=False,
                        ),
                        json.dumps(
                            {
                                "event": "advisor_escalated",
                                "question": "FORCE_ESCALATE",
                                "reason": "manual review needed",
                                "confidence": "low",
                            },
                            ensure_ascii=False,
                        ),
                        json.dumps(
                            {
                                "event": "supervise_finished",
                                "status": "completed",
                                "turns": 3,
                            },
                            ensure_ascii=False,
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            out = io.StringIO()

            with redirect_stdout(out):
                code = main(["ledger", "--ledger", str(ledger), "--tail", "5"])

            self.assertEqual(code, 0)
            summary = out.getvalue()
            self.assertIn(
                "advisor_turn turn=1 action=ANSWER confidence=high injected=True",
                summary,
            )
            self.assertIn("question=사람들과 있을 때 에너지가 생기나요?", summary)
            self.assertIn(
                "advisor_escalated confidence=low question=FORCE_ESCALATE",
                summary,
            )
            self.assertIn("reason=manual review needed", summary)
            self.assertIn("supervise_finished status=completed turns=3", summary)

    def test_ledger_command_prints_attach_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "ledger.jsonl"
            ledger.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "event": "attach_turn",
                                "target": "cd-visible",
                                "canonical_target": "%7",
                                "turn_index": 1,
                                "question": "user는 어떤 답변을 선호하나요?",
                                "action": "ANSWER",
                                "confidence": "high",
                                "readback_status": "matched",
                                "enter_sent": True,
                                "injected": True,
                            },
                            ensure_ascii=False,
                        ),
                        json.dumps(
                            {
                                "event": "attach_finished",
                                "target": "cd-visible",
                                "status": "completed",
                                "turns": 1,
                            },
                            ensure_ascii=False,
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            out = io.StringIO()

            with redirect_stdout(out):
                code = main(["ledger", "--ledger", str(ledger), "--tail", "5"])

            self.assertEqual(code, 0)
            summary = out.getvalue()
            self.assertIn("attach_turn target=cd-visible canonical=%7", summary)
            self.assertIn("injected=True", summary)
            self.assertIn(
                "attach_finished target=cd-visible status=completed turns=1",
                summary,
            )

    def test_attach_parser_defaults_to_codex_backend(self):
        args = build_parser().parse_args(
            [
                "attach",
                "--target",
                "%7",
            ]
        )

        self.assertEqual(args.command, "attach")
        self.assertEqual(args.target, "%7")
        self.assertEqual(args.backend, "codex")
        self.assertEqual(args.mode, "auto")

    def test_fake_backend_does_not_auto_allow_missing_contract(self):
        # E-2: fake backend must not automatically bypass the task contract.
        from clone_driver import cli

        src = Path(cli.__file__).read_text(encoding="utf-8")
        normalized = src.replace("'", '"')

        self.assertNotIn(
            'backend.name == "fake"',
            normalized,
            "fake backend must not automatically enable allow_missing_contract (E-2)",
        )

    def test_attach_cli_runs_fake_backend_against_fake_terminal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = Path(tmp) / "attach-ledger.jsonl"
            seed = root / "seed.md"
            wiw = root / "wiw.md"
            not_to_do = root / "not-to-do.md"
            final = root / "final.md"
            for path, text in [
                (seed, "answer the visible prompt"),
                (wiw, "user answer preference question"),
                (not_to_do, "do not trust worker self-grading"),
                (final, "visible answer submitted"),
            ]:
                path.write_text(text, encoding="utf-8")

            class Terminal:
                def __init__(self):
                    self.sent = []

                def capture(self, session):
                    return SimpleNamespace(
                        status="captured",
                        transcript="READY\n질문: user는 어떤 답변을 선호하나요?\n",
                        canonical_target="%7",
                        error="",
                    )

                def readiness(self, session):
                    return SimpleNamespace(
                        idle=True,
                        evidence="question_detected",
                        canonical_target="%7",
                    )

                def is_idle(self, session):
                    return True

                def send(self, session, message):
                    self.sent.append((session, message))
                    return SimpleNamespace(
                        status="sent",
                        enter_sent=True,
                        readback_status="matched",
                        canonical_target=session,
                    )

                def send_keys(self, session, keys):
                    self.sent.append((session, " ".join(keys)))
                    return SimpleNamespace(
                        status="sent",
                        enter_sent="Enter" in keys,
                        readback_status="key_sequence_sent",
                        canonical_target=session,
                    )

            terminal = Terminal()
            out = io.StringIO()

            with patch("clone_driver.cli.TmuxTerminalBroker", return_value=terminal):
                with redirect_stdout(out):
                    code = main(
                        [
                            "attach",
                            "--target",
                            "%7",
                            "--backend",
                            "fake",
                            "--ledger",
                            str(ledger),
                            "--seed",
                            str(seed),
                            "--wiw",
                            str(wiw),
                            "--not-to-do",
                            str(not_to_do),
                            "--final-artifact",
                            str(final),
                            "--max-turns",
                            "1",
                            "--timeout",
                            "1",
                            "--poll-interval",
                            "0.01",
                        ]
                    )

            self.assertEqual(code, 0)
            self.assertIn("completed", out.getvalue())
            self.assertEqual(terminal.sent[0][0], "%7")
            self.assertIn("injected=True", out.getvalue())

    def test_attach_parser_accepts_model_effort_and_quick_reply(self):
        args = build_parser().parse_args(
            [
                "attach",
                "--target",
                "%7",
                "--backend",
                "codex",
                "--advisor-model",
                "gpt-5.4-mini",
                "--advisor-effort",
                "low",
                "--quick-regex",
                "계속|진행",
                "--quick-reply",
                "진행해.",
                "--mode",
                "auto",
            ]
        )

        self.assertEqual(args.advisor_model, "gpt-5.4-mini")
        self.assertEqual(args.advisor_effort, "low")
        self.assertEqual(args.quick_regex, "계속|진행")
        self.assertEqual(args.quick_reply, "진행해.")

    def test_attach_parser_accepts_v4_runtime_options(self):
        args = build_parser().parse_args(
            [
                "attach",
                "--target",
                "%7",
                "--config",
                "docs/examples/attach-codex-low.toml",
                "--advisor-display",
                "tmux",
                "--advisor-display-target",
                "clone-advisor",
                "--advisor-transcript",
                "runtime/run/advisor-transcript.jsonl",
                "--quick-keys",
                "Enter",
                "--confirm-timeout",
                "12",
                "--run-id",
                "night-run",
                "--target-fingerprint",
                "abc123",
                "--advisor-timeout",
                "30",
                "--seed",
                "seed.md",
                "--wiw",
                "wiw.md",
                "--not-to-do",
                "not-to-do.md",
                "--final-artifact",
                "final.md",
                "--redact-regex",
                "TOKEN=[^ ]+",
            ]
        )

        self.assertEqual(args.config, "docs/examples/attach-codex-low.toml")
        self.assertEqual(args.advisor_display, "tmux")
        self.assertEqual(args.advisor_display_target, "clone-advisor")
        self.assertEqual(args.quick_keys, ["Enter"])
        self.assertEqual(args.confirm_timeout, 12)
        self.assertEqual(args.run_id, "night-run")
        self.assertEqual(args.target_fingerprint, "abc123")
        self.assertEqual(args.advisor_timeout, 30)
        self.assertEqual(args.seed, "seed.md")
        self.assertEqual(args.redact_regex, ["TOKEN=[^ ]+"])

    def test_targets_runs_control_and_doctor_parsers_exist(self):
        self.assertEqual(build_parser().parse_args(["targets"]).command, "targets")
        self.assertEqual(build_parser().parse_args(["runs"]).command, "runs")
        control = build_parser().parse_args(
            ["control", "--run-id", "night-run", "--mode", "paused"]
        )
        self.assertEqual(control.mode, "paused")
        doctor = build_parser().parse_args(
            [
                "doctor",
                "--backend",
                "codex",
                "--advisor-model",
                "gpt-5.4-mini",
                "--advisor-effort",
                "low",
            ]
        )
        self.assertEqual(doctor.command, "doctor")
        self.assertEqual(doctor.backend, "codex")

    def test_pair_parser_accepts_visible_advisor_options(self):
        args = build_parser().parse_args(
            [
                "pair",
                "--target",
                "%7",
                "--backend",
                "fake",
                "--quick-regex",
                "계속|진행",
                "--quick-reply",
                "진행해.",
                "--mode",
                "auto",
                "--allow-missing-contract",
                "--max-turns",
                "1",
            ]
        )

        self.assertEqual(args.command, "pair")
        self.assertEqual(args.target, "%7")
        self.assertEqual(args.backend, "fake")
        self.assertEqual(args.quick_reply, "진행해.")

    def test_pair_cli_launches_visible_advisor_pane(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "pair-ledger.jsonl"
            out = io.StringIO()

            with patch("clone_driver.cli.PairLauncher") as launcher:
                launcher.return_value.launch.return_value = SimpleNamespace(
                    status="started",
                    worker_target="%7",
                    advisor_target="%8",
                    run_id="pair-test",
                    ledger_path=ledger,
                    error="",
                )
                with redirect_stdout(out):
                    code = main(
                        [
                            "pair",
                            "--target",
                            "%7",
                            "--backend",
                            "fake",
                            "--ledger",
                            str(ledger),
                            "--run-id",
                            "pair-test",
                            "--allow-missing-contract",
                        ]
                    )

            self.assertEqual(code, 0)
            text = out.getvalue()
            self.assertIn("started", text)
            self.assertIn("worker=%7", text)
            self.assertIn("advisor=%8", text)
            self.assertIn("run_id=pair-test", text)
            self.assertIn(f"log={ledger}", text)

    def test_supervise_parser_accepts_required_fields(self):
        args = build_parser().parse_args(
            [
                "supervise",
                "--ledger",
                "runtime/mbti-ledger.jsonl",
                "--profile",
                "profile.md",
                "--answer-policy",
                "policy.md",
                "--advisor-cmd",
                "python3 tests/fixtures/fake_advisor.py",
                "--ready-regex",
                "MBTI_READY|질문",
                "--question-regex",
                "질문[:：]\\s*(.+)",
                "--max-turns",
                "5",
                "--",
                "python3",
                "tests/fixtures/fake_mbti_worker.py",
            ]
        )

        self.assertEqual(args.command, "supervise")
        self.assertEqual(args.ledger, "runtime/mbti-ledger.jsonl")
        self.assertEqual(args.max_turns, 5)
        self.assertEqual(args.worker_command[-1], "tests/fixtures/fake_mbti_worker.py")

    def test_supervise_cli_runs_fake_mbti_worker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = root / "ledger.jsonl"
            profile = root / "profile.md"
            policy = root / "policy.md"
            profile.write_text("user prefers pragmatic direct answers.", encoding="utf-8")
            policy.write_text("Answer in Korean as user. Keep answers short.", encoding="utf-8")
            out = io.StringIO()

            with redirect_stdout(out):
                code = main(
                    [
                        "supervise",
                        "--ledger",
                        str(ledger),
                        "--profile",
                        str(profile),
                        "--answer-policy",
                        str(policy),
                        "--advisor-cmd",
                        f"{sys.executable} tests/fixtures/fake_advisor.py",
                        "--ready-regex",
                        "MBTI_READY|질문|Q[0-9]+:",
                        "--question-regex",
                        r"질문[:：]\s*(.+)|Q[0-9]+[:：]\s*(.+)|([^\n]+\?)",
                        "--max-turns",
                        "5",
                        "--",
                        sys.executable,
                        "tests/fixtures/fake_mbti_worker.py",
                    ]
                )

            self.assertEqual(code, 0)
            self.assertEqual(out.getvalue().strip(), "completed")
            self.assertIn('"event": "advisor_turn"', ledger.read_text(encoding="utf-8"))

    def test_try_cli_runs_single_command_demo(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "try-ledger.jsonl"
            out = io.StringIO()

            with redirect_stdout(out):
                code = main(["try", "--ledger", str(ledger)])

            self.assertEqual(code, 0)
            output = out.getvalue()
            self.assertIn("completed", output)
            self.assertIn(f"ledger={ledger}", output)
            self.assertIn("injected=True", output)

    def test_drive_parser_defaults_to_codex_backend(self):
        args = build_parser().parse_args(
            [
                "drive",
                "--",
                "codex",
                "Ask one question.",
            ]
        )

        self.assertEqual(args.command, "drive")
        self.assertEqual(args.backend, "codex")
        self.assertEqual(args.worker_command[-1], "Ask one question.")

    def test_try_parser_accepts_codex_backend(self):
        args = build_parser().parse_args(["try", "--backend", "codex"])

        self.assertEqual(args.command, "try")
        self.assertEqual(args.backend, "codex")

    def test_drive_cli_runs_fake_backend_worker_with_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            worker = root / "worker.py"
            ledger = root / "drive-ledger.jsonl"
            worker.write_text(
                "print('READY', flush=True)\n"
                "print('질문: user는 어떤 답변을 선호하나요?', flush=True)\n"
                "answer = input()\n"
                "print('worker_received=' + answer, flush=True)\n",
                encoding="utf-8",
            )
            out = io.StringIO()

            with redirect_stdout(out):
                code = main(
                    [
                        "drive",
                        "--backend",
                        "fake",
                        "--ledger",
                        str(ledger),
                        "--",
                        sys.executable,
                        str(worker),
                    ]
                )

            self.assertEqual(code, 0)
            output = out.getvalue()
            self.assertIn("completed", output)
            self.assertIn("advisor_turn turn=1", output)
            self.assertIn("injected=True", output)
