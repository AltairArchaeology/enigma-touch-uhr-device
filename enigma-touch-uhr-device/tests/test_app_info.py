import unittest
from pathlib import Path

from enigma_uhr_touch.app_info import HELP_TEXT, MIT_LICENSE_TEXT, about_text, build_timestamp
from enigma_uhr_touch.version import VERSION_INFO, __version__


class AppInfoTests(unittest.TestCase):
    def test_help_contains_approved_output_labels(self):
        self.assertIn("Letters Per Group", HELP_TEXT)
        self.assertIn("Keep Spaces and Punctuation", HELP_TEXT)
        self.assertIn("Stops an active conversion", HELP_TEXT)
        self.assertIn("Update Position Before Convert", HELP_TEXT)
        self.assertIn("The Custom Enigma model is not yet implemented", HELP_TEXT)

    def test_about_contains_approved_contacts(self):
        text = about_text()
        self.assertIn("Version: 1.0.0", text)
        self.assertIn("Build: ", text)
        self.assertIn("Reddit: u/Mirzayev", text)
        self.assertIn("GitHub: https://github.com/AltairArchaeology", text)
        self.assertTrue(build_timestamp())

    def test_release_version(self):
        self.assertEqual(__version__, "1.0.0")
        self.assertEqual(VERSION_INFO, (1, 0, 0, 0))

    def test_license_dialog_matches_distributed_license(self):
        license_path = Path(__file__).resolve().parents[1] / "LICENSE"
        self.assertEqual(MIT_LICENSE_TEXT.strip(), license_path.read_text(encoding="ascii").strip())


if __name__ == "__main__":
    unittest.main()
