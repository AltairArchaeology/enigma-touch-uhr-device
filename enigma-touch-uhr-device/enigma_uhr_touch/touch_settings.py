from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping

from .uhr import ALPHABET, Plugboard

MODEL_NAMES = {
    "I": "Enigma I",
    "M3": "M3",
    "M4": "M4",
    "D": "Enigma D",
    "K": "Enigma K",
    "KD": "Enigma K, Reflector D",
    "KR": "Railway K",
    "KS": "Swiss K",
    "N": "Norway",
    "T": "Tirpitz",
    "G": "Enigma G",
    "G1": "G111",
    "G2": "G219",
    "G3": "G312",
    "X": "Custom",
}

UHR_MODEL_CODES = {"I", "M3", "M4"}


@dataclass(frozen=True)
class TouchSettings:
    model: str
    reflector: str
    rotors: tuple[str, ...]
    rings: tuple[int, ...]
    positions: tuple[int, ...]
    plugboard_pairs: str
    reflector_d_pairs: str = ""

    @property
    def model_name(self) -> str:
        return MODEL_NAMES.get(self.model, self.model)

    @property
    def has_uhr_plugboard(self) -> bool:
        return self.model in UHR_MODEL_CODES

    @property
    def uses_numeric_labels(self) -> bool:
        return self.model == "I"

    def require_uhr_supported(self, *, ahistoric: bool = False) -> None:
        if self.model == "X":
            raise ValueError("Custom model support is not enabled yet.")
        if not self.has_uhr_plugboard:
            raise ValueError(f"{self.model_name} does not have an active plugboard, so Uhr conversion is not available.")
        Plugboard.parse(self.plugboard_pairs, ahistoric=ahistoric)

    def rings_display(self) -> str:
        return format_setting_values(self.rings, numeric=self.uses_numeric_labels)

    def positions_display(self) -> str:
        return format_setting_values(self.positions, numeric=self.uses_numeric_labels)


def parse_touch_settings(responses: Mapping[str, str]) -> TouchSettings:
    model = parse_model_response(responses["?MO"])
    reflector, rotors = parse_rotor_response(responses["?RO"])
    rings = parse_setting_values(value_after_label(responses["?RI"], "Rings"))
    positions = parse_setting_values(value_after_label(responses["?RP"], "Positions"))
    plugboard_pairs = parse_pair_response(responses.get("?PB", ""), "Plugboard")
    reflector_d_pairs = parse_pair_response(responses.get("?RD", ""), "UKW D")
    return TouchSettings(
        model=model,
        reflector=reflector,
        rotors=rotors,
        rings=rings,
        positions=positions,
        plugboard_pairs=plugboard_pairs,
        reflector_d_pairs=reflector_d_pairs,
    )


def build_touch_settings(
    *,
    model: str,
    reflector: str,
    rotors: str,
    rings: str,
    positions: str,
    plugboard_pairs: str,
    reflector_d_pairs: str = "",
) -> TouchSettings:
    return TouchSettings(
        model=normalize_model_code(model),
        reflector=normalize_reflector(reflector),
        rotors=tuple(normalize_rotor_name(token) for token in rotors.split()),
        rings=parse_setting_values(rings),
        positions=parse_setting_values(positions),
        plugboard_pairs=format_pair_tokens(plugboard_pairs),
        reflector_d_pairs=format_pair_tokens(reflector_d_pairs),
    )


def parse_model_response(text: str) -> str:
    return normalize_model_code(value_after_label(text, "Enigma"))


def parse_rotor_response(text: str) -> tuple[str, tuple[str, ...]]:
    reflector = normalize_reflector(value_after_label(text, "Reflector"))
    rotors = tuple(normalize_rotor_name(token) for token in value_after_label(text, "Rotors").split())
    if not rotors:
        raise ValueError("Rotor response did not include any rotors.")
    return reflector, rotors


def parse_setting_values(text: str) -> tuple[int, ...]:
    tokens = text.replace(",", " ").split()
    values: list[int] = []
    for token in tokens:
        token = token.strip().upper()
        if len(token) == 1 and token in ALPHABET:
            values.append(ALPHABET.index(token))
            continue
        if re.fullmatch(r"\d{1,2}", token):
            value = int(token)
            if 1 <= value <= 26:
                values.append(value - 1)
                continue
        raise ValueError(f"Invalid ring or position value {token!r}.")
    if not values:
        raise ValueError("Expected at least one ring or position value.")
    return tuple(values)


def parse_pair_response(text: str, label: str) -> str:
    try:
        value = value_after_label(text, label)
    except ValueError:
        return ""
    return format_pair_tokens(value)


def format_pair_tokens(text: str) -> str:
    pairs = re.findall(r"(?<![A-Z])[A-Z]{2}(?![A-Z])", text.upper())
    return " ".join(pairs)


def value_after_label(text: str, label: str) -> str:
    normalized = text.replace("\x00", "")
    label_upper = label.upper()
    matches: list[str] = []
    for line in normalized.splitlines():
        stripped = line.strip()
        if not stripped.upper().startswith(label_upper):
            continue
        value = stripped[len(label) :].strip()
        if value:
            matches.append(value)
    if not matches:
        raise ValueError(f"Could not find {label!r} in Enigma Touch response: {text.strip()!r}")
    return matches[-1]


def normalize_model_code(value: str) -> str:
    model = value.strip().upper()
    if model not in MODEL_NAMES:
        raise ValueError(f"Unsupported Enigma Touch model {model!r}.")
    return model


def normalize_reflector(value: str) -> str:
    reflector = value.strip().upper()
    if not reflector:
        raise ValueError("Reflector cannot be empty.")
    return reflector


def normalize_rotor_name(value: str) -> str:
    rotor = value.strip()
    lower = rotor.lower()
    if lower in {"beta", "gamma"}:
        return lower
    return rotor.upper()


def format_setting_values(values: tuple[int, ...], *, numeric: bool) -> str:
    if numeric:
        return " ".join(f"{value + 1:02d}" for value in values)
    return " ".join(ALPHABET[value] for value in values)
