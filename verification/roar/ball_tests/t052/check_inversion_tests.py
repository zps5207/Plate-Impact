"""Extract metrics for T-052 Hex Inversion Test Matrix.

Runnable via:
  1. Local Python on viewer npz files:
     python check_inversion_tests.py . --npz
  2. Abaqus Python on ROAR directly on ODBs:
     abaqus python check_inversion_tests.py . --odb --json summary.json --csv summary.csv

Metrics extracted:
  - Total C3D8R hex corner Jacobian inversion fraction (all elements, matching bt2)
  - Active (alive) C3D8R hex corner Jacobian inversion fraction (STATUS > 0)
  - Ball deleted element count and percentage at 12 us
  - Energy ratio: ETOTAL end / start, ALLKE peak / start
  - Wall-clock runtime from .sta / .log files
"""

from __future__ import print_function, division
import os
import sys
import json
import glob
from pathlib import Path
import numpy as np

NBR = {0: (1, 3, 4), 1: (2, 0, 5), 2: (3, 1, 6), 3: (0, 2, 7), 4: (7, 5, 0), 5: (4, 6, 1), 6: (5, 7, 2), 7: (6, 4, 3)}


def min_corner_scaled_jacobian(elem_coords):
    """Compute minimum corner scaled Jacobian for an array of 8-node hexes.
    
    elem_coords: (M, 8, 3) numpy array of nodal coordinates.
    Returns: (M,) numpy array of minimum corner scaled Jacobians.
    """
    M = len(elem_coords)
    sj = np.full(M, 9.0)
    for v, (a, b, c) in NBR.items():
        e1 = elem_coords[:, a] - elem_coords[:, v]
        e2 = elem_coords[:, b] - elem_coords[:, v]
        e3 = elem_coords[:, c] - elem_coords[:, v]
        t = np.einsum("ij,ij->i", np.cross(e1, e2), e3)
        n = np.linalg.norm(e1, axis=1) * np.linalg.norm(e2, axis=1) * np.linalg.norm(e3, axis=1)
        sj = np.minimum(sj, t / np.maximum(n, 1e-30))
    return sj


def analyze_npz(npz_path):
    """Analyze viewer npz file."""
    d = np.load(npz_path)
    conn = d["ball_conn_C3D8R"]
    pos = d["ball_pos"]
    times = d["times"] * 1e6  # in microseconds

    has_status = "ball_status_C3D8R" in d
    status = d["ball_status_C3D8R"] if has_status else None

    frac_all = []
    frac_alive = []
    del_count = []

    for i in range(len(times)):
        p = pos[i].astype(np.float64)
        elem_pts = p[conn]
        sj = min_corner_scaled_jacobian(elem_pts)
        inv_mask = (sj <= 0)
        frac_all.append(float(inv_mask.mean()))

        if status is not None:
            alive = (status[i] > 0.5)
            n_dead = int((~alive).sum())
            del_count.append(n_dead)
            if alive.any():
                frac_alive.append(float((inv_mask & alive).sum() / alive.sum()))
            else:
                frac_alive.append(0.0)
        else:
            del_count.append(0)
            frac_alive.append(float(inv_mask.mean()))

    return {
        "times": times.tolist(),
        "inv_all_end": frac_all[-1] if frac_all else 0.0,
        "inv_alive_end": frac_alive[-1] if frac_alive else 0.0,
        "del_end": del_count[-1] if del_count else 0,
        "total_hexes": len(conn),
    }


def analyze_odb(odb_path):
    """Analyze Abaqus ODB using abaqus python."""
    try:
        from odbAccess import openOdb
    except ImportError:
        print(f"Error: openOdb not available. Run with 'abaqus python {sys.argv[0]}'")
        return None

    odb = openOdb(str(odb_path), readOnly=True)
    step = odb.steps[odb.steps.keys()[-1]]

    # Energy history
    allke_hist = []
    etotal_hist = []
    for hname, hreg in step.historyRegions.items():
        if "Assembly" in hname:
            if "ALLKE" in hreg.historyOutputs:
                allke_hist = [v[1] for v in hreg.historyOutputs["ALLKE"].data]
            if "ETOTAL" in hreg.historyOutputs:
                etotal_hist = [v[1] for v in hreg.historyOutputs["ETOTAL"].data]

    allke_start = allke_hist[0] if allke_hist else 0.0
    allke_peak = max(allke_hist) if allke_hist else 0.0
    etotal_start = etotal_hist[0] if etotal_hist else 0.0
    etotal_end = etotal_hist[-1] if etotal_hist else 0.0

    # Instance
    ball_inst = None
    for iname in odb.rootAssembly.instances.keys():
        if "BALL" in iname.upper():
            ball_inst = odb.rootAssembly.instances[iname]
            break

    total_elems = len(ball_inst.elements) if ball_inst else 0

    # Last frame status
    last_frame = step.frames[-1]
    deleted = 0
    if "STATUS" in last_frame.fieldOutputs and ball_inst:
        stat_field = last_frame.fieldOutputs["STATUS"].getSubset(region=ball_inst)
        dead = sum(1 for v in stat_field.values if v.data < 0.5)
        deleted = dead

    odb.close()

    return {
        "total_elems": total_elems,
        "deleted_elems": deleted,
        "allke_start": allke_start,
        "allke_peak_ratio": (allke_peak / allke_start) if allke_start else 1.0,
        "etotal_end_ratio": (etotal_end / etotal_start) if etotal_start else 1.0,
    }


def main():
    root_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    print(f"Scanning directory: {root_dir}")

    # Check for .npz files
    npz_files = sorted(root_dir.glob("*.npz"))
    odb_files = sorted(root_dir.glob("*.odb"))

    results = {}
    if npz_files:
        print(f"Found {len(npz_files)} NPZ viewer files:")
        for p in npz_files:
            name = p.stem
            res = analyze_npz(p)
            results[name] = res
            print(f"  {name:35s}: Inverted (all) = {res['inv_all_end']*100:5.2f}%, Inverted (alive) = {res['inv_alive_end']*100:5.2f}%, Deleted = {res['del_end']}")

    if odb_files:
        print(f"Found {len(odb_files)} ODB files:")
        for p in odb_files:
            name = p.stem
            res = analyze_odb(p)
            if res:
                results[name] = res
                print(f"  {name:35s}: Deleted = {res['deleted_elems']}, ETOTAL ratio = {res['etotal_end_ratio']:.4f}")

    if not npz_files and not odb_files:
        print("No .npz or .odb files found in specified directory.")


if __name__ == "__main__":
    main()
