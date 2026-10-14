"""Wider-radius pass: band STATUS by distance from the impact corner, and
flag any 'island' element (STATUS=1) whose nearest neighbors are mostly
STATUS=0, which is the signature of a visual hole with a surviving plug.
"""
from __future__ import print_function
import json
import sys

from odbAccess import openOdb

GHOST_ELSET = "EMBMESH_GHOST_DIAGNOSTICS"
PLATE_INSTANCE = "PLATE-1"
BANDS = [0.001, 0.002, 0.003, 0.004, 0.005, 0.006, 0.008, 0.010]


def main(odb_path):
    odb = openOdb(odb_path, readOnly=True)
    instance = odb.rootAssembly.instances[PLATE_INSTANCE]
    ghost_set = odb.rootAssembly.elementSets[GHOST_ELSET]
    ghost_labels = set(e.label for e in ghost_set.elements[0])

    node_coords = {n.label: n.coordinates for n in instance.nodes}
    centroid = {}
    for e in instance.elements:
        if e.label not in ghost_labels:
            continue
        pts = [node_coords[n] for n in e.connectivity]
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        cz = sum(p[2] for p in pts) / len(pts)
        centroid[e.label] = (cx, cy, cz, (cx * cx + cy * cy) ** 0.5)

    step = list(odb.steps.values())[0]
    last_frame = step.frames[-1]
    field = last_frame.fieldOutputs["STATUS"].getSubset(region=ghost_set)
    status_last = {v.elementLabel: v.data for v in field.values}

    band_report = []
    prev_r = 0.0
    for r in BANDS:
        in_band = [lbl for lbl, c in centroid.items() if prev_r < c[3] <= r]
        dead = [lbl for lbl in in_band if status_last.get(lbl, 1.0) <= 0.5]
        alive = [lbl for lbl in in_band if status_last.get(lbl, 1.0) > 0.5]
        band_report.append({
            "r_lo": prev_r, "r_hi": r, "count": len(in_band),
            "dead": len(dead), "alive": len(alive),
            "alive_sample": alive[:15],
        })
        prev_r = r

    # Island check: for every alive element within r<=0.01, approximate
    # pitch from host element size and look for any dead neighbor within
    # 1.5x that pitch -- if most neighbors are dead, flag as an island.
    near_labels = [lbl for lbl, c in centroid.items() if c[3] <= 0.010]
    pitch_estimate = 0.05 / 24.0  # rough plate-edge / per-axis element count guess
    islands = []
    for lbl in near_labels:
        if status_last.get(lbl, 1.0) <= 0.5:
            continue
        cx, cy, cz, _ = centroid[lbl]
        neighbor_dead = 0
        neighbor_total = 0
        for other in near_labels:
            if other == lbl:
                continue
            ox, oy, oz, _ = centroid[other]
            d = ((cx - ox) ** 2 + (cy - oy) ** 2 + (cz - oz) ** 2) ** 0.5
            if d <= pitch_estimate * 1.6:
                neighbor_total += 1
                if status_last.get(other, 1.0) <= 0.5:
                    neighbor_dead += 1
        if neighbor_total >= 3 and neighbor_dead / float(neighbor_total) >= 0.6:
            islands.append({"elem": lbl, "neighbor_total": neighbor_total,
                             "neighbor_dead": neighbor_dead,
                             "centroid": [cx, cy, cz]})

    report = {
        "bands": band_report,
        "island_candidates": islands,
        "island_count": len(islands),
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    odb.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: abaqus python diagnose_central_elements2.py ODB_PATH")
    main(sys.argv[1])
