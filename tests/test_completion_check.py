import unittest

from clone_driver.completion_check import verify_completion


class CompletionCheckTests(unittest.TestCase):
    def test_empty_ac_is_fail(self):
        result = verify_completion(ac_results=[], exit_code=0, regressed=False)

        self.assertFalse(result.passed)

    def test_all_pass_and_exit0_passes(self):
        result = verify_completion(ac_results=[True, True], exit_code=0, regressed=False)

        self.assertTrue(result.passed)
        self.assertTrue(result.all_passed)

    def test_one_ac_fail_is_fail(self):
        result = verify_completion(ac_results=[True, False], exit_code=0, regressed=False)

        self.assertFalse(result.passed)

    def test_no_runtime_evidence_is_fail(self):
        result = verify_completion(ac_results=[True], exit_code=None, regressed=False)

        self.assertFalse(result.passed)

    def test_regression_is_fail(self):
        result = verify_completion(ac_results=[True], exit_code=0, regressed=True)

        self.assertFalse(result.passed)


if __name__ == "__main__":
    unittest.main()
