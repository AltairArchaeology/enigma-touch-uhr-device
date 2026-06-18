from __future__ import annotations

from dataclasses import dataclass

ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

# Published Enigma Uhr fixed wiring: white contact -> red contact.
UHR_WIRING = (
    26,
    11,
    24,
    21,
    2,
    31,
    0,
    25,
    30,
    39,
    28,
    13,
    22,
    35,
    20,
    37,
    6,
    23,
    4,
    33,
    34,
    19,
    32,
    9,
    18,
    7,
    16,
    17,
    10,
    3,
    8,
    1,
    38,
    27,
    36,
    29,
    14,
    15,
    12,
    5,
)

INVERSE_UHR_WIRING = tuple(sorted(range(40), key=lambda contact: UHR_WIRING[contact]))

# Contact labels at Uhr position 00. Only every other contact is used; positions
# 01-39 rotate the labels around the 40-contact switch.
RED_CONTACTS_POSITION_00 = (
    ("1a", "thick"),
    ("1a", "thin"),
    ("2a", "thick"),
    ("2a", "thin"),
    ("3a", "thick"),
    ("3a", "thin"),
    ("4a", "thick"),
    ("4a", "thin"),
    ("5a", "thick"),
    ("5a", "thin"),
    ("6a", "thick"),
    ("6a", "thin"),
    ("7a", "thick"),
    ("7a", "thin"),
    ("8a", "thick"),
    ("8a", "thin"),
    ("9a", "thick"),
    ("9a", "thin"),
    ("10a", "thick"),
    ("10a", "thin"),
)

WHITE_CONTACTS_POSITION_00 = (
    ("7b", "thick"),
    ("7b", "thin"),
    ("1b", "thick"),
    ("1b", "thin"),
    ("8b", "thick"),
    ("8b", "thin"),
    ("6b", "thick"),
    ("6b", "thin"),
    ("2b", "thick"),
    ("2b", "thin"),
    ("9b", "thick"),
    ("9b", "thin"),
    ("5b", "thick"),
    ("5b", "thin"),
    ("3b", "thick"),
    ("3b", "thin"),
    ("10b", "thick"),
    ("10b", "thin"),
    ("4b", "thick"),
    ("4b", "thin"),
)


@dataclass(frozen=True)
class Plugboard:
    pairs: tuple[tuple[str, str], ...]

    @classmethod
    def parse(cls, text: str, *, ahistoric: bool = False) -> "Plugboard":
        raw_pairs = text.replace(",", " ").split()
        pairs: list[tuple[str, str]] = []
        seen: set[str] = set()
        for raw_pair in raw_pairs:
            pair = raw_pair.strip().upper()
            if len(pair) != 2 or not all(char in ALPHABET for char in pair):
                raise ValueError(f"Invalid plugboard pair {raw_pair!r}; use pairs like AD CN ET.")
            left, right = pair
            if left == right:
                raise ValueError(f"Invalid plugboard pair {pair!r}; a letter cannot plug to itself.")
            duplicate = seen.intersection(pair)
            if duplicate:
                letter = sorted(duplicate)[0]
                raise ValueError(f"Letter {letter} appears in more than one plugboard pair.")
            seen.update(pair)
            pairs.append((left, right))
        if ahistoric:
            if not 1 <= len(pairs) <= 13:
                raise ValueError("The ahistoric Uhr Device requires between one and thirteen plugboard pairs.")
        elif len(pairs) != 10:
            raise ValueError("The historical Uhr Device requires exactly ten plugboard pairs.")
        return cls(tuple(pairs))

    def swap(self, letter: str) -> str:
        for left, right in self.pairs:
            if letter == left:
                return right
            if letter == right:
                return left
        return letter

    def label_to_letter(self) -> dict[str, str]:
        labels: dict[str, str] = {}
        for index, (left, right) in enumerate(self.pairs, start=1):
            labels[f"{index}a"] = left
            labels[f"{index}b"] = right
        return labels

    def __str__(self) -> str:
        return " ".join(f"{left}{right}" for left, right in self.pairs)


