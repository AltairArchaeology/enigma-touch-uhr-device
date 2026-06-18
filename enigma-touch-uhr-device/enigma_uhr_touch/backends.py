from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass
from typing import Iterable, Optional, Protocol

from .uhr import Plugboard


class TouchBackend(Protocol):
    def encipher_letter(self, letter: str) -> str:
        """Send one already-adapted letter through the Enigma Touch core."""

    def close(self) -> None:
        """Release any external resources."""


class SerialOperationCancelled(Exception):
    """Raised when an active serial conversion is stopped by the user."""


class MockBackend:
    """Identity backend for testing the Uhr wrapper without hardware."""

    def encipher_letter(self, letter: str) -> str:
        return letter

    def close(self) -> None:
        return None


class ManualBackend:
    def encipher_letter(self, letter: str) -> str:
        while True:
            answer = input(f"Type {letter} on the Enigma Touch, then enter the lightboard letter: ")
            answer = answer.strip().upper()
            if len(answer) == 1 and "A" <= answer <= "Z":
                return answer
            print("Please enter one letter A-Z.")

    def close(self) -> None:
        return None


@dataclass(frozen=True)
class SerialConfig:
    port: str
    baud: int = 2400
    timeout: float = 2.0
    protocol: str = "char"
    output_regex: Optional[str] = None


class SerialBackend:
    def __init__(self, config: SerialConfig) -> None:
        try:
            import serial
        except ImportError as exc:
            raise RuntimeError(
                "Serial mode needs pyserial. Install it with: py -m pip install -r requirements.txt"
            ) from exc

        self.config = config
        self._serial = serial.Serial(
            config.port,
            baudrate=config.baud,
            timeout=min(config.timeout, 0.02),
            write_timeout=config.timeout,
        )
        self._regex = re.compile(config.output_regex) if config.output_regex else None
        self._letters_sent = 0
        self._stop_requested = threading.Event()
        drain_serial_input(
            self._serial,
            total_timeout=max(1.0, config.timeout),
            quiet_time=0.2,
        )

    def encipher_letter(self, letter: str) -> str:
        self._raise_if_stopped()
        if self._letters_sent == 0:
            drain_serial_input(
                self._serial,
                total_timeout=max(1.0, self.config.timeout),
                quiet_time=0.2,
            )
        else:
            drain_serial_input(self._serial, total_timeout=0.25, quiet_time=0.04)
        self._raise_if_stopped()
        self._serial.write(self._encode(letter))
        self._serial.flush()
        if self._regex:
            output = self._read_regex()
        else:
            output = self._read_first_letter()
        self._letters_sent += 1
        return output

    def close(self) -> None:
        self._serial.close()

    def request_stop(self) -> None:
        self._stop_requested.set()
        try:
            self._serial.cancel_read()
        except (AttributeError, OSError):
            pass

    def _raise_if_stopped(self) -> None:
        if self._stop_requested.is_set():
            raise SerialOperationCancelled("Conversion stopped by user.")

    def _encode(self, letter: str) -> bytes:
        if self.config.protocol == "char":
            return letter.encode("ascii")
        if self.config.protocol == "line":
            return f"{letter}\n".encode("ascii")
        if self.config.protocol == "command":
            return f"KEY {letter}\n".encode("ascii")
        raise ValueError(f"Unknown serial protocol: {self.config.protocol}")

    def _read_first_letter(self) -> str:
        first_letter = self._read_next_letter()
        letters = [first_letter]
        quiet_time = 0.15 if self._letters_sent == 0 else 0.04
        last_data_at = time.monotonic()
        deadline = time.monotonic() + self.config.timeout
        while time.monotonic() < deadline:
            byte = self._serial.read(1)
            now = time.monotonic()
            if byte:
                last_data_at = now
                char = byte.decode("ascii", errors="ignore").upper()
                if len(char) == 1 and "A" <= char <= "Z":
                    letters.append(char)
                continue
            self._raise_if_stopped()
            if now - last_data_at >= quiet_time:
                break
        return letters[-1]

    def _read_next_letter(self) -> str:
        deadline = time.monotonic() + self.config.timeout
        while time.monotonic() < deadline:
            byte = self._serial.read(1)
            if not byte:
                self._raise_if_stopped()
                continue
            char = byte.decode("ascii", errors="ignore").upper()
            if len(char) == 1 and "A" <= char <= "Z":
                return char
        raise TimeoutError("Timed out waiting for an output letter from the Enigma Touch.")

    def _read_regex(self) -> str:
        while True:
            raw = self._serial.readline()
            if not raw:
                raise TimeoutError("Timed out waiting for a matching output line from the Enigma Touch.")
            line = raw.decode("ascii", errors="ignore").strip()
            match = self._regex.search(line)
            if not match:
                continue
            value = match.group(1).upper()
            if len(value) != 1 or not ("A" <= value <= "Z"):
                raise ValueError(f"Output regex captured {value!r}, not a single A-Z letter.")
            return value


