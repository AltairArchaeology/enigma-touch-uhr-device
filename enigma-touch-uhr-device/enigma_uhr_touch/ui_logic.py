from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from .backends import TouchBackend
from .enigma_core import EnigmaMachine
from .uhr import ALPHABET, UhrAdapter


@dataclass(frozen=True)
class PreparedTouchInput:
    original_text: str
    touch_letters: str
    preserve_nonletters: bool
    plugboard_pairs: tuple[tuple[str, str], ...]
    uhr_position: int

    @property
    def letter_count(self) -> int:
        return len(self.touch_letters)


@dataclass(frozen=True)
class ConversionProgress:
    touch_input_text: str
    touch_output_text: str
    output_text: str
    completed_letters: int
    total_letters: int


class ConversionStopped(Exception):
    def __init__(self, output_text: str, completed_letters: int, total_letters: int) -> None:
        super().__init__("Conversion stopped by user.")
        self.output_text = output_text
        self.completed_letters = completed_letters
        self.total_letters = total_letters


def prepare_touch_input(
    adapter: UhrAdapter,
    text: str,
    *,
    preserve_nonletters: bool,
) -> PreparedTouchInput:
    original_text = text.upper()
    touch_letters = "".join(adapter.to_touch(char) for char in original_text if char in ALPHABET)
    return PreparedTouchInput(
        original_text=original_text,
        touch_letters=touch_letters,
        preserve_nonletters=preserve_nonletters,
        plugboard_pairs=adapter.plugboard.pairs,
        uhr_position=adapter.uhr.position,
    )


def finish_manual_conversion(
    adapter: UhrAdapter,
    prepared: PreparedTouchInput,
    touch_output: str,
) -> str:
    validate_prepared_settings(adapter, prepared)
    output_letters = sanitize_letters(touch_output)
    if len(output_letters) != prepared.letter_count:
        raise ValueError(
            f"Expected {prepared.letter_count} Touch output letters, but received {len(output_letters)}."
        )

    output: list[str] = []
    output_index = 0
    for char in prepared.original_text:
        if char in ALPHABET:
            output.append(adapter.from_touch(output_letters[output_index]))
            output_index += 1
        elif prepared.preserve_nonletters:
            output.append(char)
    return "".join(output)


def validate_prepared_settings(adapter: UhrAdapter, prepared: PreparedTouchInput) -> None:
    if (
        adapter.plugboard.pairs != prepared.plugboard_pairs
        or adapter.uhr.position != prepared.uhr_position
    ):
        raise ValueError("Settings changed since Touch input was prepared. Click Convert again first.")


def convert_with_backend(
    adapter: UhrAdapter,
    backend: TouchBackend,
    text: str,
    *,
    preserve_nonletters: bool,
) -> str:
    return convert_with_backend_stream(
        adapter,
        backend,
        text,
        preserve_nonletters=preserve_nonletters,
    )


def convert_with_backend_stream(
    adapter: UhrAdapter,
    backend: TouchBackend,
    text: str,
    *,
    preserve_nonletters: bool,
    progress: Callable[[ConversionProgress], None] | None = None,
) -> str:
    output: list[str] = []
    touch_inputs: list[str] = []
    touch_outputs: list[str] = []
    original_text = text.upper()
    total_letters = sum(1 for char in original_text if char in ALPHABET)
    completed_letters = 0

    for char in original_text:
        if char in ALPHABET:
            touch_input = adapter.to_touch(char)
            touch_inputs.append(touch_input)
            touch_output = backend.encipher_letter(touch_input)
            touch_outputs.append(touch_output)
            output.append(adapter.from_touch(touch_output))
            completed_letters += 1
            emit_progress(
                progress,
                touch_inputs,
                touch_outputs,
                output,
                completed_letters,
                total_letters,
            )
        elif preserve_nonletters:
            output.append(char)
            emit_progress(
                progress,
                touch_inputs,
                touch_outputs,
                output,
                completed_letters,
                total_letters,
            )
    return "".join(output)


def convert_direct_with_backend_stream(
    adapter: UhrAdapter,
    machine: EnigmaMachine,
    backend: TouchBackend,
    text: str,
    *,
    preserve_nonletters: bool,
    progress: Callable[[ConversionProgress], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> str:
    output: list[str] = []
    touch_inputs: list[str] = []
    touch_outputs: list[str] = []
    original_text = text.upper()
    total_letters = sum(1 for char in original_text if char in ALPHABET)
    completed_letters = 0

    for char in original_text:
        if should_stop and should_stop():
            raise ConversionStopped("".join(output), completed_letters, total_letters)
        if char in ALPHABET:
            machine.step()
            target_output = adapter.uhr.inverse(
                machine.encipher_current(adapter.uhr.forward(char), use_plugboard=False)
            )
            touch_input = machine.input_for_output_current(target_output, use_plugboard=True)
            touch_inputs.append(touch_input)
            try:
                touch_output = backend.encipher_letter(touch_input)
            except Exception as exc:
                if should_stop and should_stop():
                    raise ConversionStopped("".join(output), completed_letters, total_letters) from exc
                raise
            touch_outputs.append(touch_output)
            if touch_output != target_output:
                raise ValueError(
                    f"Touch output {touch_output!r} did not match calculated Uhr result {target_output!r}. "
                    "Read Enigma Touch settings again and confirm the rotor positions have not changed."
                )
            output.append(touch_output)
            completed_letters += 1
            emit_progress(
                progress,
                touch_inputs,
                touch_outputs,
                output,
                completed_letters,
                total_letters,
            )
        elif preserve_nonletters:
            output.append(char)
            emit_progress(
                progress,
                touch_inputs,
                touch_outputs,
                output,
                completed_letters,
                total_letters,
            )
    return "".join(output)


def emit_progress(
    progress: Callable[[ConversionProgress], None] | None,
    touch_inputs: list[str],
    touch_outputs: list[str],
    output: list[str],
    completed_letters: int,
    total_letters: int,
) -> None:
    if not progress:
        return
    progress(
        ConversionProgress(
            touch_input_text="".join(touch_inputs),
            touch_output_text="".join(touch_outputs),
            output_text="".join(output),
            completed_letters=completed_letters,
            total_letters=total_letters,
        )
    )


def sanitize_letters(text: str) -> str:
    return "".join(char for char in text.upper() if char in ALPHABET)


def format_groups(text: str, group: int) -> str:
    if group <= 0:
        return text
    letters = [char for char in text if char in ALPHABET]
    return " ".join("".join(chunk) for chunk in chunks(letters, group))


def chunks(values: list[str], size: int) -> Iterable[list[str]]:
    for index in range(0, len(values), size):
        yield values[index : index + size]


def extract_port_device(port_label: str) -> str:
    port = port_label.strip()
    if not port:
        raise ValueError("Choose a serial port first.")
    return port.split(" - ", 1)[0].strip()


def mapping_lines(adapter: UhrAdapter) -> str:
    alphabet = ALPHABET
    return "\n".join(
        [
            f"Uhr Device mode: {'Ahistoric' if adapter.uhr.ahistoric else 'Historical'}",
            f"Uhr Device position: {adapter.uhr.position:02d}",
            f"Pairs: {adapter.plugboard}",
            "Alphabet:   " + alphabet,
            "Uhr:        " + "".join(adapter.uhr.forward(char) for char in alphabet),
            "To Touch:   " + "".join(adapter.to_touch(char) for char in alphabet),
            "From Touch: " + "".join(adapter.from_touch(char) for char in alphabet),
        ]
    )
