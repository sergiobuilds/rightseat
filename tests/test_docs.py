import json
import unittest
from pathlib import Path


class DocumentationTests(unittest.TestCase):
    def test_quickstart_and_recipes_exist(self):
        readme = Path("README.md")
        recipes = Path("docs/recipes.md")
        manual = Path("docs/user-manual-ko.md")

        self.assertTrue(readme.exists())
        self.assertTrue(recipes.exists())
        self.assertTrue(manual.exists())

        readme_text = readme.read_text(encoding="utf-8")
        recipes_text = recipes.read_text(encoding="utf-8")
        manual_text = manual.read_text(encoding="utf-8")

        self.assertIn("RightSeat", readme_text)
        self.assertIn("rightseat", readme_text)
        for command in ["rightseat status", "rightseat pause", "rightseat resume", "rightseat off"]:
            self.assertIn(command, readme_text)
            self.assertIn(command, manual_text)
            self.assertIn(command, recipes_text)
        self.assertIn("rightseat log", readme_text)
        self.assertIn("--model", readme_text)
        self.assertIn("--effort", readme_text)
        self.assertIn("--log", readme_text)
        self.assertIn("backend LLM", readme_text)
        self.assertIn("choose by number", readme_text)
        self.assertIn("항상 번호로 고릅니다", manual_text)
        self.assertIn("agent-discord", manual_text)
        self.assertNotIn("picks it automatically", readme_text)
        self.assertNotIn("하나뿐이면 이걸로 끝", manual_text)
        self.assertNotIn("clone-driver pair --target", readme_text)
        self.assertNotIn("clone-driver pair --target", recipes_text)
        self.assertNotIn("clone-driver pair --target", manual_text)
        self.assertNotIn("--quick-regex", readme_text)
        self.assertNotIn("--quick-regex", recipes_text)
        self.assertNotIn("--quick-regex", manual_text)
        self.assertIn("제일 쉬운 사용법", manual_text)
        self.assertIn("user", manual_text)
        for label in ["OOO", "looprun", "ralph", "Superpowers"]:
            self.assertIn(label, recipes_text)

    def test_verifier_template_and_schema_examples_exist(self):
        template = Path("docs/verifier-template.md")
        examples = [
            Path("examples/verdict-pass.json"),
            Path("examples/verdict-fail.json"),
            Path("examples/verdict-escalate.json"),
        ]

        self.assertTrue(template.exists())
        template_text = template.read_text(encoding="utf-8")
        self.assertIn("untrusted DATA", template_text)
        for status in ["PASS", "FAIL", "ESCALATE"]:
            self.assertIn(status, template_text)

        statuses = []
        for example in examples:
            self.assertTrue(example.exists())
            data = json.loads(example.read_text(encoding="utf-8"))
            statuses.append(data["status"])
            self.assertIn("reason", data)
        self.assertEqual(statuses, ["PASS", "FAIL", "ESCALATE"])

    def test_advisor_loop_docs_exist(self):
        advisor_template = Path("docs/advisor-template.md")
        profile = Path("docs/examples/default-profile.md")
        policy = Path("docs/examples/answer-policy.md")
        readme = Path("README.md").read_text(encoding="utf-8")
        manual = Path("docs/user-manual-ko.md").read_text(encoding="utf-8")
        recipes = Path("docs/recipes.md").read_text(encoding="utf-8")

        self.assertTrue(advisor_template.exists())
        self.assertTrue(profile.exists())
        self.assertTrue(policy.exists())
        self.assertIn("deprecated compatibility", readme)
        self.assertIn("worker", readme)
        self.assertIn("RightSeat", manual)
        self.assertIn("worker 옆에 생기는 보이는 조종석", manual)
        self.assertIn("Compatibility", recipes)
        self.assertIn("rightseat", recipes)
