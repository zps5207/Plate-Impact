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

For a patched deck plus a host/fiber visualization, use:

```powershell
.\dist\embmesh.exe visualize .\examples\flat_disc.inp --instance DISC-1 --diameter 0.25 --output .\outputs\flat-view
```

This writes `output.inp`, `host_fibers.vtk`, `fiber_volume.csv`, and `report.json`. Add `--preview` when running from a Python environment with matplotlib to also write `preview.png`. Symmetry node sets found in the source `*Boundary` definitions are extended with generated fiber nodes on the same plane.
