import unittest

from clone_driver.backend_doctor import DoctorResult, validate_advisor_schema


class BackendDoctorTests(unittest.TestCase):
    def test_validates_advisor_schema(self):
        result = validate_advisor_schema(
            '{"action":"ANSWER","answer":"진행해.","reason":"ok","confidence":"high","input_mode":"text"}'
        )

        self.assertEqual(result.status, "ok")

    def test_rejects_invalid_schema(self):
        result = validate_advisor_schema('{"answer":"missing action"}')

        self.assertEqual(result.status, "schema_error")
        self.assertIsInstance(result, DoctorResult)


if __name__ == "__main__":
    unittest.main()
