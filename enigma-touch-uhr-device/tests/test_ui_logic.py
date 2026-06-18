import unittest

from enigma_uhr_touch.ui_logic import (
    convert_with_backend_stream,
    extract_port_device,
    finish_manual_conversion,
    format_groups,
    prepare_touch_input,
)
from enigma_uhr_touch.uhr import Plugboard, Uhr, UhrAdapter


class UiLogicTests(unittest.TestCase):
    def setUp(self):
        plugboard = Plugboard.parse("AD CN ET FL GI JV KZ PU QY WX")
        self.adapter = UhrAdapter(plugboard, Uhr(plugboard, 0))

    def test_prepare_position_zero_is_original_letters(self):
        prepared = prepare_touch_input(self.adapter, "HELLO, WORLD!", preserve_nonletters=True)
        self.assertEqual(prepared.touch_letters, "HELLOWORLD")
        self.assertEqual(prepared.letter_count, 10)

    def test_finish_manual_conversion_preserves_nonletters(self):
        prepared = prepare_touch_input(self.adapter, "HELLO, WORLD!", preserve_nonletters=True)
        result = finish_manual_conversion(self.adapter, prepared, "HELLO WORLD")
        self.assertEqual(result, "HELLO, WORLD!")

    def test_finish_manual_conversion_validates_length(self):
        prepared = prepare_touch_input(self.adapter, "HELLO", preserve_nonletters=True)
        with self.assertRaises(ValueError):
            finish_manual_conversion(self.adapter, prepared, "HELL")

    def test_finish_manual_conversion_rejects_changed_settings(self):
        prepared = prepare_touch_input(self.adapter, "HELLO", preserve_nonletters=True)
        changed_adapter = UhrAdapter(self.adapter.plugboard, Uhr(self.adapter.plugboard, 1))
        with self.assertRaisesRegex(ValueError, "Settings changed"):
            finish_manual_conversion(changed_adapter, prepared, "HELLO")

    def test_format_groups(self):
        self.assertEqual(format_groups("HELLO, WORLD", 5), "HELLO WORLD")

    def test_extract_port_device(self):
        self.assertEqual(extract_port_device("COM5 - USB Serial Device"), "COM5")
        self.assertEqual(extract_port_device("COM7"), "COM7")

    def test_streaming_conversion_reports_progress(self):
        class IdentityBackend:
            def encipher_letter(self, letter):
                return letter

        progress = []
        result = convert_with_backend_stream(
            self.adapter,
            IdentityBackend(),
            "AB!",
            preserve_nonletters=True,
            progress=progress.append,
        )

        self.assertEqual(result, "AB!")
        self.assertEqual([item.output_text for item in progress], ["A", "AB", "AB!"])
        self.assertEqual(progress[-1].completed_letters, 2)
        self.assertEqual(progress[-1].total_letters, 2)


if __name__ == "__main__":
    unittest.main()
