import unittest

from clone_driver.question import QuestionDetection, detect_question


class QuestionTests(unittest.TestCase):
    def test_detects_korean_question_marker(self):
        transcript = "MBTI_READY\n질문: 사람들과 있을 때 에너지가 생기나요?\n"
        result = detect_question(transcript, r"질문[:：]\s*(.+)|Q[0-9]+[:：]\s*(.+)|([^\n]+\?)")

        self.assertEqual(result.status, "found")
        self.assertEqual(result.question, "사람들과 있을 때 에너지가 생기나요?")

    def test_detects_last_question(self):
        transcript = (
            "질문: 사람들과 있을 때 에너지가 생기나요?\n"
            "네, 대체로 그렇습니다.\n"
            "Q2: 혼자 정리하는 시간이 꼭 필요한가요?\n"
        )
        result = detect_question(transcript, r"질문[:：]\s*(.+)|Q[0-9]+[:：]\s*(.+)|([^\n]+\?)")

        self.assertEqual(result.status, "found")
        self.assertEqual(result.question, "혼자 정리하는 시간이 꼭 필요한가요?")

    def test_missing_question_returns_missing(self):
        result = detect_question("working...\n", r"질문[:：]\s*(.+)")

        self.assertEqual(result, QuestionDetection(status="missing", question=""))

    def test_invalid_regex_is_error(self):
        result = detect_question("질문: x", "[")

        self.assertEqual(result.status, "regex_error")
        self.assertEqual(result.question, "")
