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

This writes `output.inp`, `host_fibers.vtk`, `fiber_volume.csv`, and `report.json`. Add `--preview` when running from a Python environment with matplotlib to also write `preview.png`. Symmetry node sets found in the source `*Boundary` definitions are extended with generated fiber nodes on the same plane. `output.inp` embeds the generated fibers as their own `*Part`/`*Instance` inside the source deck's assembly, so it loads in Abaqus as-is.

## Flat vs. curved layup

`--curved` selects the layup family (default `flat`):

- `flat` (plates, boxes, cubes, anything with parallel front/back faces): the through-thickness ("fiber orienting") axis is auto-detected from the host's bounding box, or set explicitly with `--thickness-axis x|y|z|dx,dy,dz`.
- `cylindrical` (a plate curved about a single axis, full cylinder or a partial panel -- both auto-detected from the host mesh): `--curve-axis-point x,y,z --curve-axis-dir dx,dy,dz`.
- `spherical` (a spherically curved plate/panel): `--curve-center x,y,z --curve-pole-axis dx,dy,dz` (the pole axis is whichever direction you judge most representative of the shell, per its own director-field convention).

Both curved modes lay down two alternating fiber families (axial/hoop for cylindrical, meridian/latitude for spherical) and inner/outer radius, thickness, and angular extent are all read from the host mesh itself -- no extra geometry description is needed beyond the axis/center.

Other useful `visualize` options: `--node-offset`/`--element-offset` (default 100000; raise these if the host deck already uses labels that high, or when re-meshing an already-fibered deck), `--fiber-elastic E,nu` and `--fiber-density` (the placeholder fiber material's properties -- `embmesh` always warns that this is a placeholder to edit before running Abaqus), `--precise-volume` (also writes `fiber_volume_precise.csv`, a slower but more accurate per-host fiber volume using true cylinder/hex cross-section intersection instead of the default centerline-length approximation -- see `docs/INTERFACE.md`).
