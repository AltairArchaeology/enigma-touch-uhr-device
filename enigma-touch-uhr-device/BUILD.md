# Building Enigma Touch - Uhr Device

The official 1.0.0 executables were built on 64-bit Windows with Python 3.12.13 and PyInstaller 6.21.0.

## Environment

```powershell
py -3.12 -m venv .build-venv
.\.build-venv\Scripts\python.exe -m pip install --upgrade pip
.\.build-venv\Scripts\python.exe -m pip install -r requirements-build.txt
```

`requirements.txt` pins runtime dependencies. `requirements-build.txt` adds the exact PyInstaller toolchain used for the release.

## Release Build

```powershell
powershell -ExecutionPolicy Bypass -File .\build_release.ps1
```

The script runs automated tests and source smoke tests, builds both portable applications, smoke-tests the packaged executables, and writes SHA-256 checksums. Output is placed in `release\v1.0.0`.

The primary release candidate is `Enigma Touch - Uhr Device.exe`. `EnigmaTouchUhrPortable.exe` is the larger alternative Qt build.
