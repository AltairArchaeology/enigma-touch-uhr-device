import sys
import types
import unittest

from enigma_uhr_touch.backends import (
    detect_plugboard_pairs,
    SerialBackend,
    SerialConfig,
    SerialOperationCancelled,
    drain_serial_input,
    encode_query_ending,
    parse_plugboard_pairs,
    query_touch_commands,
)


class PlugboardDetectionTests(unittest.TestCase):
    def test_serial_config_default_baud_is_2400(self):
        self.assertEqual(SerialConfig("COM7").baud, 2400)

    def test_parse_plugboard_line(self):
        text = "Plugboard AD CN ET FL GI JV KZ PU QY WX\r\n"
        self.assertEqual(parse_plugboard_pairs(text), "AD CN ET FL GI JV KZ PU QY WX")

    def test_parse_after_command_echo(self):
        text = "?PB\r\nPlugboard \r\nAD CN ET FL GI JV KZ PU QY WX\r\n"
        self.assertEqual(parse_plugboard_pairs(text), "AD CN ET FL GI JV KZ PU QY WX")

    def test_parse_without_marker(self):
        text = "current pairs: AD CN ET FL GI JV KZ PU QY WX"
        self.assertEqual(parse_plugboard_pairs(text), "AD CN ET FL GI JV KZ PU QY WX")

    def test_ignore_invalid_duplicate_window(self):
        text = "Plugboard AD AC ET FL GI JV KZ PU QY WX"
        self.assertIsNone(parse_plugboard_pairs(text))

    def test_encode_query_endings(self):
        self.assertEqual(encode_query_ending("none"), b"")
        self.assertEqual(encode_query_ending("cr"), b"\r")
        self.assertEqual(encode_query_ending("lf"), b"\n")
        self.assertEqual(encode_query_ending("crlf"), b"\r\n")

    def test_detect_plugboard_starts_command_on_fresh_line(self):
        pairs = b"Plugboard AD CN ET FL GI JV KZ PU QY WX\r\n"

        class CommandSerial(FakeSerialPort):
            instances = []

            def __init__(self, *args, **kwargs):
                super().__init__(b"")
                self.timeout = kwargs["timeout"]
                self.writes = []
                self.__class__.instances.append(self)

            def reset_input_buffer(self):
                self.buffer.clear()

            def write(self, data):
                self.writes.append(data)
                self.buffer.extend(pairs)
                return len(data)

            def flush(self):
                return None

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        previous_serial = sys.modules.get("serial")
        sys.modules["serial"] = types.SimpleNamespace(Serial=CommandSerial)
        try:
            result = detect_plugboard_pairs(SerialConfig("COM7", timeout=0.01), attempts=1)
        finally:
            if previous_serial is None:
                del sys.modules["serial"]
            else:
                sys.modules["serial"] = previous_serial

        self.assertEqual(result, pairs.decode("ascii").split(" ", 1)[1].strip())
        self.assertEqual(CommandSerial.instances[0].writes, [b"\r\n?PB\r"])

    def test_query_touch_commands_start_each_command_on_fresh_line(self):
        class CommandSerial(FakeSerialPort):
            instances = []

            def __init__(self, *args, **kwargs):
                super().__init__(b"")
                self.timeout = kwargs["timeout"]
                self.writes = []
                self.__class__.instances.append(self)

            def reset_input_buffer(self):
                self.buffer.clear()

            def write(self, data):
                self.writes.append(data)
                self.buffer.extend(b"OK\r\n")
                return len(data)

            def flush(self):
                return None

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        previous_serial = sys.modules.get("serial")
        sys.modules["serial"] = types.SimpleNamespace(Serial=CommandSerial)
        try:
            responses = query_touch_commands(SerialConfig("COM7", timeout=0.01), ("MO", "?RO"))
        finally:
            if previous_serial is None:
                del sys.modules["serial"]
            else:
                sys.modules["serial"] = previous_serial

        self.assertEqual(responses, {"?MO": "OK\r\n", "?RO": "OK\r\n"})
        self.assertEqual(CommandSerial.instances[0].writes, [b"\r\n?MO\r", b"\r\n?RO\r"])

    def test_drain_serial_input_discards_pending_text(self):
        port = FakeSerialPort(b"Plugboard P\r\n")

        drain_serial_input(port, total_timeout=0.02, quiet_time=0.001)

        self.assertEqual(port.buffer, b"")
        self.assertEqual(port.timeout, 2.0)

    def test_detect_plugboard_retries_after_status_chatter(self):
        pairs = b"Plugboard AD CN ET FL GI JV KZ PU QY WX\r\n"

        class NoisyPairSerial(FakeSerialPort):
            def __init__(self, *args, **kwargs):
                super().__init__(b"")
                self.timeout = kwargs["timeout"]
                self.write_count = 0

            def reset_input_buffer(self):
                self.buffer.clear()

            def write(self, data):
                self.write_count += 1
                if self.write_count == 1:
                    self.buffer.extend(b"?\r\nPositions A A A A\r\nbp\r\n")
                else:
                    self.buffer.extend(pairs)
                return len(data)

            def flush(self):
                return None

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        previous_serial = sys.modules.get("serial")
        sys.modules["serial"] = types.SimpleNamespace(Serial=NoisyPairSerial)
        try:
            result = detect_plugboard_pairs(SerialConfig("COM7", timeout=0.01))
        finally:
            if previous_serial is None:
                del sys.modules["serial"]
            else:
                sys.modules["serial"] = previous_serial

        self.assertEqual(result, pairs.decode("ascii").split(" ", 1)[1].strip())

    def test_serial_backend_ignores_stale_text_before_lamp_letter(self):
        class ScriptedSerial(FakeSerialPort):
            instances = []

            def __init__(self, *args, **kwargs):
                super().__init__(b"Plugboard P\r\n")
                self.timeout = kwargs["timeout"]
                self.writes = []
                self.closed = False
                self.__class__.instances.append(self)

            def write(self, data):
                self.writes.append(data)
                self.buffer.extend(b"c")
                return len(data)

            def flush(self):
                return None

            def close(self):
                self.closed = True

        previous_serial = sys.modules.get("serial")
        sys.modules["serial"] = types.SimpleNamespace(Serial=ScriptedSerial)
        try:
            backend = SerialBackend(SerialConfig("COM7", timeout=2.0))
            try:
                self.assertEqual(backend.encipher_letter("H"), "C")
            finally:
                backend.close()
        finally:
            if previous_serial is None:
                del sys.modules["serial"]
            else:
                sys.modules["serial"] = previous_serial

    def test_serial_backend_uses_last_letter_in_first_response_burst(self):
        class BurstSerial(FakeSerialPort):
            def __init__(self, *args, **kwargs):
                super().__init__(b"")
                self.timeout = kwargs["timeout"]

            def write(self, data):
                self.buffer.extend(b"Pc")
                return len(data)

            def flush(self):
                return None

            def close(self):
                return None

        previous_serial = sys.modules.get("serial")
        sys.modules["serial"] = types.SimpleNamespace(Serial=BurstSerial)
        try:
            backend = SerialBackend(SerialConfig("COM7", timeout=0.3))
            try:
                self.assertEqual(backend.encipher_letter("H"), "C")
            finally:
                backend.close()
        finally:
            if previous_serial is None:
                del sys.modules["serial"]
            else:
                sys.modules["serial"] = previous_serial

    def test_serial_backend_does_not_reconfigure_timeout_per_letter(self):
        class StableTimeoutSerial(FakeSerialPort):
            instances = []

            def __init__(self, *args, **kwargs):
                super().__init__(b"")
                self.timeout_writes = []
                self.timeout = kwargs["timeout"]
                self.__class__.instances.append(self)

            @property
            def timeout(self):
                return self._timeout

            @timeout.setter
            def timeout(self, value):
                self._timeout = value
                if hasattr(self, "timeout_writes"):
                    self.timeout_writes.append(value)

            def write(self, data):
                self.buffer.extend(b"C")
                return len(data)

            def flush(self):
                return None

            def close(self):
                return None

        previous_serial = sys.modules.get("serial")
        sys.modules["serial"] = types.SimpleNamespace(Serial=StableTimeoutSerial)
        try:
            backend = SerialBackend(SerialConfig("COM7", timeout=0.01))
            try:
                self.assertEqual(backend.encipher_letter("H"), "C")
                self.assertEqual(backend.encipher_letter("I"), "C")
            finally:
                backend.close()
        finally:
            if previous_serial is None:
                del sys.modules["serial"]
            else:
                sys.modules["serial"] = previous_serial

        self.assertEqual(StableTimeoutSerial.instances[0].timeout_writes, [0.01])

    def test_serial_backend_stop_cancels_active_reads(self):
        class CancellableSerial(FakeSerialPort):
            instances = []

            def __init__(self, *args, **kwargs):
                super().__init__(b"")
                self.timeout = kwargs["timeout"]
                self.cancelled = False
                self.__class__.instances.append(self)

            def cancel_read(self):
                self.cancelled = True

            def close(self):
                return None

        previous_serial = sys.modules.get("serial")
        sys.modules["serial"] = types.SimpleNamespace(Serial=CancellableSerial)
        try:
            backend = SerialBackend(SerialConfig("COM7", timeout=0.01))
            try:
                backend.request_stop()
                with self.assertRaises(SerialOperationCancelled):
                    backend.encipher_letter("H")
            finally:
                backend.close()
        finally:
            if previous_serial is None:
                del sys.modules["serial"]
            else:
                sys.modules["serial"] = previous_serial

        self.assertTrue(CancellableSerial.instances[0].cancelled)


class FakeSerialPort:
    def __init__(self, buffer):
        self.buffer = bytearray(buffer)
        self.timeout = 2.0

    @property
    def in_waiting(self):
        return len(self.buffer)

    def read(self, size=1):
        if not self.buffer:
            return b""
        size = min(size, len(self.buffer))
        output = bytes(self.buffer[:size])
        del self.buffer[:size]
        return output


if __name__ == "__main__":
    unittest.main()
