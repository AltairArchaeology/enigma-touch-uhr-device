import unittest

from enigma_uhr_touch.uhr import ALPHABET, Plugboard, Uhr, UhrAdapter


class UhrTests(unittest.TestCase):
    def setUp(self):
        self.plugboard = Plugboard.parse("AD CN ET FL GI JV KZ PU QY WX")

    def test_position_zero_matches_plugboard(self):
        uhr = Uhr(self.plugboard, 0)
        for char in ALPHABET:
            self.assertEqual(uhr.forward(char), self.plugboard.swap(char))

    def test_position_zero_wrapper_is_noop(self):
        adapter = UhrAdapter(self.plugboard, Uhr(self.plugboard, 0))
        for char in ALPHABET:
            self.assertEqual(adapter.to_touch(char), char)
            self.assertEqual(adapter.from_touch(char), char)

    def test_all_positions_are_permutations(self):
        for position in range(40):
            with self.subTest(position=position):
                mapping = Uhr(self.plugboard, position).mapping()
                self.assertEqual(set(mapping), set(ALPHABET))
                self.assertEqual(set(mapping.values()), set(ALPHABET))

    def test_every_fourth_position_is_involutory(self):
        for position in range(40):
            uhr = Uhr(self.plugboard, position)
            involutory = all(uhr.forward(uhr.forward(char)) == char for char in ALPHABET)
            self.assertEqual(involutory, position % 4 == 0)

    def test_position_one_sample_mapping(self):
        uhr = Uhr(self.plugboard, 1)
        self.assertEqual("".join(uhr.forward(char) for char in ALPHABET), "TBLPYUIHCZDFMJOXNRSAWQVKGE")

    def test_wrapper_steps_are_inverses(self):
        for position in range(40):
            adapter = UhrAdapter(self.plugboard, Uhr(self.plugboard, position))
            for char in ALPHABET:
                self.assertEqual(adapter.from_touch(adapter.to_touch(char)), char)

    def test_parse_rejects_duplicate_letters(self):
        with self.assertRaises(ValueError):
            Plugboard.parse("AD AC")

    def test_historical_mode_rejects_nonhistorical_pair_count(self):
        with self.assertRaisesRegex(ValueError, "exactly ten"):
            Plugboard.parse("AB CD EF")

    def test_ahistoric_mode_requires_at_least_one_pair(self):
        with self.assertRaisesRegex(ValueError, "between one and thirteen"):
            Plugboard.parse("", ahistoric=True)

    def test_ahistoric_mode_supports_every_pair_count_and_position(self):
        all_pairs = [ALPHABET[index : index + 2] for index in range(0, len(ALPHABET), 2)]
        for pair_count in range(1, 14):
            plugboard = Plugboard.parse(" ".join(all_pairs[:pair_count]), ahistoric=True)
            for position in range(40):
                with self.subTest(pair_count=pair_count, position=position):
                    uhr = Uhr(plugboard, position, ahistoric=True)
                    adapter = UhrAdapter(plugboard, uhr)
                    mapping = uhr.mapping()
                    self.assertEqual(set(mapping), set(ALPHABET))
                    self.assertEqual(set(mapping.values()), set(ALPHABET))
                    for char in ALPHABET:
                        self.assertEqual(adapter.from_touch(adapter.to_touch(char)), char)

    def test_ahistoric_position_zero_is_noop_for_every_pair_count(self):
        all_pairs = [ALPHABET[index : index + 2] for index in range(0, len(ALPHABET), 2)]
        for pair_count in range(1, 14):
            plugboard = Plugboard.parse(" ".join(all_pairs[:pair_count]), ahistoric=True)
            adapter = UhrAdapter(plugboard, Uhr(plugboard, 0, ahistoric=True))
            for char in ALPHABET:
                self.assertEqual(adapter.to_touch(char), char)
                self.assertEqual(adapter.from_touch(char), char)

    def test_ten_pair_ahistoric_mode_preserves_historical_wiring(self):
        ahistoric_plugboard = Plugboard.parse(str(self.plugboard), ahistoric=True)
        for position in range(40):
            historical = Uhr(self.plugboard, position)
            ahistoric = Uhr(ahistoric_plugboard, position, ahistoric=True)
            self.assertEqual(ahistoric.mapping(), historical.mapping())


if __name__ == "__main__":
    unittest.main()
