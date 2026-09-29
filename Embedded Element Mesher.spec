# -*- mode: python ; coding: utf-8 -*-

import glob
import os
import sys

# On a conda/Anaconda Python, tkinter's compiled _tkinter.pyd depends on
# tcl86t.dll/tk86t.dll (and, transitively, a handful of other conda-packaged
# DLLs -- libmpdec, libcrypto, liblzma, libbz2) that live under
# <conda prefix>\Library\bin, not next to python.exe or in DLLs\ where
# PyInstaller's dependency walker looks by default. Without these, the build
# completes with "Library not found" warnings and the frozen exe fails at
# startup with "ImportError: DLL load failed while importing _tkinter"
# (confirmed on this build; see docs/BUGS.md). Locating them explicitly here
# means a rebuild doesn't depend on the invoking shell happening to have
# Library\bin on PATH.
_conda_lib_bin = os.path.join(sys.base_prefix, 'Library', 'bin')
_extra_binaries = []
if os.path.isdir(_conda_lib_bin):
    for _dll in ('tcl86t.dll', 'tk86t.dll', 'libmpdec-4.dll', 'liblzma.dll', 'LIBBZ2.dll'):
        _hits = glob.glob(os.path.join(_conda_lib_bin, _dll))
        _extra_binaries += [(h, '.') for h in _hits]
    # libcrypto's version-numbered filename varies by OpenSSL build (e.g.
    # libcrypto-3-x64.dll); pick it up by pattern instead of a fixed name.
    _extra_binaries += [(h, '.') for h in glob.glob(os.path.join(_conda_lib_bin, 'libcrypto-*.dll'))]

a = Analysis(
    ['embmesh_desktop.py'],
    pathex=[],
    binaries=[('dist/embmesh.exe', '.')] + _extra_binaries,
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Embedded Element Mesher',
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
)
