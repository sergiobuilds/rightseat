import unittest

from clone_driver.redaction import redact_screen


class RedactionTests(unittest.TestCase):
    def test_redacts_common_secret_shapes(self):
        result = redact_screen("token=example-secret-value\nnormal line\n")

        self.assertNotIn("example-secret-value", result.text)
        self.assertIn("[REDACTED]", result.text)
        self.assertEqual(result.count, 1)
        self.assertEqual(len(result.hash), 64)


if __name__ == "__main__":
    unittest.main()
