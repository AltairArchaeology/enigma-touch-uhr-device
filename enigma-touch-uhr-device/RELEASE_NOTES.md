# Enigma Touch - Uhr Device 1.0.0

The first stable release provides historical Enigma Uhr Device behavior for ten plugboard pairs and an optional ahistoric mode supporting one through thirteen pairs. It reads the active Enigma Touch settings over USB serial and drives the Touch so its lightboard displays the final Uhr-adjusted result.

## Highlights

- Historical Uhr positions 00 through 39.
- Ahistoric one- through thirteen-pair mode.
- Enigma I, M3, and M4 support.
- Long-message progress and Stop control.
- Lite portable Windows executable with no installer required.
- Alternative Qt portable build.

## Download

`Enigma Touch - Uhr Device.exe` is the recommended build. `EnigmaTouchUhrPortable.exe` provides the same core behavior using the Qt interface.

## Compatibility

- 64-bit Windows 10 or Windows 11.
- Enigma Touch firmware supporting the documented serial setting queries.
- USB serial connection at 2400 baud recommended.

## Known Limitations

- The Custom Enigma model is not implemented.
- Uhr conversion is limited to models with an active plugboard.
- The executables are unsigned and may display a Microsoft Defender SmartScreen warning.
