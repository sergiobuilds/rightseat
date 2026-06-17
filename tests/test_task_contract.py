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


if __name__ == "__main__":
    unittest.main()
