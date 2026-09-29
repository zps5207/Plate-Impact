# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files

# plotly ships its validator schema and the embeddable plotly.js bundle as
# package data (needed at runtime by fig.write_html(include_plotlyjs=True)),
# not just importable modules -- a plain hiddenimports list misses those.
# NOTE: deliberately *not* collect_submodules('plotly') -- that force-imports
# every optional plotly submodule (matplotlib/orca/kaleido image-export
# bridges, etc.) at build time and, in this environment, pulls in both PyQt5
# and PySide6, which PyInstaller refuses to bundle together. embmesh.visualize
# only uses plotly.graph_objects's own HTML export, which PyInstaller's normal
# static import analysis (via the hiddenimport below) already follows fine.
datas = collect_data_files('plotly')
hiddenimports = ['embmesh.visualize', 'plotly.graph_objects',
    # multiprocessing.freeze_support() (see embmesh_entry.py) needs the spawn
    # bootstrap importable inside the frozen exe for ProcessPoolExecutor to work.
    'multiprocessing.popen_spawn_win32',
]

a = Analysis(
    ['embmesh_entry.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Qt bindings and matplotlib are not used by embmesh.visualize (plotly-based)
    # or anything else this exe imports; excluding them keeps the build from
    # pulling in unrelated, conflicting optional dependencies present in this
    # dev environment (see the collect_submodules note above).
    excludes=['PyQt5', 'PySide2', 'PySide6', 'PyQt6', 'matplotlib', 'IPython',
              'plotly.matplotlylib'],
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
    name='embmesh',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
