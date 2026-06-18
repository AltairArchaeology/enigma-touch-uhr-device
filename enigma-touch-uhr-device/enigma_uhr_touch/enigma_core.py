from __future__ import annotations

from dataclasses import dataclass

from .touch_settings import TouchSettings
from .uhr import ALPHABET, Plugboard


def wiring_tuple(wiring: str) -> tuple[int, ...]:
    values = tuple(ALPHABET.index(char) for char in wiring)
    if len(values) != 26 or set(values) != set(range(26)):
        raise ValueError("Rotor wiring must be a complete alphabet permutation.")
    return values


def letter_indexes(letters: str) -> tuple[int, ...]:
    return tuple(ALPHABET.index(letter) for letter in letters)


@dataclass(frozen=True)
class RotorSpec:
    name: str
    wiring: tuple[int, ...]
    notches: tuple[int, ...] = ()


ROTOR_SPECS = {
    "I": RotorSpec("I", wiring_tuple("EKMFLGDQVZNTOWYHXUSPAIBRCJ"), letter_indexes("Q")),
    "II": RotorSpec("II", wiring_tuple("AJDKSIRUXBLHWTMCQGZNPYFVOE"), letter_indexes("E")),
    "III": RotorSpec("III", wiring_tuple("BDFHJLCPRTXVZNYEIWGAKMUSQO"), letter_indexes("V")),
    "IV": RotorSpec("IV", wiring_tuple("ESOVPZJAYQUIRHXLNFTGKDCMWB"), letter_indexes("J")),
    "V": RotorSpec("V", wiring_tuple("VZBRGITYUPSDNHLXAWMJQOFECK"), letter_indexes("Z")),
    "VI": RotorSpec("VI", wiring_tuple("JPGVOUMFYQBENHZRDKASXLICTW"), letter_indexes("ZM")),
    "VII": RotorSpec("VII", wiring_tuple("NZJHGRCXMYSWBOUFAIVLPEKQDT"), letter_indexes("ZM")),
    "VIII": RotorSpec("VIII", wiring_tuple("FKQHTLXOCBJSPDZRAMEWNIUYGV"), letter_indexes("ZM")),
    "beta": RotorSpec("beta", wiring_tuple("LEYJVCNIXWPBQMDRTAKZGFUHOS")),
    "gamma": RotorSpec("gamma", wiring_tuple("FSOKANUERHMBTIYCWLQPZXVGJD")),
}

REFLECTORS = {
    "A": wiring_tuple("EJMZALYXVBWFCRQUONTSPIKHGD"),
    "B": wiring_tuple("YRUHQSLDPXNGOKMIEBFZCWVJAT"),
    "C": wiring_tuple("FVPJIAOYEDRZXWGCTKUQSBNMHL"),
}

M4_THIN_REFLECTORS = {
    "B": wiring_tuple("ENKQAUYWJICOPBLMDXZVFTHRGS"),
    "C": wiring_tuple("RDOBJNTKVEHMLFCWZAXGYIPSUQ"),
}

GERMAN_UKWD_LABELS_BY_BP_CONTACT = "AYZXWVUTSRQPONJMLKIHGFEDCB"
GERMAN_UKWD_TO_BP = {
    german_label: ALPHABET[index] for index, german_label in enumerate(GERMAN_UKWD_LABELS_BY_BP_CONTACT)
}


