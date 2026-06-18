from __future__ import annotations

import tempfile
from pathlib import Path


def write_windows_version_info(
    *,
    version: str,
    original_filename: str,
    file_description: str,
    suffix: str,
) -> Path:
    version_numbers = tuple(int(part) for part in version.split("."))
    if len(version_numbers) != 3:
        raise ValueError("Release versions must contain three numeric components.")
    file_version = (*version_numbers, 0)
    path = Path(tempfile.gettempdir()) / f"enigma_touch_{suffix}_version_info.txt"
    path.write_text(
        f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={file_version!r},
    prodvers={file_version!r},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [
          StringStruct('CompanyName', 'AltairArchaeology'),
          StringStruct('FileDescription', {file_description!r}),
          StringStruct('FileVersion', {version!r}),
          StringStruct('InternalName', 'EnigmaTouchUhrDevice'),
          StringStruct('LegalCopyright', 'Copyright (c) 2026 AltairArchaeology'),
          StringStruct('OriginalFilename', {original_filename!r}),
          StringStruct('ProductName', 'Enigma Touch - Uhr Device'),
          StringStruct('ProductVersion', {version!r})
        ]
      )
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
""",
        encoding="ascii",
    )
    return path
