import sys
import unittest

from clone_driver.pty_session import PtyWorker


class PtySessionTests(unittest.TestCase):
    def test_worker_output_can_be_read_and_answered(self):
        code = (
            "import sys; "
            "print('MBTI_READY', flush=True); "
            "print('질문: 사람들과 있을 때 에너지가 생기나요?', flush=True); "
            "answer = input(); "
            "print('worker_received=' + answer, flush=True)"
        )
        worker = PtyWorker([sys.executable, "-c", code])
        try:
            transcript = worker.read_until("질문:", timeout_seconds=3)
            self.assertIn("MBTI_READY", transcript)
            self.assertIn("질문:", transcript)

            worker.send_line("네, 대체로 그렇습니다.")
            transcript = worker.read_until("worker_received=", timeout_seconds=3)

            self.assertIn("worker_received=네, 대체로 그렇습니다.", transcript)
        finally:
            worker.close()

    def test_read_until_times_out_with_transcript(self):
        code = "import time; print('started', flush=True); time.sleep(2)"
        worker = PtyWorker([sys.executable, "-c", code])
        try:
            transcript = worker.read_until("missing-marker", timeout_seconds=0.2)
            self.assertIn("started", transcript)
            self.assertNotIn("missing-marker", transcript)
        finally:
            worker.close()
