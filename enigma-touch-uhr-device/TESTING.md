# Testing and Validation

## Automated Tests

The 1.0.0 release passes 46 automated tests covering:

- Historical and ahistoric Uhr permutations and inverse mappings.
- All Uhr positions and ahistoric pair counts from one through thirteen.
- Enigma Touch setting parsing for alphabetic and numeric machine formats.
- Direct conversion, progress reporting, grouping, and formatting behavior.
- Serial response handling, stable timeout configuration, and cooperative cancellation.

Run the suite with:

```powershell
py -m unittest discover -s tests -v
```

## Hardware Validation

Hardware validation used an Enigma Touch over USB serial at 2400 baud.

- Pair counts 1 through 13 were checked at Uhr positions 00, 01, 17, and 39 using M4 settings.
- Ten-pair ahistoric results were confirmed equivalent to historical Uhr results.
- An Enigma I numeric-setting sanity check was completed.
- Ahistoric 1-, 10-, and 13-pair stress tests each encrypted and decrypted 475 letters at Uhr position 39.
- Every 475-letter decryption exactly matched the normalized source text.
- The Enigma Touch lightboard output matched the application Result.
- Results remained repeatable after disconnecting and reconnecting the Enigma Touch.

## Packaged Application Checks

Both portable executables pass their `--smoke-test` startup checks. A final release-candidate run on a separate clean Windows 10 or Windows 11 system remains the last external release gate.
