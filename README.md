# embmesh

`embmesh` is a Python 3.11+ parser, host-selection, fiber-layout, volume-accounting, and Abaqus-deck writer for embedded truss/beam fibers. Run `embmesh list model.inp` for a compact deck summary. Abaqus itself is not required for the Python tests; ROAR/SLURM templates contain explicit TODOs where site-specific module or license settings are needed.

## Windows executable

`dist/embmesh.exe` is a standalone Windows x64 build. For example:

```powershell
.\dist\embmesh.exe list .\examples\flat_disc.inp
```

To rebuild it with PyInstaller:

```powershell
python -m pip install pyinstaller
python -m PyInstaller --noconfirm --clean --onefile --name embmesh embmesh_entry.py
```