class Uhr:
    def __init__(self, plugboard: Plugboard, position: int, *, ahistoric: bool = False) -> None:
        if not 0 <= position <= 39:
            raise ValueError("Uhr position must be between 0 and 39.")
        pair_count = len(plugboard.pairs)
        if ahistoric:
            if not 1 <= pair_count <= 13:
                raise ValueError("The ahistoric Uhr Device requires between one and thirteen plugboard pairs.")
        elif pair_count != 10:
            raise ValueError("The historical Uhr Device requires exactly ten plugboard pairs.")
        self.plugboard = plugboard
        self.position = position
        self.ahistoric = ahistoric
        self._forward = self._build_forward_mapping()
        self._inverse = invert_mapping(self._forward)

    def forward(self, letter: str) -> str:
        return self._forward[letter]

    def inverse(self, letter: str) -> str:
        return self._inverse[letter]

    def mapping(self) -> dict[str, str]:
        return dict(self._forward)

    def inverse_mapping(self) -> dict[str, str]:
        return dict(self._inverse)

    def _build_forward_mapping(self) -> dict[str, str]:
        label_to_letter = self.plugboard.label_to_letter()
        label_mapping = self._historical_label_mapping()
        pair_count = len(self.plugboard.pairs)

        if pair_count < 10:
            label_mapping = contract_label_mapping(label_mapping, pair_count)
        elif pair_count > 10:
            label_mapping = extend_label_mapping(label_mapping, pair_count, self.position)

        mapping = {letter: letter for letter in ALPHABET}
        for label, mapped_label in label_mapping.items():
            mapping[label_to_letter[label]] = label_to_letter[mapped_label]

        validate_permutation(mapping)
        return mapping

    def _historical_label_mapping(self) -> dict[str, str]:
        (
            red_contact_to_label,
            white_contact_to_label,
            red_keyboard_label_to_contact,
            white_keyboard_label_to_contact,
        ) = self._rotated_contacts()
        mapping: dict[str, str] = {}

        for label, red_contact in red_keyboard_label_to_contact.items():
            white_contact = INVERSE_UHR_WIRING[red_contact]
            mapping[label] = white_contact_to_label[white_contact]

        for label, white_contact in white_keyboard_label_to_contact.items():
            red_contact = UHR_WIRING[white_contact]
            mapping[label] = red_contact_to_label[red_contact]

        return mapping

    def _rotated_contacts(
        self,
    ) -> tuple[dict[int, str], dict[int, str], dict[str, int], dict[str, int]]:
        red_contact_to_label: dict[int, str] = {}
        white_contact_to_label: dict[int, str] = {}
        red_keyboard_label_to_contact: dict[str, int] = {}
        white_keyboard_label_to_contact: dict[str, int] = {}

        for index, (label, pin) in enumerate(RED_CONTACTS_POSITION_00):
            contact = (2 * index + self.position) % 40
            red_contact_to_label[contact] = label
            if pin == "thick":
                red_keyboard_label_to_contact[label] = contact

        for index, (label, pin) in enumerate(WHITE_CONTACTS_POSITION_00):
            contact = (2 * index + self.position) % 40
            white_contact_to_label[contact] = label
            if pin == "thick":
                white_keyboard_label_to_contact[label] = contact

        return red_contact_to_label, white_contact_to_label, red_keyboard_label_to_contact, white_keyboard_label_to_contact


def endpoint_labels(pair_count: int) -> tuple[str, ...]:
    return tuple(f"{slot}{end}" for slot in range(1, pair_count + 1) for end in ("a", "b"))


def contract_label_mapping(mapping: dict[str, str], pair_count: int) -> dict[str, str]:
    # Remove absent sockets from each historical cycle while preserving its order.
    active_labels = endpoint_labels(pair_count)
    active = set(active_labels)
    contracted: dict[str, str] = {}
    for label in active_labels:
        mapped_label = mapping[label]
        while mapped_label not in active:
            mapped_label = mapping[mapped_label]
        contracted[label] = mapped_label
    return contracted


def extend_label_mapping(mapping: dict[str, str], pair_count: int, position: int) -> dict[str, str]:
    if position == 0:
        return {
            f"{slot}{end}": f"{slot}{'b' if end == 'a' else 'a'}"
            for slot in range(1, pair_count + 1)
            for end in ("a", "b")
        }

    extended = dict(mapping)
    labels = list(endpoint_labels(10))
    for slot in range(11, pair_count + 1):
        for end_index, end in enumerate(("a", "b")):
            label = f"{slot}{end}"
            # Fixed strides spread new endpoints across existing cycle edges reproducibly.
            anchor_index = (position * 7 + slot * 5 + end_index * 11) % len(labels)
            anchor = labels[anchor_index]
            extended[label] = extended[anchor]
            extended[anchor] = label
            labels.append(label)
    return extended


@dataclass(frozen=True)
class UhrAdapter:
    plugboard: Plugboard
    uhr: Uhr

    def to_touch(self, letter: str) -> str:
        """Convert user input to the letter that should be sent to the plugged Touch."""

        return self.plugboard.swap(self.uhr.forward(letter))

    def from_touch(self, letter: str) -> str:
        """Convert the plugged Touch output back to Uhr-adjusted output."""

        return self.uhr.inverse(self.plugboard.swap(letter))


def invert_mapping(mapping: dict[str, str]) -> dict[str, str]:
    inverse = {value: key for key, value in mapping.items()}
    if len(inverse) != len(mapping):
        raise ValueError("Mapping is not one-to-one.")
    return inverse


def validate_permutation(mapping: dict[str, str]) -> None:
    if set(mapping) != set(ALPHABET) or set(mapping.values()) != set(ALPHABET):
        raise ValueError("Uhr mapping is not a complete alphabet permutation.")