class EnigmaMachine:
    def __init__(
        self,
        *,
        rotors: tuple[RotorSpec, ...],
        reflector: tuple[int, ...],
        rings: tuple[int, ...],
        positions: tuple[int, ...],
        plugboard: Plugboard | None = None,
        moving_rotor_count: int = 3,
    ) -> None:
        if len(rotors) != len(rings) or len(rotors) != len(positions):
            raise ValueError("Rotor, ring, and position counts must match.")
        if moving_rotor_count > len(rotors):
            raise ValueError("Moving rotor count cannot exceed rotor count.")
        self.rotors = rotors
        self.reflector = reflector
        self.rings = list(rings)
        self.positions = list(positions)
        self.plugboard = plugboard
        self.moving_rotor_count = moving_rotor_count
        self._inverse_wirings = [invert_wiring(rotor.wiring) for rotor in rotors]

    def step(self) -> None:
        moving = list(range(len(self.rotors) - self.moving_rotor_count, len(self.rotors)))
        if len(moving) != 3:
            raise ValueError("Only three moving-rotor Enigma stepping is currently supported.")

        left, middle, right = moving
        step_rotors = {right}
        if self._at_notch(middle):
            step_rotors.add(left)
            step_rotors.add(middle)
        if self._at_notch(right):
            step_rotors.add(middle)

        for index in step_rotors:
            self.positions[index] = (self.positions[index] + 1) % 26

    def encipher_current(self, letter: str, *, use_plugboard: bool) -> str:
        value = ALPHABET.index(letter)
        if use_plugboard and self.plugboard:
            value = ALPHABET.index(self.plugboard.swap(ALPHABET[value]))

        for index in range(len(self.rotors) - 1, -1, -1):
            value = self._rotor_forward(index, value)

        value = self.reflector[value]

        for index in range(len(self.rotors)):
            value = self._rotor_backward(index, value)

        result = ALPHABET[value]
        if use_plugboard and self.plugboard:
            result = self.plugboard.swap(result)
        return result

    def encipher_letter(self, letter: str, *, use_plugboard: bool) -> str:
        self.step()
        return self.encipher_current(letter, use_plugboard=use_plugboard)

    def input_for_output_current(self, target_output: str, *, use_plugboard: bool) -> str:
        for letter in ALPHABET:
            if self.encipher_current(letter, use_plugboard=use_plugboard) == target_output:
                return letter
        raise ValueError(f"Could not find an Enigma input that produces {target_output!r}.")

    def position_values(self) -> tuple[int, ...]:
        return tuple(self.positions)

    def _at_notch(self, rotor_index: int) -> bool:
        return self.positions[rotor_index] in self.rotors[rotor_index].notches

    def _rotor_forward(self, rotor_index: int, value: int) -> int:
        shift = self.positions[rotor_index] - self.rings[rotor_index]
        wired = self.rotors[rotor_index].wiring[(value + shift) % 26]
        return (wired - shift) % 26

    def _rotor_backward(self, rotor_index: int, value: int) -> int:
        shift = self.positions[rotor_index] - self.rings[rotor_index]
        wired = self._inverse_wirings[rotor_index][(value + shift) % 26]
        return (wired - shift) % 26


def machine_from_touch_settings(
    settings: TouchSettings,
    plugboard: Plugboard,
    *,
    ahistoric: bool = False,
) -> EnigmaMachine:
    settings.require_uhr_supported(ahistoric=ahistoric)
    if settings.reflector == "D":
        reflector = reflector_from_german_pairs(settings.reflector_d_pairs)
    elif settings.model == "M4":
        try:
            reflector = M4_THIN_REFLECTORS[settings.reflector]
        except KeyError as exc:
            raise ValueError(f"Unsupported M4 reflector {settings.reflector!r}.") from exc
    else:
        try:
            reflector = REFLECTORS[settings.reflector]
        except KeyError as exc:
            raise ValueError(f"Unsupported reflector {settings.reflector!r}.") from exc

    rotors = tuple(rotor_spec(name) for name in settings.rotors)
    expected_count = 4 if settings.model == "M4" and settings.reflector != "D" else 3
    if len(rotors) != expected_count:
        raise ValueError(f"{settings.model_name} expects {expected_count} rotor values.")
    if len(settings.rings) != len(rotors) or len(settings.positions) != len(rotors):
        raise ValueError("Rotor, ring, and position counts from the Touch do not match.")

    return EnigmaMachine(
        rotors=rotors,
        reflector=reflector,
        rings=settings.rings,
        positions=settings.positions,
        plugboard=plugboard,
        moving_rotor_count=3,
    )


def rotor_spec(name: str) -> RotorSpec:
    try:
        return ROTOR_SPECS[name]
    except KeyError as exc:
        raise ValueError(f"Unsupported rotor {name!r}.") from exc


def reflector_from_german_pairs(pairs: str) -> tuple[int, ...]:
    wiring = list(range(26))
    seen: set[str] = set()
    tokens = pairs.split()
    if len(tokens) != 13:
        raise ValueError("Reflector D wiring must contain 13 letter pairs.")
    for token in tokens:
        if len(token) != 2 or token[0] not in GERMAN_UKWD_TO_BP or token[1] not in GERMAN_UKWD_TO_BP:
            raise ValueError(f"Invalid Reflector D pair {token!r}.")
        left = GERMAN_UKWD_TO_BP[token[0]]
        right = GERMAN_UKWD_TO_BP[token[1]]
        if left in seen or right in seen or left == right:
            raise ValueError("Reflector D wiring must pair each letter exactly once.")
        seen.update((left, right))
        left_index = ALPHABET.index(left)
        right_index = ALPHABET.index(right)
        wiring[left_index] = right_index
        wiring[right_index] = left_index
    if seen != set(ALPHABET):
        raise ValueError("Reflector D wiring must include every letter exactly once.")
    return tuple(wiring)


def invert_wiring(wiring: tuple[int, ...]) -> tuple[int, ...]:
    inverse = [0] * 26
    for index, value in enumerate(wiring):
        inverse[value] = index
    return tuple(inverse)
