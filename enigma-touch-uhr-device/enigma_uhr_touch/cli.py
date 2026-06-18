from __future__ import annotations

import argparse
import sys
from typing import Iterable

from .backends import (
    ManualBackend,
    SerialBackend,
    SerialConfig,
    TouchBackend,
    detect_plugboard_pairs,
    list_serial_ports,
)
from .uhr import Plugboard, Uhr, UhrAdapter


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="enigma-uhr-touch",
        description="Use an Enigma Touch as the rotor core with a software Enigma Uhr adapter.",
    )
    parser.add_argument("--pairs", help='Ordered plugboard pairs, for example: "AD CN ET FL GI JV KZ PU QY WX"')
    parser.add_argument(
        "--auto-pairs",
        action="store_true",
        help="Ask the Enigma Touch for its currently connected plugboard pairs over serial.",
    )
    parser.add_argument(
        "--pair-query",
        default="?PB",
        help='Serial command used by --auto-pairs. Default: "?PB"',
    )
    parser.add_argument(
        "--pair-query-ending",
        choices=["none", "cr", "lf", "crlf"],
        default="cr",
        help="Line ending sent after --pair-query. Default: cr, matching many terminal setups.",
    )
    parser.add_argument("--uhr", type=int, default=0, help="Uhr switch position, 0-39. Default: 0")
    parser.add_argument("--port", help="Serial port, for example COM5. Implies --backend serial.")
    parser.add_argument("--baud", type=int, default=2400, help="Serial baud rate. Default: 2400.")
    parser.add_argument("--timeout", type=float, default=2.0, help="Serial read/write timeout in seconds.")
    parser.add_argument(
        "--serial-protocol",
        choices=["char", "line", "command"],
        default="char",
        help="How to send a key to firmware: A, A newline, or KEY A newline.",
    )
    parser.add_argument(
        "--output-regex",
        help="Regex with one capture group for extracting output letters from detailed serial log lines.",
    )
    parser.add_argument(
        "--backend",
        choices=["serial", "manual"],
        help="Input backend. Default: serial when --port is supplied, otherwise manual.",
    )
    parser.add_argument("--group", type=int, default=0, help="Group output letters every N characters. Default: off.")
    parser.add_argument(
        "--strip-nonletters",
        action="store_true",
        help="Drop spaces and punctuation from displayed output instead of preserving them.",
    )
    parser.add_argument("--list-ports", action="store_true", help="List detected serial ports and exit.")
    parser.add_argument("--show-map", action="store_true", help="Show the current Uhr and wrapper mappings.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list_ports:
        try:
            ports = list_serial_ports()
        except RuntimeError as exc:
            parser.error(str(exc))
        if not ports:
            print("No serial ports found.")
        else:
            print("\n".join(ports))
        return 0

    if args.pairs and args.pairs.strip().lower() == "auto":
        args.auto_pairs = True

    if args.auto_pairs:
        if not args.port:
            parser.error("--auto-pairs requires --port.")
        try:
            args.pairs = detect_plugboard_pairs(
                SerialConfig(port=args.port, baud=args.baud, timeout=args.timeout),
                query=args.pair_query,
                query_ending=args.pair_query_ending,
            )
        except (RuntimeError, TimeoutError, ValueError) as exc:
            parser.error(str(exc))
        print(f"Detected plugboard pairs: {args.pairs}")

    if not args.pairs:
        parser.error("--pairs is required unless --auto-pairs or --list-ports is used.")

    try:
        plugboard = Plugboard.parse(args.pairs)
        uhr = Uhr(plugboard, args.uhr)
    except ValueError as exc:
        parser.error(str(exc))

    adapter = UhrAdapter(plugboard, uhr)
    if args.show_map:
        print_mapping(adapter)

    backend_name = args.backend or ("serial" if args.port else "manual")
    try:
        backend = create_backend(backend_name, args)
    except (RuntimeError, ValueError) as exc:
        parser.error(str(exc))

    try:
        run_repl(adapter, backend, group=args.group, preserve_nonletters=not args.strip_nonletters)
    except KeyboardInterrupt:
        print()
        return 130
    finally:
        backend.close()
    return 0


def create_backend(name: str, args: argparse.Namespace) -> TouchBackend:
    if name == "manual":
        return ManualBackend()
    if name == "serial":
        if not args.port:
            raise ValueError("--port is required for serial backend.")
        return SerialBackend(
            SerialConfig(
                port=args.port,
                baud=args.baud,
                timeout=args.timeout,
                protocol=args.serial_protocol,
                output_regex=args.output_regex,
            )
        )
    raise ValueError(f"Unknown backend: {name}")


def run_repl(
    adapter: UhrAdapter,
    backend: TouchBackend,
    *,
    group: int,
    preserve_nonletters: bool,
) -> None:
    print("Enter text to encipher/decipher. Commands: /map, /quit")
    while True:
        line = input("> ")
        command = line.strip().lower()
        if command in {"/quit", "/exit"}:
            return
        if command == "/map":
            print_mapping(adapter)
            continue
        result = process_text(adapter, backend, line, preserve_nonletters=preserve_nonletters)
        print(format_groups(result, group))


def process_text(
    adapter: UhrAdapter,
    backend: TouchBackend,
    text: str,
    *,
    preserve_nonletters: bool,
) -> str:
    output: list[str] = []
    for char in text.upper():
        if "A" <= char <= "Z":
            touch_input = adapter.to_touch(char)
            touch_output = backend.encipher_letter(touch_input)
            output.append(adapter.from_touch(touch_output))
        elif preserve_nonletters:
            output.append(char)
    return "".join(output)


def format_groups(text: str, group: int) -> str:
    if group <= 0:
        return text
    letters = [char for char in text if "A" <= char <= "Z"]
    grouped = " ".join("".join(chunk) for chunk in chunks(letters, group))
    return grouped


def chunks(values: list[str], size: int) -> Iterable[list[str]]:
    for index in range(0, len(values), size):
        yield values[index : index + size]


def print_mapping(adapter: UhrAdapter) -> None:
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    print(f"Uhr position: {adapter.uhr.position:02d}")
    print(f"Pairs: {adapter.plugboard}")
    print("Uhr:        " + "".join(adapter.uhr.forward(char) for char in alphabet))
    print("To Touch:   " + "".join(adapter.to_touch(char) for char in alphabet))
    print("From Touch: " + "".join(adapter.from_touch(char) for char in alphabet))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
