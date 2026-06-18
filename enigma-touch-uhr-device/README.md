# Enigma Touch - Uhr Device

Enigma Touch - Uhr Device is a lightweight Windows desktop application for applying historical Enigma Uhr behavior, and an optional ahistoric variable-pair Uhr mode, to the Enigma Touch.

Current stable version: **1.0.0**

The program reads the active machine settings from an Enigma Touch over USB serial and calculates the key inputs needed to make the Enigma Touch lightboard display the final Uhr-adjusted result.

Created by **AltairArchaeology** with development assistance from **OpenAI Codex**.

## Features

- Reads the model, reflector, rotors, rings, rotor position, plugboard, and Reflector D wiring from the Enigma Touch.
- Supports the plugboard-equipped Enigma I, M3, and M4 models.
- Implements the historical 40-position Enigma Uhr Device with exactly ten ordered plugboard pairs.
- Provides an optional ahistoric Uhr Device mode supporting one through thirteen plugboard pairs.
- Updates the Result area while the Enigma Touch processes the message.
- Can stop an active conversion while preserving completed output and the current rotor position.
- Can refresh the rotor position automatically immediately before conversion.
- Supports configurable output grouping and preservation of spaces and punctuation.
- Includes built-in Help, About, License, and mapping displays.
- Uses a conservative default serial rate of 2400 baud for reliable longer messages.

## Installation

1. Open the [latest GitHub release](../../releases/latest).
2. Download `Enigma Touch - Uhr Device.exe`.
3. Connect the Enigma Touch to the computer over USB.
4. Run the downloaded EXE. No installer is required.

The executables are currently unsigned. Windows may display a Microsoft Defender SmartScreen warning the first time they are opened. Confirm that the file came from the official GitHub release before choosing to run it.

## Quick Start

1. Select the Enigma Touch COM port. Use **Refresh** if the port is not listed.
2. Confirm that the baud rate is `2400` and the timeout is `2.0` seconds.
3. Select **Read Enigma Touch Settings**.
4. Choose an **Uhr Device** position from `00` through `39`.
5. Enter plain text or cipher text in **Message**.
6. Select **Convert**.

The converted text appears in **Result** as it is processed. The Result should match the letters displayed on the Enigma Touch lightboard.

**Update Position Before Convert** is enabled by default and reads the current rotor position immediately before conversion.

## Historical Uhr Device

Historical mode is enabled by default and requires exactly ten plugboard pairs. The order and orientation of the pairs are significant because they represent the numbered and colored Uhr cable connections.

Position `00` introduces no additional Uhr scrambling and produces ordinary plugboard behavior. Positions `01` through `39` apply the historical Uhr wiring.

## Ahistoric Uhr Device

Select **Enable Ahistoric Uhr Device** to use between one and thirteen plugboard pairs.

- One through nine pairs use a deterministic contraction of the historical wiring.
- Ten pairs preserve the exact historical Uhr mapping.
- Eleven through thirteen pairs use a deterministic extension of the historical wiring.

This mode is intentionally ahistoric. The same pair order, pair orientation, Uhr position, and program version are required to reproduce its results.

## Output Formatting

**Letters Per Group** defaults to `5`. German Army and Luftwaffe traffic commonly used five-letter groups, while Kriegsmarine traffic often used four-letter groups. Set the value to `0` to disable grouping.

**Keep Spaces and Punctuation** is disabled by default. Enabling it preserves the original formatting and disables output grouping.

## Compatibility

- Windows 10 or Windows 11, 64-bit
- Enigma Touch connected through a USB serial port
- Enigma Touch firmware supporting `?MO`, `?RO`, `?RI`, `?RP`, `?PB`, and `?RD` queries
- Enigma I, M3, or M4 when performing Uhr conversion

The settings reader was developed against Enigma Touch firmware 4.21. Other built-in Enigma Touch models can be read, but Uhr conversion is unavailable when the selected model does not have an active plugboard. Custom model support is not currently enabled.

## Running From Source

Python 3.10 or newer is required.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
py Enigma_Uhr_UI.pyw
```

To launch the Qt interface instead:

```powershell
py Enigma_Uhr_Qt.pyw
```

Run the automated tests with:

```powershell
py -m unittest discover -v
```

Release builds are documented in [BUILD.md](BUILD.md). Hardware and automated validation are summarized in [TESTING.md](TESTING.md).

## License

Enigma Touch - Uhr Device is available under the [MIT License](LICENSE).

Copyright (c) 2026 AltairArchaeology.

## Credits

Designed and developed by **AltairArchaeology** with assistance from **OpenAI Codex**.

## Contact

For bugs, feedback, and comments, please contact the program creator through one of the following methods:

- Email: altairarchaeology@gmail.com
- Discord: Revenant_MZ
- Reddit: u/Mirzayev
- GitHub: [AltairArchaeology](https://github.com/AltairArchaeology)
