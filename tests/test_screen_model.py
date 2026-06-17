import unittest

from clone_driver.screen_model import analyze_screen


class ScreenModelTests(unittest.TestCase):
    def test_codex_empty_input_is_input_empty(self):
        screen = analyze_screen("╭─ Codex ─╮\n\n› Implement {feature}\n")

        self.assertEqual(screen.adapter, "codex")
        self.assertEqual(screen.state, "input_empty")
        self.assertEqual(screen.current_input, "")

    def test_codex_draft_ready_reads_current_input(self):
        screen = analyze_screen("╭─ Codex ─╮\n\n› Run /review on my current changes\n")

        self.assertEqual(screen.state, "draft_ready")
        self.assertEqual(screen.current_input, "Run /review on my current changes")

    def test_current_draft_beats_old_scrollback_question(self):
        transcript = "\n".join(
            [
                "1d ago      — wget --mirror 라는게 뭔지알아?",
                "",
                "› Run /review on my current changes",
            ]
        )

        screen = analyze_screen(transcript)

        self.assertEqual(screen.state, "draft_ready")
        self.assertEqual(screen.current_input, "Run /review on my current changes")
        self.assertEqual(screen.question, "")

    def test_current_question_above_empty_prompt_is_question_waiting(self):
        transcript = "\n".join(
            [
                "user, 어떤 방식으로 진행할까요?",
                "",
                "›",
            ]
        )

        screen = analyze_screen(transcript)

        self.assertEqual(screen.state, "question_waiting")
        self.assertEqual(screen.question, "user, 어떤 방식으로 진행할까요?")

    def test_choice_menu_above_empty_prompt_is_choice_waiting(self):
        transcript = "\n".join(
            [
                "ooo 통합 첫 실행을 어떻게 증명할까요?",
                "❯ 1. 작은 실제 작업으로 1사이클",
                "  2. 가드레일 주입 설계부터 문서화",
                "",
                "›",
            ]
        )

        screen = analyze_screen(transcript)

        self.assertEqual(screen.state, "choice_waiting")
        self.assertIn("작은 실제 작업", screen.question)

    def test_detects_worker_completion_claim(self):
        screen = analyze_screen("작업을 마쳤습니다.\n✅ 모든 테스트 통과, 작업 완료\n› ")

        self.assertIn(screen.worker_claim, {"done", "passed"})

    def test_detects_hard_stop_affordance(self):
        screen = analyze_screen("rm -rf / 실행할까요? [y/N]\n")

        self.assertTrue(screen.hard_stop)

    def test_detects_busy(self):
        screen = analyze_screen("⠋ working...\n")

        self.assertTrue(screen.busy)

    def test_foreign_draft_when_self_did_not_author(self):
        screen = analyze_screen("› 0")

        self.assertEqual(screen.current_input, "0")
        self.assertEqual(screen.draft_author, "FOREIGN")


if __name__ == "__main__":
    unittest.main()
