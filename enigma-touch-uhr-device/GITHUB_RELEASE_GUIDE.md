# GitHub Publication Guide

## Repository

Recommended repository name: `enigma-touch-uhr-device`

Suggested description:

> Windows companion application that adds historical and variable-pair ahistoric Enigma Uhr behavior to the Enigma Touch.

Suggested topics:

`enigma`, `enigma-machine`, `historical-ciphers`, `uhr`, `windows`, `python`, `pyserial`

Create a public repository without adding a GitHub-generated README, license, or `.gitignore`; those files are already included. Upload the contents of the prepared `enigma-touch-uhr-device` repository folder and commit them to the default branch.

The included GitHub Actions workflow will run the automated tests on Python 3.10 and 3.12 after the source is committed.

## Version 1.0.0 Release

Complete the clean-Windows checks in `RELEASE_CHECKLIST.md` before publishing.

1. Open the repository's Releases page and create a new release.
2. Create the tag `v1.0.0` from the tested release commit.
3. Use `Enigma Touch - Uhr Device 1.0.0` as the release title.
4. Paste the contents of `RELEASE_NOTES.md` into the release description.
5. Upload `Enigma Touch - Uhr Device.exe`, `EnigmaTouchUhrPortable.exe`, and `SHA256SUMS.txt` from the prepared release-assets folder.
6. Publish the release after confirming the filenames and checksums.

The Lite executable is the recommended download. The Qt executable is an alternative build with the same core functionality.
