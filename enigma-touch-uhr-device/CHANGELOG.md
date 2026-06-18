# Changelog

All notable changes to Enigma Touch - Uhr Device are documented here.

## 1.0.0 - 2026-06-18

### Added

- Historical 40-position Enigma Uhr Device behavior for ten ordered plugboard pairs.
- Optional ahistoric Uhr mode supporting one through thirteen ordered pairs.
- Enigma I, M3, and M4 conversion using settings read from the Enigma Touch.
- Lite Tk and alternative Qt portable Windows applications.
- Live conversion progress, cooperative Stop control, output grouping, and formatting preservation.
- Built-in Help, About, License, mapping display, and build information.

### Reliability

- Conservative 2400 baud default for long messages.
- Stable serial timeout configuration during conversions.
- Rotor-position refresh before conversion and partial-position preservation after Stop.
- Automated coverage for Uhr mappings, Touch settings, serial handling, and conversion cancellation.

### Known Limitations

- The Custom Enigma model is not implemented.
- Uhr conversion requires an Enigma Touch model with an active plugboard.
- Windows executables are unsigned.
