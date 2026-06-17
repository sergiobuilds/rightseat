import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from clone_driver.attach import AttachConfig, AttachLoop
from clone_driver.ledger import read_jsonl_records
from clone_driver.terminal import FakeTerminalBroker


def write_contract(root: Path) -> tuple[Path, Path, Path, Path]:
    seed = root / "seed.md"
    wiw = root / "wiw.md"
    not_to_do = root / "not-to-do.md"
    final = root / "final.md"
    for path, text in [
        (seed, "answer only the current live prompt"),
        (wiw, "visible prompt answered with evidence"),
        (not_to_do, "do not trust worker self-grading"),
        (final, "stable prompt answered"),
    ]:
        path.write_text(text, encoding="utf-8")
    return seed, wiw, not_to_do, final


class AttachLoopTests(unittest.TestCase):
    def test_attach_reads_visible_question_and_injects_answer(self):
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
            terminal = FakeTerminalBroker(
                idle=True,
                transcript="READY\n질문: user는 어떤 답변을 선호하나요?\n",
            )

            config = AttachConfig(
                target="visible-pane",
                advisor_command=[sys.executable, "-m", "clone_driver.fake_advisor"],
                ledger_path=ledger,
                profile_path=profile,
                answer_policy_path=policy,
                question_regex=r"질문[:：]\s*(.+)|([^\n]+\?)",
                lock_root=root / "locks",
                seed_path=seed,
                wiw_path=wiw,
                not_to_do_path=not_to_do,
                final_artifact_path=final,
                max_turns=1,
                poll_interval_seconds=0.01,
                timeout_seconds=1.0,
            )

            result = AttachLoop(config, terminal=terminal).run()

            self.assertEqual(result["status"], "completed")
            self.assertEqual(terminal.sent[0][0], "visible-pane")
            self.assertIn("user는", terminal.sent[0][1])
            records = read_jsonl_records(ledger)
            turn = [record for record in records if record["event"] == "attach_turn"][0]
            self.assertEqual(turn["target"], "visible-pane")
            self.assertEqual(turn["canonical_target"], "visible-pane")
            self.assertTrue(turn["injected"])
            self.assertTrue(turn["enter_sent"])
            self.assertEqual(turn["detected_state"], "question")
            self.assertEqual(turn["contract_clause"], "all gates passed")
            self.assertEqual(turn["risk"], "low")

    def test_attach_escalates_without_contract_before_send(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = root / "ledger.jsonl"
            profile = root / "profile.md"
            policy = root / "policy.md"
            seed, wiw, not_to_do, final = write_contract(root)
            profile.write_text("profile", encoding="utf-8")
            policy.write_text("policy", encoding="utf-8")
            terminal = FakeTerminalBroker(
                idle=True,
                transcript="READY\n질문: 계속할까요?\n",
            )

            config = AttachConfig(
                target="visible-pane",
                advisor_command=[sys.executable, "-m", "clone_driver.fake_advisor"],
                ledger_path=ledger,
                profile_path=profile,
                answer_policy_path=policy,
                question_regex=r"질문[:：]\s*(.+)",
                lock_root=root / "locks",
                allow_missing_contract=True,
                max_turns=1,
                poll_interval_seconds=0.01,
                timeout_seconds=1.0,
            )

            result = AttachLoop(config, terminal=terminal).run()

            self.assertEqual(result["status"], "escalated")
            self.assertEqual(terminal.sent, [])
            records = read_jsonl_records(ledger)
            escalation = [record for record in records if record["event"] == "attach_escalated"][0]
            self.assertIn("no contract", escalation["reason"])

    def test_attach_escalates_on_worker_completion_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = root / "ledger.jsonl"
            profile = root / "profile.md"
            policy = root / "policy.md"
            seed, wiw, not_to_do, final = write_contract(root)
            profile.write_text("profile", encoding="utf-8")
            policy.write_text("policy", encoding="utf-8")
            terminal = FakeTerminalBroker(
                idle=True,
                transcript="✅ 모든 테스트 통과, 작업 완료\n질문: 계속할까요?\n",
            )

            config = AttachConfig(
                target="visible-pane",
                advisor_command=[sys.executable, "-m", "clone_driver.fake_advisor"],
                ledger_path=ledger,
                profile_path=profile,
                answer_policy_path=policy,
                question_regex=r"질문[:：]\s*(.+)",
                seed_path=seed,
                wiw_path=wiw,
                not_to_do_path=not_to_do,
                final_artifact_path=final,
                lock_root=root / "locks",
                max_turns=1,
                poll_interval_seconds=0.01,
                timeout_seconds=1.0,
            )

            result = AttachLoop(config, terminal=terminal).run()

            self.assertEqual(result["status"], "escalated")
            self.assertEqual(terminal.sent, [])
            records = read_jsonl_records(ledger)
            escalation = [record for record in records if record["event"] == "attach_escalated"][0]
            self.assertIn("completion claim", escalation["reason"])

    def test_attach_does_not_inject_without_question(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = root / "ledger.jsonl"
            profile = root / "profile.md"
            policy = root / "policy.md"
            seed, wiw, not_to_do, final = write_contract(root)
            profile.write_text("profile", encoding="utf-8")
            policy.write_text("policy", encoding="utf-8")
            terminal = FakeTerminalBroker(idle=True, transcript="READY\nno question\n")

            config = AttachConfig(
                target="visible-pane",
                advisor_command=[sys.executable, "-m", "clone_driver.fake_advisor"],
                ledger_path=ledger,
                profile_path=profile,
                answer_policy_path=policy,
                question_regex=r"질문[:：]\s*(.+)",
                lock_root=root / "locks",
                max_turns=1,
                poll_interval_seconds=0.01,
                timeout_seconds=0.05,
            )

            result = AttachLoop(config, terminal=terminal).run()

            self.assertEqual(result["status"], "timeout")
            self.assertEqual(terminal.sent, [])

    def test_attach_quick_rule_does_not_author_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = root / "ledger.jsonl"
            profile = root / "profile.md"
            policy = root / "policy.md"
            profile.write_text("profile", encoding="utf-8")
            policy.write_text("policy", encoding="utf-8")
            terminal = FakeTerminalBroker(
                idle=True,
                transcript="Press Enter to continue",
            )
            config = AttachConfig(
                target="visible-pane",
                advisor_command=[sys.executable, "-m", "clone_driver.fake_advisor"],
                ledger_path=ledger,
                profile_path=profile,
                answer_policy_path=policy,
                question_regex=r"질문[:：]\s*(.+)",
                quick_regex=r"Press Enter",
                quick_reply="",
                quick_keys=["Enter"],
                lock_root=root / "locks",
                max_turns=1,
                poll_interval_seconds=0.01,
                timeout_seconds=1.0,
            )

            with patch("clone_driver.attach.ExternalAdvisor.ask") as ask:
                result = AttachLoop(config, terminal=terminal).run()

            self.assertEqual(result["status"], "timeout")
            ask.assert_not_called()
            self.assertEqual(terminal.sent, [])
            self.assertNotIn("attach_turn", ledger.read_text(encoding="utf-8"))

    def test_attach_writes_quiet_advisor_status_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = root / "ledger.jsonl"
            transcript = root / "advisor-transcript.jsonl"
            profile = root / "profile.md"
            policy = root / "policy.md"
            seed, wiw, not_to_do, final = write_contract(root)
            profile.write_text("profile", encoding="utf-8")
            policy.write_text("policy", encoding="utf-8")
            terminal = FakeTerminalBroker(
                idle=True,
                transcript="READY\n질문: 계속할까요?\n",
            )
            config = AttachConfig(
                target="visible-pane",
                advisor_command=[sys.executable, "-m", "clone_driver.fake_advisor"],
                ledger_path=ledger,
                profile_path=profile,
                answer_policy_path=policy,
                question_regex=r"질문[:：]\s*(.+)",
                quick_regex="계속",
                quick_reply="진행해.",
                lock_root=root / "locks",
                seed_path=seed,
                wiw_path=wiw,
                not_to_do_path=not_to_do,
                final_artifact_path=final,
                advisor_display="inline",
                advisor_transcript_path=transcript,
                max_turns=1,
                poll_interval_seconds=0.01,
                timeout_seconds=1.0,
            )
            out = StringIO()

            with redirect_stdout(out):
                result = AttachLoop(config, terminal=terminal).run()

            self.assertEqual(result["status"], "completed")
            visible = out.getvalue()
            self.assertIn("RightSeat ON", visible)
            self.assertIn("state: watching", visible)
            self.assertIn("action: text", visible)
            self.assertIn("result: injected=True", visible)
            self.assertNotIn("advisor status=prompt_observed", visible)
            self.assertNotIn("no actionable prompt", visible)
            events = [record["event"] for record in read_jsonl_records(transcript)]
            self.assertIn("advisor_status", events)
            self.assertIn("advisor_decision", events)

    def test_attach_uses_advisor_key_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = root / "ledger.jsonl"
            profile = root / "profile.md"
            policy = root / "policy.md"
            seed, wiw, not_to_do, final = write_contract(root)
            profile.write_text("profile", encoding="utf-8")
            policy.write_text("policy", encoding="utf-8")
            terminal = FakeTerminalBroker(
                idle=True,
                transcript="질문: 어떤 메뉴를 선택할까요?",
            )
            config = AttachConfig(
                target="visible-pane",
                advisor_command=[sys.executable, "-m", "clone_driver.fake_advisor"],
                ledger_path=ledger,
                profile_path=profile,
                answer_policy_path=policy,
                question_regex=r"질문[:：]\s*(.+)",
                lock_root=root / "locks",
                seed_path=seed,
                wiw_path=wiw,
                not_to_do_path=not_to_do,
                final_artifact_path=final,
                max_turns=1,
                poll_interval_seconds=0.01,
                timeout_seconds=1.0,
            )
            response = SimpleNamespace(
                action="ANSWER",
                answer="",
                reason="Choose the second item.",
                confidence="high",
                input_mode="keys",
                keys=["Down", "Enter"],
                choice_label="second",
                answer_source="llm",
            )

            with patch("clone_driver.attach.ExternalAdvisor.ask", return_value=response):
                result = AttachLoop(config, terminal=terminal).run()

            self.assertEqual(result["status"], "completed")
            self.assertEqual(terminal.sent, [("visible-pane", "Down Enter")])
            turn = [
                record
                for record in read_jsonl_records(ledger)
                if record["event"] == "attach_turn"
            ][0]
            self.assertEqual(turn["input_mode"], "keys")
            self.assertEqual(turn["keys"], ["Down", "Enter"])
            self.assertEqual(turn["choice_label"], "second")

    def test_attach_refuses_foreign_current_codex_draft(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = root / "ledger.jsonl"
            profile = root / "profile.md"
            policy = root / "policy.md"
            seed, wiw, not_to_do, final = write_contract(root)
            profile.write_text("profile", encoding="utf-8")
            policy.write_text("policy", encoding="utf-8")
            terminal = FakeTerminalBroker(
                idle=True,
                transcript=(
                    "1d ago      — wget --mirror 라는게 뭔지알아?\n\n"
                    "› Run /review on my current changes\n"
                ),
            )
            config = AttachConfig(
                target="visible-pane",
                advisor_command=[sys.executable, "-m", "clone_driver.fake_advisor"],
                ledger_path=ledger,
                profile_path=profile,
                answer_policy_path=policy,
                question_regex=r"질문[:：]\s*(.+)|([^\n]+\?)",
                lock_root=root / "locks",
                seed_path=seed,
                wiw_path=wiw,
                not_to_do_path=not_to_do,
                final_artifact_path=final,
                max_turns=1,
                poll_interval_seconds=0.01,
                timeout_seconds=1.0,
            )
            response = SimpleNamespace(
                action="SUBMIT",
                answer="",
                text="",
                reason="Current draft is ready to submit.",
                confidence="high",
                input_mode="keys",
                keys=["Enter"],
                choice_label="",
                answer_source="llm",
            )

            with patch("clone_driver.attach.ExternalAdvisor.ask", return_value=response) as ask:
                result = AttachLoop(config, terminal=terminal).run()

            self.assertEqual(result["status"], "escalated")
            self.assertEqual(terminal.sent, [])
            request = ask.call_args.args[0]
            self.assertEqual(request.screen_state, "draft_ready")
            self.assertEqual(request.current_input, "Run /review on my current changes")
            self.assertEqual(request.question, "")
            records = read_jsonl_records(ledger)
            escalation = [record for record in records if record["event"] == "attach_escalated"][0]
            self.assertIn("foreign draft", escalation["reason"])

    def test_attach_refuses_stale_screen_before_injecting(self):
        class ChangingTerminal(FakeTerminalBroker):
            def __init__(self):
                super().__init__(idle=True, transcript="READY\n질문: 계속할까요?\n")
                self.captures = 0

            def capture(self, session):
                self.captures += 1
                if self.captures == 1:
                    self.transcript = "READY\n질문: 계속할까요?\n"
                else:
                    self.transcript = "READY\n이미 사람이 답했습니다.\n"
                return super().capture(session)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = root / "ledger.jsonl"
            profile = root / "profile.md"
            policy = root / "policy.md"
            seed = root / "seed.md"
            wiw = root / "wiw.md"
            not_to_do = root / "not-to-do.md"
            final = root / "final.md"
            for path, text in [
                (profile, "profile"),
                (policy, "policy"),
                (seed, "answer the live question"),
                (wiw, "continue only when current prompt is stable"),
                (not_to_do, "do not send on stale screen"),
                (final, "stable prompt answered"),
            ]:
                path.write_text(text, encoding="utf-8")

            config = AttachConfig(
                target="visible-pane",
                advisor_command=[sys.executable, "-m", "clone_driver.fake_advisor"],
                ledger_path=ledger,
                profile_path=profile,
                answer_policy_path=policy,
                question_regex=r"질문[:：]\s*(.+)",
                quick_regex="계속",
                quick_reply="진행해.",
                seed_path=seed,
                wiw_path=wiw,
                not_to_do_path=not_to_do,
                final_artifact_path=final,
                lock_root=root / "locks",
                max_turns=1,
                poll_interval_seconds=0.01,
                timeout_seconds=1.0,
            )

            terminal = ChangingTerminal()
            result = AttachLoop(config, terminal=terminal).run()

            self.assertEqual(result["status"], "stale_screen")
            self.assertEqual(terminal.sent, [])
            self.assertNotIn("attach_turn", ledger.read_text(encoding="utf-8"))

    def test_attach_refuses_cosmetic_screen_changes_when_current_draft_is_foreign(self):
        class CosmeticChangingTerminal(FakeTerminalBroker):
            def __init__(self):
                super().__init__(
                    idle=True,
                    transcript="gpt-5.5 xhigh · Context 0% used\n› 0\n",
                )
                self.captures = 0

            def capture(self, session):
                self.captures += 1
                if self.captures == 1:
                    self.transcript = "gpt-5.5 xhigh · Context 0% used\n› 0\n"
                else:
                    self.transcript = "gpt-5.5 xhigh · Context 1% used\n› 0\n"
                return super().capture(session)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = root / "ledger.jsonl"
            profile = root / "profile.md"
            policy = root / "policy.md"
            seed, wiw, not_to_do, final = write_contract(root)
            profile.write_text("profile", encoding="utf-8")
            policy.write_text("policy", encoding="utf-8")
            config = AttachConfig(
                target="visible-pane",
                advisor_command=[sys.executable, "-m", "clone_driver.fake_advisor"],
                ledger_path=ledger,
                profile_path=profile,
                answer_policy_path=policy,
                question_regex=r"질문[:：]\s*(.+)|([^\n]+\?)",
                lock_root=root / "locks",
                seed_path=seed,
                wiw_path=wiw,
                not_to_do_path=not_to_do,
                final_artifact_path=final,
                max_turns=1,
                poll_interval_seconds=0.01,
                timeout_seconds=1.0,
            )

            terminal = CosmeticChangingTerminal()
            result = AttachLoop(config, terminal=terminal).run()

            self.assertEqual(result["status"], "escalated")
            self.assertEqual(terminal.sent, [])

    def test_attach_records_contract_hashes_when_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = root / "ledger.jsonl"
            profile = root / "profile.md"
            policy = root / "policy.md"
            seed = root / "seed.md"
            wiw = root / "wiw.md"
            not_to_do = root / "not-to-do.md"
            final = root / "final.md"
            for path, text in [
                (profile, "profile"),
                (policy, "policy"),
                (seed, "seed"),
                (wiw, "wiw"),
                (not_to_do, "not to do"),
                (final, "final"),
            ]:
                path.write_text(text, encoding="utf-8")

            terminal = FakeTerminalBroker(idle=True, transcript="READY\n질문: 계속할까요?\n")
            config = AttachConfig(
                target="visible-pane",
                advisor_command=[sys.executable, "-m", "clone_driver.fake_advisor"],
                ledger_path=ledger,
                profile_path=profile,
                answer_policy_path=policy,
                question_regex=r"질문[:：]\s*(.+)",
                seed_path=seed,
                wiw_path=wiw,
                not_to_do_path=not_to_do,
                final_artifact_path=final,
                lock_root=root / "locks",
                max_turns=1,
                poll_interval_seconds=0.01,
                timeout_seconds=1.0,
            )

            result = AttachLoop(config, terminal=terminal).run()

            self.assertEqual(result["status"], "completed")
            records = read_jsonl_records(ledger)
            turn = [record for record in records if record["event"] == "attach_turn"][0]
            self.assertIn("contract_hashes", turn)
            self.assertIn("seed", turn["contract_hashes"])

    def test_attach_redacts_screen_before_advisor_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = root / "ledger.jsonl"
            profile = root / "profile.md"
            policy = root / "policy.md"
            seed, wiw, not_to_do, final = write_contract(root)
            profile.write_text("profile", encoding="utf-8")
            policy.write_text("policy", encoding="utf-8")
            terminal = FakeTerminalBroker(
                idle=True,
                transcript="READY\n질문: token=example-secret-value 계속할까요?\n",
            )
            config = AttachConfig(
                target="visible-pane",
                advisor_command=[sys.executable, "-m", "clone_driver.fake_advisor"],
                ledger_path=ledger,
                profile_path=profile,
                answer_policy_path=policy,
                question_regex=r"질문[:：]\s*(.+)",
                lock_root=root / "locks",
                seed_path=seed,
                wiw_path=wiw,
                not_to_do_path=not_to_do,
                final_artifact_path=final,
                max_turns=1,
                poll_interval_seconds=0.01,
                timeout_seconds=1.0,
            )
            response = SimpleNamespace(
                action="ANSWER",
                answer="진행해.",
                reason="Safe after redaction.",
                confidence="high",
                input_mode="text",
                keys=[],
                choice_label="",
                answer_source="llm",
            )

            with patch("clone_driver.attach.ExternalAdvisor.ask", return_value=response) as ask:
                result = AttachLoop(config, terminal=terminal).run()

            self.assertEqual(result["status"], "completed")
            request = ask.call_args.args[0]
            self.assertNotIn("example-secret-value", request.screen_tail)
            turn = [
                record
                for record in read_jsonl_records(ledger)
                if record["event"] == "attach_turn"
            ][0]
            self.assertEqual(turn["redaction_count"], 1)
            self.assertEqual(len(turn["redacted_screen_hash"]), 64)

    def test_attach_records_advisor_timeout_without_injection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = root / "ledger.jsonl"
            profile = root / "profile.md"
            policy = root / "policy.md"
            seed, wiw, not_to_do, final = write_contract(root)
            profile.write_text("profile", encoding="utf-8")
            policy.write_text("policy", encoding="utf-8")
            terminal = FakeTerminalBroker(idle=True, transcript="READY\n질문: 계속할까요?\n")
            config = AttachConfig(
                target="visible-pane",
                advisor_command=[sys.executable, "-m", "clone_driver.fake_advisor"],
                ledger_path=ledger,
                profile_path=profile,
                answer_policy_path=policy,
                question_regex=r"질문[:：]\s*(.+)",
                advisor_timeout_seconds=0.01,
                lock_root=root / "locks",
                allow_missing_contract=True,
                max_turns=1,
                poll_interval_seconds=0.01,
                timeout_seconds=1.0,
            )

            with patch("clone_driver.attach.ExternalAdvisor.ask", side_effect=TimeoutError("advisor command timed out")):
                result = AttachLoop(config, terminal=terminal).run()

            self.assertEqual(result["status"], "advisor_timeout")
            self.assertEqual(terminal.sent, [])
            records = read_jsonl_records(ledger)
            self.assertEqual(records[-1]["event"], "advisor_timeout")

    def test_confirm_mode_rejects_non_tty_without_injection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = root / "ledger.jsonl"
            profile = root / "profile.md"
            policy = root / "policy.md"
            seed, wiw, not_to_do, final = write_contract(root)
            profile.write_text("profile", encoding="utf-8")
            policy.write_text("policy", encoding="utf-8")
            terminal = FakeTerminalBroker(idle=True, transcript="READY\n질문: 계속할까요?\n")

            config = AttachConfig(
                target="visible-pane",
                advisor_command=[sys.executable, "-m", "clone_driver.fake_advisor"],
                ledger_path=ledger,
                profile_path=profile,
                answer_policy_path=policy,
                question_regex=r"질문[:：]\s*(.+)",
                mode="confirm",
                confirm_timeout_seconds=0.01,
                lock_root=root / "locks",
                seed_path=seed,
                wiw_path=wiw,
                not_to_do_path=not_to_do,
                final_artifact_path=final,
                max_turns=1,
                poll_interval_seconds=0.01,
                timeout_seconds=1.0,
            )

            result = AttachLoop(config, terminal=terminal, input_stream=None).run()

            self.assertEqual(result["status"], "confirm_unavailable")
            self.assertEqual(terminal.sent, [])
