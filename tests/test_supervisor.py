import sys
import tempfile
import unittest
from pathlib import Path

from clone_driver.ledger import read_jsonl_records
from clone_driver.supervisor import SupervisorConfig, SupervisorLoop


class SupervisorTests(unittest.TestCase):
    def test_fake_mbti_worker_gets_three_advisor_answers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = root / "ledger.jsonl"
            profile = root / "profile.md"
            policy = root / "policy.md"
            profile.write_text("user prefers pragmatic direct answers.", encoding="utf-8")
            policy.write_text("Answer in Korean as user. Keep answers short.", encoding="utf-8")

            config = SupervisorConfig(
                worker_command=[sys.executable, "tests/fixtures/fake_mbti_worker.py"],
                advisor_command=[sys.executable, "tests/fixtures/fake_advisor.py"],
                ledger_path=ledger,
                profile_path=profile,
                answer_policy_path=policy,
                ready_regex="MBTI_READY|질문|Q[0-9]+:",
                question_regex=r"질문[:：]\s*(.+)|Q[0-9]+[:：]\s*(.+)|([^\n]+\?)",
                max_turns=5,
                read_timeout_seconds=3.0,
            )

            result = SupervisorLoop(config).run()

            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["turns"], 3)
            records = read_jsonl_records(ledger)
            advisor_turns = [record for record in records if record["event"] == "advisor_turn"]
            self.assertEqual(len(advisor_turns), 3)
            self.assertEqual(advisor_turns[0]["action"], "ANSWER")
            self.assertTrue(advisor_turns[0]["injected"])
            self.assertIn("사람들과 있을 때", advisor_turns[0]["question"])
            self.assertTrue(any(record["event"] == "supervise_finished" for record in records))

    def test_generic_worker_can_complete_without_mbti_done_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            worker = root / "worker.py"
            ledger = root / "ledger.jsonl"
            profile = root / "profile.md"
            policy = root / "policy.md"
            worker.write_text(
                "print('READY', flush=True)\n"
                "print('질문: 지금 무엇을 해야 하나요?', flush=True)\n"
                "answer = input()\n"
                "print('worker_received=' + answer, flush=True)\n",
                encoding="utf-8",
            )
            profile.write_text("user prefers pragmatic direct answers.", encoding="utf-8")
            policy.write_text("Answer in Korean as user. Keep answers short.", encoding="utf-8")

            config = SupervisorConfig(
                worker_command=[sys.executable, str(worker)],
                advisor_command=[sys.executable, "tests/fixtures/fake_advisor.py"],
                ledger_path=ledger,
                profile_path=profile,
                answer_policy_path=policy,
                ready_regex="READY|질문",
                question_regex=r"질문[:：]\s*(.+)|([^\n]+\?)",
                max_turns=3,
                read_timeout_seconds=2.0,
            )

            result = SupervisorLoop(config).run()

            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["turns"], 1)
            records = read_jsonl_records(ledger)
            self.assertEqual(
                len([record for record in records if record["event"] == "advisor_turn"]),
                1,
            )
            self.assertTrue(
                any(
                    record["event"] == "supervise_finished"
                    and record["status"] == "completed"
                    for record in records
                )
            )

    def test_supervisor_waits_for_next_question_instead_of_stalling_on_old_transcript(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            worker = root / "worker.py"
            ledger = root / "ledger.jsonl"
            profile = root / "profile.md"
            policy = root / "policy.md"
            worker.write_text(
                "import time\n"
                "print('READY', flush=True)\n"
                "print('질문: 첫 번째?', flush=True)\n"
                "answer = input()\n"
                "print('worker_received=' + answer, flush=True)\n"
                "time.sleep(0.25)\n"
                "print('질문: 두 번째?', flush=True)\n"
                "answer = input()\n"
                "print('worker_received=' + answer, flush=True)\n",
                encoding="utf-8",
            )
            profile.write_text("user prefers pragmatic direct answers.", encoding="utf-8")
            policy.write_text("Answer in Korean as user. Keep answers short.", encoding="utf-8")

            config = SupervisorConfig(
                worker_command=[sys.executable, str(worker)],
                advisor_command=[sys.executable, "tests/fixtures/fake_advisor.py"],
                ledger_path=ledger,
                profile_path=profile,
                answer_policy_path=policy,
                ready_regex="READY|질문",
                question_regex=r"질문[:：]\s*(.+)|([^\n]+\?)",
                max_turns=3,
                read_timeout_seconds=0.1,
            )

            result = SupervisorLoop(config).run()

            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["turns"], 2)
            records = read_jsonl_records(ledger)
            advisor_turns = [record for record in records if record["event"] == "advisor_turn"]
            self.assertEqual(len(advisor_turns), 2)

    def test_supervisor_stops_on_advisor_escalate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            worker = root / "worker.py"
            ledger = root / "ledger.jsonl"
            profile = root / "profile.md"
            policy = root / "policy.md"
            worker.write_text(
                "print('MBTI_READY', flush=True)\n"
                "print('질문: FORCE_ESCALATE', flush=True)\n"
                "input()\n",
                encoding="utf-8",
            )
            profile.write_text("profile", encoding="utf-8")
            policy.write_text("policy", encoding="utf-8")

            config = SupervisorConfig(
                worker_command=[sys.executable, str(worker)],
                advisor_command=[sys.executable, "tests/fixtures/fake_advisor.py"],
                ledger_path=ledger,
                profile_path=profile,
                answer_policy_path=policy,
                ready_regex="MBTI_READY|질문",
                question_regex=r"질문[:：]\s*(.+)",
                max_turns=3,
                read_timeout_seconds=2.0,
            )

            result = SupervisorLoop(config).run()

            self.assertEqual(result["status"], "escalated")
            records = read_jsonl_records(ledger)
            self.assertTrue(any(record["event"] == "advisor_escalated" for record in records))
            self.assertFalse(any(record.get("injected") is True for record in records))
