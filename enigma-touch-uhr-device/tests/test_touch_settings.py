import unittest

from enigma_uhr_touch.enigma_core import machine_from_touch_settings, reflector_from_german_pairs
from enigma_uhr_touch.touch_settings import (
    build_touch_settings,
    parse_touch_settings,
)
from enigma_uhr_touch.ui_logic import (
    ConversionStopped,
    convert_direct_with_backend_stream,
    convert_with_backend_stream,
)
from enigma_uhr_touch.uhr import Plugboard, Uhr, UhrAdapter


SAMPLE_RESPONSES = {
    "?MO": "?MO\r\nEnigma    M4\r\n",
    "?RO": "?RO\r\nReflector B\r\nRotors    beta III II I\r\n",
    "?RI": "?RI\r\nRings     A A A A\r\n",
    "?RP": "?RP\r\nPositions A A A A\r\n",
    "?PB": "?PB\r\nPlugboard AN BR CE DV FS GP IT JO LW MY \r\n",
    "?RD": "?RD\r\nUKW D     AQ BG CK DI EL FX HZ JY MW NV OT PU RS\r\n",
}


class TouchSettingsTests(unittest.TestCase):
    def test_parse_m4_settings_from_touch_log(self):
        settings = parse_touch_settings(SAMPLE_RESPONSES)

        self.assertEqual(settings.model, "M4")
        self.assertEqual(settings.model_name, "M4")
        self.assertTrue(settings.has_uhr_plugboard)
        self.assertEqual(settings.reflector, "B")
        self.assertEqual(settings.rotors, ("beta", "III", "II", "I"))
        self.assertEqual(settings.rings, (0, 0, 0, 0))
        self.assertEqual(settings.positions, (0, 0, 0, 0))
        self.assertEqual(settings.plugboard_pairs, "AN BR CE DV FS GP IT JO LW MY")

    def test_parse_numeric_settings(self):
        settings = parse_touch_settings(
            {
                **SAMPLE_RESPONSES,
                "?MO": "Enigma    I\r\n",
                "?RO": "Reflector B\r\nRotors    III II I\r\n",
                "?RI": "Rings     01 13 07\r\n",
                "?RP": "Positions 17 23 05\r\n",
            }
        )

        self.assertEqual(settings.model, "I")
        self.assertEqual(settings.rings, (0, 12, 6))
        self.assertEqual(settings.positions, (16, 22, 4))
        self.assertEqual(settings.rings_display(), "01 13 07")
        self.assertEqual(settings.positions_display(), "17 23 05")

    def test_non_plugboard_model_rejects_uhr(self):
        settings = build_touch_settings(
            model="K",
            reflector="K",
            rotors="III II I",
            rings="A A A A",
            positions="A A A A",
            plugboard_pairs="AN BR CE DV FS GP IT JO LW MY",
        )

        with self.assertRaisesRegex(ValueError, "does not have an active plugboard"):
            settings.require_uhr_supported()

    def test_ahistoric_mode_accepts_variable_plugboard_count(self):
        settings = build_touch_settings(
            model="M4",
            reflector="B",
            rotors="beta III II I",
            rings="A A A A",
            positions="A A A A",
            plugboard_pairs="AB CD EF",
        )
        with self.assertRaisesRegex(ValueError, "exactly ten"):
            settings.require_uhr_supported()
        settings.require_uhr_supported(ahistoric=True)

    def test_reflector_d_german_notation_matches_bletchley_example(self):
        german = reflector_from_german_pairs("AQ BG CK DI EL FX HZ JY MW NV OT PU RS")
        bletchley = pairs_to_reflector("AK BO CT DV EP FN GL HM IJ QW RY SX UZ")

        self.assertEqual(german, bletchley)

    def test_direct_output_matches_existing_uhr_wrapper_result(self):
        settings = parse_touch_settings(SAMPLE_RESPONSES)
        plugboard = Plugboard.parse(settings.plugboard_pairs)
        adapter = UhrAdapter(plugboard, Uhr(plugboard, 17))

        expected_machine = machine_from_touch_settings(settings, plugboard)
        expected = convert_with_backend_stream(
            adapter,
            SimulatedTouch(expected_machine),
            "HELLO WORLD",
            preserve_nonletters=True,
        )

        direct_machine = machine_from_touch_settings(settings, plugboard)
        physical_touch = SimulatedTouch(machine_from_touch_settings(settings, plugboard))
        direct = convert_direct_with_backend_stream(
            adapter,
            direct_machine,
            physical_touch,
            "HELLO WORLD",
            preserve_nonletters=True,
        )

        self.assertEqual(direct, expected)
        self.assertEqual("".join(physical_touch.outputs), expected.replace(" ", ""))

    def test_position_zero_direct_output_sends_original_letters(self):
        settings = parse_touch_settings(SAMPLE_RESPONSES)
        plugboard = Plugboard.parse(settings.plugboard_pairs)
        adapter = UhrAdapter(plugboard, Uhr(plugboard, 0))
        physical_touch = SimulatedTouch(machine_from_touch_settings(settings, plugboard))

        convert_direct_with_backend_stream(
            adapter,
            machine_from_touch_settings(settings, plugboard),
            physical_touch,
            "HELLO",
            preserve_nonletters=True,
        )

        self.assertEqual("".join(physical_touch.inputs), "HELLO")

    def test_direct_conversion_stop_preserves_partial_output_and_position(self):
        settings = parse_touch_settings(SAMPLE_RESPONSES)
        plugboard = Plugboard.parse(settings.plugboard_pairs)
        adapter = UhrAdapter(plugboard, Uhr(plugboard, 17))
        machine = machine_from_touch_settings(settings, plugboard)
        physical_touch = SimulatedTouch(machine_from_touch_settings(settings, plugboard))
        stop_requested = False

        class StoppingTouch:
            def encipher_letter(self, letter):
                nonlocal stop_requested
                output = physical_touch.encipher_letter(letter)
                if len(physical_touch.outputs) == 2:
                    stop_requested = True
                return output

        with self.assertRaises(ConversionStopped) as caught:
            convert_direct_with_backend_stream(
                adapter,
                machine,
                StoppingTouch(),
                "HELLO",
                preserve_nonletters=True,
                should_stop=lambda: stop_requested,
            )

        self.assertEqual(caught.exception.output_text, "".join(physical_touch.outputs))
        self.assertEqual(caught.exception.completed_letters, 2)
        self.assertEqual(caught.exception.total_letters, 5)
        self.assertEqual(machine.position_values(), physical_touch.machine.position_values())

    def test_ahistoric_direct_output_matches_wrapper_for_variable_pair_counts(self):
        all_pairs = "AB CD EF GH IJ KL MN OP QR ST UV WX YZ".split()
        for pair_count in (3, 13):
            with self.subTest(pair_count=pair_count):
                pairs = " ".join(all_pairs[:pair_count])
                settings = build_touch_settings(
                    model="M4",
                    reflector="B",
                    rotors="beta III II I",
                    rings="A A A A",
                    positions="A A A A",
                    plugboard_pairs=pairs,
                )
                plugboard = Plugboard.parse(pairs, ahistoric=True)
                adapter = UhrAdapter(plugboard, Uhr(plugboard, 17, ahistoric=True))

                expected = convert_with_backend_stream(
                    adapter,
                    SimulatedTouch(machine_from_touch_settings(settings, plugboard, ahistoric=True)),
                    "HELLO WORLD",
                    preserve_nonletters=True,
                )
                physical_touch = SimulatedTouch(
                    machine_from_touch_settings(settings, plugboard, ahistoric=True)
                )
                direct = convert_direct_with_backend_stream(
                    adapter,
                    machine_from_touch_settings(settings, plugboard, ahistoric=True),
                    physical_touch,
                    "HELLO WORLD",
                    preserve_nonletters=True,
                )

                self.assertEqual(direct, expected)
                self.assertEqual("".join(physical_touch.outputs), expected.replace(" ", ""))


class SimulatedTouch:
    def __init__(self, machine):
        self.machine = machine
        self.inputs = []
        self.outputs = []

    def encipher_letter(self, letter):
        self.inputs.append(letter)
        output = self.machine.encipher_letter(letter, use_plugboard=True)
        self.outputs.append(output)
        return output


def pairs_to_reflector(pairs):
    wiring = list(range(26))
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    for pair in pairs.split():
        left = alphabet.index(pair[0])
        right = alphabet.index(pair[1])
        wiring[left] = right
        wiring[right] = left
    return tuple(wiring)


if __name__ == "__main__":
    unittest.main()
