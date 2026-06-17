import tempfile
import unittest
from pathlib import Path

from clone_driver.attach_profile import load_attach_profile


class AttachProfileTests(unittest.TestCase):
    def test_loads_toml_profile_and_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "attach.toml"
            path.write_text(
                "\n".join(
                    [
                        'profile_id = "codex-low"',
                        'backend = "codex"',
                        'advisor_model = "gpt-5.4-mini"',
                        'advisor_effort = "low"',
                        'mode = "confirm"',
                        'advisor_display = "tmux"',
                        'quick_regex = "계속|진행"',
                        'quick_reply = "진행해."',
                        'confirm_timeout = 20',
                    ]
                ),
                encoding="utf-8",
            )

            profile = load_attach_profile(path)

            self.assertEqual(profile.values["profile_id"], "codex-low")
            self.assertEqual(profile.values["backend"], "codex")
            self.assertEqual(profile.values["advisor_display"], "tmux")
            self.assertEqual(len(profile.config_hash), 64)


if __name__ == "__main__":
    unittest.main()
