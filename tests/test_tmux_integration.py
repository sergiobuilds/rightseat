import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from pathlib import Path

from clone_driver.ledger import JsonlLedger
from clone_driver.ledger import read_jsonl_records
from clone_driver.session import TmuxSessionManager
from clone_driver.terminal import NudgeRunner, TmuxTerminalBroker


def write_contract(root: Path) -> tuple[Path, Path, Path, Path]:
    seed = root / "seed.md"
    wiw = root / "wiw.md"
    not_to_do = root / "not-to-do.md"
    final = root / "final.md"
    for path, text in [
        (seed, "answer only the current live prompt"),
        (wiw, "visible worker receives the advisor answer"),
        (not_to_do, "do not trust worker self-grading"),
        (final, "worker receives one stable answer"),
    ]:
        path.write_text(text, encoding="utf-8")
    return seed, wiw, not_to_do, final


@unittest.skipIf(shutil.which("tmux") is None, "tmux is not installed")
class TmuxIntegrationTests(unittest.TestCase):
    def test_run_probe_readback_and_enter(self):
        session = f"clone-driver-test-{uuid.uuid4().hex[:8]}"
        worker_script = (
            "import select, sys, time; "
            "print('READY', flush=True); "
            "ready, _, _ = select.select([sys.stdin], [], [], 5); "
            "line = sys.stdin.readline() if ready else ''; "
            "print(line.strip(), flush=True); "
            "time.sleep(5)"
        )
        manager = TmuxSessionManager()
        target = manager.start(
            session=session,
            command=[sys.executable, "-c", worker_script],
        )
        time.sleep(0.5)
        probe = manager.probe(target=target.target)
        self.assertTrue(probe.available)

        with tempfile.TemporaryDirectory() as tmp:
            runner = NudgeRunner(
                terminal=TmuxTerminalBroker(idle_marker="READY"),
                ledger=JsonlLedger(Path(tmp) / "ledger.jsonl"),
            )
            result = runner.run(session=target.target, message="clone-driver-ok")
            self.assertEqual(result["status"], "sent")
            self.assertTrue(result["enter_sent"])
            self.assertEqual(result["readback_status"], "matched")
            time.sleep(0.5)
            consumed = manager.probe(target=target.target)
            self.assertIn("clone-driver-ok", consumed.stdout)

    def test_attach_reads_visible_tmux_question_and_enters_answer(self):
        from clone_driver.attach import AttachConfig, AttachLoop

        session = f"clone-driver-attach-{uuid.uuid4().hex[:8]}"
        worker_script = (
            "import select, sys, time; "
            "print('READY', flush=True); "
            "print('질문: user는 어떤 답변을 선호하나요?', flush=True); "
            "ready, _, _ = select.select([sys.stdin], [], [], 20); "
            "line = sys.stdin.readline().strip() if ready else ''; "
            "print('worker_received=' + line, flush=True); "
            "time.sleep(5)"
        )
        manager = TmuxSessionManager()
        target = manager.start(
            session=session,
            command=[sys.executable, "-c", worker_script],
        )
        time.sleep(0.5)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = root / "ledger.jsonl"
            profile = root / "profile.md"
            policy = root / "policy.md"
            seed, wiw, not_to_do, final = write_contract(root)
            profile.write_text(
                "user prefers direct evidence-oriented answers.",
                encoding="utf-8",
            )
            policy.write_text("Answer in Korean. Keep it short.", encoding="utf-8")
            config = AttachConfig(
                target=target.target,
                advisor_command=[sys.executable, "-m", "clone_driver.fake_advisor"],
                ledger_path=ledger,
                profile_path=profile,
                answer_policy_path=policy,
                question_regex=r"질문[:：]\s*(.+)|([^\n]+\?)",
                seed_path=seed,
                wiw_path=wiw,
                not_to_do_path=not_to_do,
                final_artifact_path=final,
                lock_root=root / "locks",
                max_turns=1,
                poll_interval_seconds=0.1,
                timeout_seconds=5.0,
            )

            result = AttachLoop(config).run()

            self.assertEqual(result["status"], "completed")
            time.sleep(0.5)
            consumed = manager.probe(target=target.target)
            self.assertIn("worker_received=", consumed.stdout)
            self.assertIn("user는", consumed.stdout)
            records = read_jsonl_records(ledger)
            turn = [record for record in records if record["event"] == "attach_turn"][0]
            self.assertTrue(turn["injected"])
            self.assertTrue(turn["enter_sent"])

    def test_attach_quick_rule_does_not_type_choice_in_visible_tmux_pane(self):
        from clone_driver.attach import AttachConfig, AttachLoop

        session = f"clone-driver-choice-{uuid.uuid4().hex[:8]}"
        worker_script = (
            "import select, sys, time; "
            "print('READY', flush=True); "
            "print('선택하세요', flush=True); "
            "print('1) 진행', flush=True); "
            "print('2) 중단', flush=True); "
            "print('번호:', flush=True); "
            "ready, _, _ = select.select([sys.stdin], [], [], 20); "
            "line = sys.stdin.readline().strip() if ready else ''; "
            "print('worker_received=' + line, flush=True); "
            "time.sleep(5)"
        )
        manager = TmuxSessionManager()
        target = manager.start(
            session=session,
            command=[sys.executable, "-c", worker_script],
        )
        time.sleep(0.5)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = root / "profile.md"
            policy = root / "policy.md"
            profile.write_text("profile", encoding="utf-8")
            policy.write_text("policy", encoding="utf-8")
            config = AttachConfig(
                target=target.target,
                advisor_command=[sys.executable, "-m", "clone_driver.fake_advisor"],
                ledger_path=root / "ledger.jsonl",
                profile_path=profile,
                answer_policy_path=policy,
                question_regex=r"질문[:：]\s*(.+)",
                quick_regex=r"1\)|2\)|번호",
                quick_reply="1",
                lock_root=root / "locks",
                max_turns=1,
                poll_interval_seconds=0.1,
                timeout_seconds=5.0,
            )

            result = AttachLoop(config).run()

            self.assertEqual(result["status"], "timeout")
            time.sleep(0.5)
            consumed = manager.probe(target=target.target)
            self.assertNotIn("worker_received=1", consumed.stdout)
            records = read_jsonl_records(root / "ledger.jsonl")
            self.assertFalse(any(record["event"] == "attach_turn" for record in records))

    def test_attach_enter_only_quick_key_does_not_submit_visible_tmux_pane(self):
        from clone_driver.attach import AttachConfig, AttachLoop

        session = f"clone-driver-enter-{uuid.uuid4().hex[:8]}"
        worker_script = (
            "import select, sys, time; "
            "print('READY', flush=True); "
            "print('Press Enter to continue', flush=True); "
            "ready, _, _ = select.select([sys.stdin], [], [], 20); "
            "line = sys.stdin.readline().strip() if ready else 'timeout'; "
            "print('worker_received=' + line, flush=True); "
            "time.sleep(5)"
        )
        manager = TmuxSessionManager()
        target = manager.start(
            session=session,
            command=[sys.executable, "-c", worker_script],
        )
        time.sleep(0.5)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = root / "profile.md"
            policy = root / "policy.md"
            profile.write_text("profile", encoding="utf-8")
            policy.write_text("policy", encoding="utf-8")
            config = AttachConfig(
                target=target.target,
                advisor_command=[sys.executable, "-m", "clone_driver.fake_advisor"],
                ledger_path=root / "ledger.jsonl",
                profile_path=profile,
                answer_policy_path=policy,
                question_regex=r"질문[:：]\s*(.+)",
                quick_regex="Press Enter",
                quick_keys=["Enter"],
                lock_root=root / "locks",
                max_turns=1,
                poll_interval_seconds=0.1,
                timeout_seconds=5.0,
            )

            result = AttachLoop(config).run()

            self.assertEqual(result["status"], "timeout")
            time.sleep(0.5)
            consumed = manager.probe(target=target.target)
            self.assertNotIn("worker_received=", consumed.stdout)
            records = read_jsonl_records(root / "ledger.jsonl")
            self.assertFalse(any(record["event"] == "attach_turn" for record in records))

    def test_key_sequence_is_sent_to_visible_tmux_pane(self):
        session = f"clone-driver-key-menu-{uuid.uuid4().hex[:8]}"
        worker_script = (
            "import sys, time; "
            "print('READY', flush=True); "
            "print('Use keys then enter', flush=True); "
            "line = sys.stdin.readline().strip(); "
            "print('worker_received=' + line, flush=True); "
            "time.sleep(5)"
        )
        manager = TmuxSessionManager()
        target = manager.start(session=session, command=[sys.executable, "-c", worker_script])
        time.sleep(0.5)

        result = TmuxTerminalBroker().send_keys(target.target, ["1", "Enter"])

        self.assertEqual(result.status, "sent")
        self.assertTrue(result.enter_sent)
        time.sleep(0.5)
        consumed = manager.probe(target=target.target)
        self.assertIn("worker_received=1", consumed.stdout)

    def test_pair_opens_visible_advisor_pane_and_drives_worker(self):
        from clone_driver.pair import PairConfig, PairLauncher

        session = f"clone-driver-pair-{uuid.uuid4().hex[:8]}"
        worker_script = (
            "import select, sys, time; "
            "print('READY', flush=True); "
            "print('질문: 계속할까요?', flush=True); "
            "ready, _, _ = select.select([sys.stdin], [], [], 20); "
            "line = sys.stdin.readline().strip() if ready else ''; "
            "print('worker_received=' + line, flush=True); "
            "time.sleep(30)"
        )
        manager = TmuxSessionManager()
        target = manager.start(session=session, command=[sys.executable, "-c", worker_script])
        time.sleep(0.5)

        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                seed, wiw, not_to_do, final = write_contract(root)
                config = PairConfig(
                    target=target.target,
                    run_id="pair-smoke",
                    ledger_path=root / "ledger.jsonl",
                    advisor_transcript_path=root / "advisor-transcript.jsonl",
                    keepalive_seconds=30,
                    attach_args=[
                        "--backend",
                        "custom",
                        "--advisor-cmd",
                        f"{sys.executable} tests/fixtures/fake_advisor.py",
                        "--seed",
                        str(seed),
                        "--wiw",
                        str(wiw),
                        "--not-to-do",
                        str(not_to_do),
                        "--final-artifact",
                        str(final),
                        "--quick-regex",
                        "계속",
                        "--quick-reply",
                        "진행해.",
                        "--max-turns",
                        "1",
                        "--timeout",
                        "5",
                        "--poll-interval",
                        "0.1",
                        "--skip-doctor",
                    ],
                )

                result = PairLauncher(config).launch()

                self.assertEqual(result.status, "started")
                deadline = time.time() + 8
                worker_output = ""
                advisor_output = ""
                while time.time() < deadline:
                    worker_output = manager.probe(target=target.target).stdout
                    advisor_output = manager.probe(target=result.advisor_target).stdout
                    if "worker_received=네, 대체로 그렇습니다." in worker_output and "RightSeat ON" in advisor_output:
                        break
                    time.sleep(0.2)

                self.assertIn("worker_received=네, 대체로 그렇습니다.", worker_output)
                self.assertIn("RightSeat ON", advisor_output)
                records = read_jsonl_records(root / "ledger.jsonl")
                self.assertTrue(any(record["event"] == "pair_started" for record in records))
                turn = [record for record in records if record["event"] == "attach_turn"][0]
                self.assertTrue(turn["injected"])
                self.assertTrue(turn["enter_sent"])
                transcript = read_jsonl_records(root / "advisor-transcript.jsonl")
                statuses = [
                    record["status"]
                    for record in transcript
                    if record["event"] == "advisor_status"
                ]
                self.assertIn("watching", statuses)
                self.assertIn("prompt_observed", statuses)
                self.assertIn("injection_result", statuses)
                decisions = [
                    record
                    for record in transcript
                    if record["event"] == "advisor_decision"
                ]
                self.assertNotEqual(decisions[0]["reason"], "quick_reply")
        finally:
            subprocess.run(
                ["tmux", "kill-session", "-t", session],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