def list_serial_ports() -> list[str]:
    try:
        from serial.tools import list_ports
    except ImportError as exc:
        raise RuntimeError(
            "Listing serial ports needs pyserial. Install it with: py -m pip install -r requirements.txt"
        ) from exc
    return [f"{port.device} - {port.description}" for port in list_ports.comports()]


def drain_serial_input(serial_port, *, total_timeout: float = 0.5, quiet_time: float = 0.05) -> None:
    """Discard pending serial chatter and wait briefly for the stream to go quiet."""

    deadline = time.monotonic() + total_timeout
    last_data_at = time.monotonic()
    while time.monotonic() < deadline:
        try:
            waiting = serial_port.in_waiting
        except (AttributeError, OSError):
            waiting = 0

        if waiting:
            raw = serial_port.read(waiting)
            if raw:
                last_data_at = time.monotonic()
                continue
        now = time.monotonic()
        if now - last_data_at >= quiet_time:
            break
        time.sleep(min(0.005, quiet_time))


def detect_plugboard_pairs(
    config: SerialConfig,
    *,
    query: str = "?PB",
    query_prefix: str = "crlf",
    query_ending: str = "cr",
    expected_pairs: int = 10,
    attempts: int = 2,
    query_delay: float = 0.0,
) -> str:
    try:
        import serial
    except ImportError as exc:
        raise RuntimeError(
            "Auto-detecting plugboard pairs needs pyserial. Install it with: py -m pip install -r requirements.txt"
        ) from exc

    prefix = encode_query_ending(query_prefix)
    ending = encode_query_ending(query_ending)
    command = prefix + query.encode("ascii") + ending
    buffer = ""

    with serial.Serial(
        config.port,
        baudrate=config.baud,
        timeout=0.1,
        write_timeout=config.timeout,
    ) as serial_port:
        reset_serial_input(serial_port)
        drain_serial_input(
            serial_port,
            total_timeout=min(max(config.timeout, 0.25), 1.0),
            quiet_time=0.1,
        )
        if query_delay > 0:
            time.sleep(query_delay)

        for _attempt in range(max(1, attempts)):
            reset_serial_input(serial_port)
            serial_port.write(command)
            serial_port.flush()

            deadline = time.monotonic() + config.timeout
            while time.monotonic() < deadline:
                raw = serial_port.read(256)
                if not raw:
                    continue
                buffer += raw.decode("ascii", errors="ignore")
                pairs = parse_plugboard_pairs(buffer, expected_pairs=expected_pairs)
                if pairs:
                    drain_serial_input(serial_port, total_timeout=0.25, quiet_time=0.05)
                    return pairs

            drain_serial_input(serial_port, total_timeout=0.25, quiet_time=0.05)

    raise TimeoutError(
        f"Timed out waiting for {expected_pairs} plugboard pairs after sending {query!r}. "
        f"Received: {buffer.strip() or '<nothing>'}"
    )


