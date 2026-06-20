import tempfile
import unittest
from pathlib import Path

from clone_driver.task_contract import load_task_contract


class TaskContractTests(unittest.TestCase):
    def test_loads_contract_docs_and_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed = root / "seed.md"
            wiw = root / "wiw.md"
            not_to_do = root / "not-to-do.md"
            final = root / "final.md"
            seed.write_text("seed", encoding="utf-8")
            wiw.write_text("wiw", encoding="utf-8")
            not_to_do.write_text("not to do", encoding="utf-8")
            final.write_text("final artifact", encoding="utf-8")

            contract = load_task_contract(seed, wiw, not_to_do, final)

            self.assertEqual(contract.seed, "seed")
            self.assertEqual(contract.wiw, "wiw")
            self.assertEqual(contract.not_to_do, "not to do")
            self.assertEqual(contract.final_artifact, "final artifact")
            self.assertEqual(len(contract.hashes["seed"]), 64)
            self.assertEqual(contract.acceptance_criteria, [])

    def test_parses_acceptance_criteria_section(self):
        seed_text = (
            "# Task\n"
            "어떤 의도.\n\n"
            "## 합격 기준\n"
            "- [ ] 목록 화면에 항목이 1개 이상 뜬다\n"
            "- 4개 소스에서 데이터가 실제로 수집된다\n"
            "* [x] 필터를 누르면 결과가 바뀐다\n\n"
            "## 다음 섹션\n"
            "- 이건 기준이 아니다\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed = root / "seed.md"
            wiw = root / "wiw.md"
            not_to_do = root / "not-to-do.md"
            final = root / "final.md"
            seed.write_text(seed_text, encoding="utf-8")
            wiw.write_text("wiw", encoding="utf-8")
            not_to_do.write_text("x", encoding="utf-8")
            final.write_text("x", encoding="utf-8")

            contract = load_task_contract(seed, wiw, not_to_do, final)

            self.assertEqual(
                contract.acceptance_criteria,
                [
                    "목록 화면에 항목이 1개 이상 뜬다",
                    "4개 소스에서 데이터가 실제로 수집된다",
                    "필터를 누르면 결과가 바뀐다",
                ],
            )

    def test_acceptance_criteria_accepts_english_header(self):
        seed_text = "## Acceptance Criteria\n- builds without error\n"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed = root / "seed.md"
            for name in ("wiw.md", "not-to-do.md", "final.md"):
                (root / name).write_text("x", encoding="utf-8")
            seed.write_text(seed_text, encoding="utf-8")

            contract = load_task_contract(
                seed, root / "wiw.md", root / "not-to-do.md", root / "final.md"
            )

            self.assertEqual(contract.acceptance_criteria, ["builds without error"])


if __name__ == "__main__":
    unittest.main()
