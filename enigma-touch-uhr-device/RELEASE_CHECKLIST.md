# Version 1.0.0 Release Checklist

## Completed Locally

- [x] Version is set to 1.0.0 in the application and Windows file metadata.
- [x] Automated tests pass.
- [x] Hardware mapping, round-trip, lightboard, reconnect, and long-message tests pass.
- [x] Lite and Qt source smoke tests pass.
- [x] Packaged Lite and Qt smoke tests pass.
- [x] SHA-256 checksums are generated for final artifacts.
- [x] Changelog, release notes, build instructions, validation summary, and license are present.

## External Release Gates

- [ ] Run `Enigma Touch - Uhr Device.exe` on a clean 64-bit Windows 10 or Windows 11 system.
- [ ] Confirm COM-port discovery, settings read, one conversion, Stop behavior, Help, About, and License.
- [ ] Create the GitHub repository `enigma-touch-uhr-device`.
- [ ] Commit the contents of the prepared repository folder.
- [ ] Tag the release commit as `v1.0.0`.
- [ ] Create the GitHub 1.0.0 release using `RELEASE_NOTES.md`.
- [ ] Upload both executables and `SHA256SUMS.txt` from the prepared release-assets folder.
