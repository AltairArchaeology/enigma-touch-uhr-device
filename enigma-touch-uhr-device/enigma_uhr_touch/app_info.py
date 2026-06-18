from __future__ import annotations

import sys
import os
from datetime import datetime
from pathlib import Path

from .version import __version__


HELP_TEXT = """PURPOSE

This project provides a lightweight software solution for simulating an Enigma Uhr Device with the Enigma Touch. It reads the active machine settings from the Enigma Touch and applies the historical Uhr Device scrambling to ten plugboard pairs according to the selected Uhr Device position.

Position 00 introduces no additional Uhr scrambling and produces ordinary plugboard behavior. The program also provides an ahistoric implementation of the Uhr Device that supports between one and thirteen plugboard pairs.

CONNECTION

Port
Selects the COM port connected to the Enigma Touch.

Refresh
Refreshes the list of available serial ports.

Baud
Sets the serial communication speed. The default is 2400. Higher rates may increase serial overflow errors during longer messages, particularly messages exceeding approximately 200 characters.

Timeout
Sets how many seconds the program waits for a serial response. The default is 2.0 seconds.

Read Enigma Touch Settings
Reads the model, reflector, rotors, rings, rotor position, plugboard, and Reflector D wiring from the Enigma Touch.

ENIGMA TOUCH SETTINGS

?MO reads the Enigma model.
?RO reads both the reflector and rotor selection.
?RI reads the ring settings.
?RP reads the current rotor position.
?PB reads the plugboard pairs.
?RD reads the Reflector D wiring.

The displayed settings can be edited manually, but reading them directly from the Enigma Touch is recommended.

UHR DEVICE

Position
Selects an Uhr Device position from 00 through 39. Position 00 produces ordinary plugboard behavior. With matching plugboard settings, this allows compatibility with an Enigma that is not using an Uhr Device.

Enable Ahistoric Uhr Device
This option is unchecked by default. Historical mode requires exactly ten plugboard pairs. Ahistoric mode permits between one and thirteen pairs. Pair order and orientation affect the resulting mapping.

Uhr conversion is available only for Enigma Touch models with an active plugboard: Enigma I, M3, and M4.

Custom Enigma Model
The Custom Enigma model is not yet implemented in this application.

OUTPUT

Letters Per Group
Sets how many letters appear in each output group. The default is 5. German Army and Luftwaffe traffic commonly used five-letter groups, while Kriegsmarine traffic often used four-letter groups. Enter 0 to disable grouping.

Keep Spaces and Punctuation
Preserves the original spaces and punctuation. When selected, output grouping is disabled so the original formatting can be retained.

MESSAGE AND RESULT

Message
Contains the plain text or cipher text to convert. Enigma conversion is reciprocal, so the same process is used for encryption and decryption.

Convert
Converts the message using the displayed Enigma Touch and Uhr Device settings. The Result area updates as letters return from the Enigma Touch.

Stop
Stops an active conversion. The Result area keeps the letters already completed, and the displayed rotor position is updated to match the stopped conversion.

Clear
Clears the Message and Result areas without changing the machine settings.

Update Position Before Convert
Reads the current rotor position immediately before conversion. This keeps the software synchronized with the Enigma Touch and is enabled by default.

Result
Displays the final converted text. It will match the output shown on the Enigma Touch lightboard.

MAP AND STATUS

The Map area shows the Uhr Device mode, position, plugboard pairs, and calculated letter transformations.

The status bar reports settings queries, conversion progress, completion, and errors.

If an output mismatch occurs, read the Enigma Touch settings again and confirm that its rotor position has not changed.
"""


MIT_LICENSE_TEXT = """MIT License

Copyright (c) 2026 AltairArchaeology

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""


def build_timestamp() -> str:
    embedded_timestamp = os.environ.get("ENIGMA_TOUCH_BUILD_TIMESTAMP")
    if embedded_timestamp:
        return embedded_timestamp
    source = Path(sys.executable) if getattr(sys, "frozen", False) else Path(__file__)
    built_at = datetime.fromtimestamp(source.stat().st_mtime).astimezone()
    timezone = built_at.strftime("%Z")
    suffix = f" {timezone}" if timezone else ""
    return f"{built_at.strftime('%B')} {built_at.day}, {built_at.year} at {built_at.strftime('%I:%M %p').lstrip('0')}{suffix}"


def about_text() -> str:
    return f"""Enigma Touch - Uhr Device

This program is a lightweight desktop application for applying historical Enigma Uhr behavior, and an optional ahistoric variable-pair Uhr mode, to the Enigma Touch.

Version: {__version__}
Build: {build_timestamp()}

Created by AltairArchaeology

Licensed under the MIT License.

For bugs, feedback, and comments, please contact the program creator via one of the methods below:

Email: altairarchaeology@gmail.com
Discord: Revenant_MZ
Reddit: u/Mirzayev
GitHub: https://github.com/AltairArchaeology
"""
