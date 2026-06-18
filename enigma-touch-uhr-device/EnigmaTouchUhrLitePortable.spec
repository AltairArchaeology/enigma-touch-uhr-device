# -*- mode: python ; coding: utf-8 -*-

from datetime import datetime
from pathlib import Path
import tempfile

from build_support.windows_version_info import write_windows_version_info
from enigma_uhr_touch.version import __version__


built_at = datetime.now().astimezone()
timezone = built_at.strftime('%Z')
build_timestamp = (
    f"{built_at.strftime('%B')} {built_at.day}, {built_at.year} at "
    f"{built_at.strftime('%I:%M %p').lstrip('0')}{f' {timezone}' if timezone else ''}"
)
build_hook = Path(tempfile.gettempdir()) / 'enigma_touch_lite_build_timestamp.py'
build_hook.write_text(
    f"import os\nos.environ['ENIGMA_TOUCH_BUILD_TIMESTAMP'] = {build_timestamp!r}\n",
    encoding='ascii',
)
version_file = write_windows_version_info(
    version=__version__,
    original_filename='Enigma Touch - Uhr Device.exe',
    file_description='Enigma Touch - Uhr Device',
    suffix='lite',
)


a = Analysis(
    ['Enigma_Uhr_UI.pyw'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(build_hook)],
    excludes=['PySide6', 'shiboken6'],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Enigma Touch - Uhr Device',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version=str(version_file),
)