def query_touch_command(
    config: SerialConfig,
    command: str,
    *,
    query_prefix: str = "crlf",
    query_ending: str = "cr",
    query_delay: float = 0.0,
    quiet_time: float = 0.2,
) -> str:
    responses = query_touch_commands(
        config,
        (command,),
        query_prefix=query_prefix,
        query_ending=query_ending,
        query_delay=query_delay,
        quiet_time=quiet_time,
    )
    return responses[normalize_query_command(command)]


def query_touch_commands(
    config: SerialConfig,
    commands: Iterable[str],
    *,
    query_prefix: str = "crlf",
    query_ending: str = "cr",
    query_delay: float = 0.0,
    quiet_time: float = 0.2,
) -> dict[str, str]:
    try:
        import serial
    except ImportError as exc:
        raise RuntimeError(
            "Reading Enigma Touch settings needs pyserial. Install it with: py -m pip install -r requirements.txt"
        ) from exc

    prefix = encode_query_ending(query_prefix)
    ending = encode_query_ending(query_ending)
    normalized_commands = [normalize_query_command(command) for command in commands]
    responses: dict[str, str] = {}

    with serial.Serial(
        config.port,
        baudrate=config.baud,
        timeout=0.1,
        write_timeout=config.timeout,
    ) as serial_port:
        reset_serial_input(serial_port)
        drain_serial_input(
            serial_port,
            total_timeout=min(max(config.timeout, 0.25), 1.0),
            quiet_time=0.1,
        )
        if query_delay > 0:
            time.sleep(query_delay)

        for command in normalized_commands:
            reset_serial_input(serial_port)
            serial_port.write(prefix + command.encode("ascii") + ending)
            serial_port.flush()
            responses[command] = read_serial_response(
                serial_port,
                total_timeout=config.timeout,
                quiet_time=quiet_time,
            )

    return responses


def normalize_query_command(command: str) -> str:
    normalized = command.strip().upper()
    if not normalized:
        raise ValueError("Serial query command cannot be empty.")
    if not normalized.startswith(("?", "!")):
        normalized = "?" + normalized
    if len(normalized) < 3:
        raise ValueError("Serial query command must include a two-letter instruction.")
    return normalized


def read_serial_response(serial_port, *, total_timeout: float, quiet_time: float) -> str:
    buffer = bytearray()
    deadline = time.monotonic() + total_timeout
    last_data_at: float | None = None

    while time.monotonic() < deadline:
        raw = serial_port.read(256)
        now = time.monotonic()
        if raw:
            buffer.extend(raw)
            last_data_at = now
            continue
        if last_data_at is not None and now - last_data_at >= quiet_time:
            break

    if not buffer:
        raise TimeoutError("Timed out waiting for a response from the Enigma Touch.")
    drain_serial_input(serial_port, total_timeout=0.25, quiet_time=0.05)
    return buffer.decode("ascii", errors="ignore")


def reset_serial_input(serial_port) -> None:
    try:
        serial_port.reset_input_buffer()
    except AttributeError:
        return


def encode_query_ending(name: str) -> bytes:
    endings = {
        "none": b"",
        "cr": b"\r",
        "lf": b"\n",
        "crlf": b"\r\n",
    }
    try:
        return endings[name]
    except KeyError as exc:
        raise ValueError("query ending must be one of: none, cr, lf, crlf") from exc


def parse_plugboard_pairs(text: str, *, expected_pairs: int = 10) -> Optional[str]:
    normalized = text.upper()
    marker_match = list(re.finditer(r"PLUGBOARD|STECKER(?:BRETT)?", normalized))
    if marker_match:
        marker_text = normalized[marker_match[-1].end() :]
        pairs = find_pair_window(marker_text, expected_pairs=expected_pairs)
        if pairs:
            return pairs

    return find_pair_window(normalized, expected_pairs=expected_pairs)


def find_pair_window(text: str, *, expected_pairs: int) -> Optional[str]:
    tokens = re.findall(r"(?<![A-Z])[A-Z]{2}(?![A-Z])", text)
    for start in range(0, len(tokens) - expected_pairs + 1):
        window = tokens[start : start + expected_pairs]
        try:
            Plugboard.parse(" ".join(window))
        except ValueError:
            continue
        return " ".join(window)
    return None
