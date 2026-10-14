"""Find island ghost elements (STATUS=1, surrounded by dead neighbors) and
cross-reference their VU1 host's own SDV49 failure flag, now that it's
requested as field output (T-007 diagnostic patch).

Run on ROAR: abaqus python crosscheck_sdv_islands.py flat_t007.odb
"""
from __future__ import print_function
import json
import sys

from odbAccess import openOdb

GHOST_ELSET = "EMBMESH_GHOST_DIAGNOSTICS"
VUEL_ELSET = "EMBMESH_VUEL_DIAGNOSTICS"
PLATE_INSTANCE = "PLATE-1"
GHOST_HOST_OFFSET = 24000


def main(odb_path):
    odb = openOdb(odb_path, readOnly=True)
    instance = odb.rootAssembly.instances[PLATE_INSTANCE]
    ghost_set = odb.rootAssembly.elementSets[GHOST_ELSET]
    vuel_set = odb.rootAssembly.elementSets[VUEL_ELSET]
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
    status_field = last_frame.fieldOutputs["STATUS"].getSubset(region=ghost_set)
    status_last = {v.elementLabel: v.data for v in status_field.values}

    near_labels = [lbl for lbl, c in centroid.items() if c[3] <= 0.010]
    pitch_estimate = 0.05 / 24.0
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
            islands.append(lbl)

    # SDV49 for each island's VU1 host, at the LAST frame it's requested
    # (1000 intervals, same cadence as ghost diagnostics).
    sdv_field = last_frame.fieldOutputs["SDV49"].getSubset(region=vuel_set)
    sdv49_by_host = {v.elementLabel: v.data for v in sdv_field.values}

    cross = []
    for ghost_lbl in islands:
        host_lbl = ghost_lbl - GHOST_HOST_OFFSET
        cross.append({
            "ghost_label": ghost_lbl,
            "host_label": host_lbl,
            "ghost_status_last": status_last.get(ghost_lbl),
            "vu1_sdv49_last": sdv49_by_host.get(host_lbl),
        })

    vu1_failed_but_ghost_alive = sum(
        1 for c in cross if c["vu1_sdv49_last"] is not None
        and c["vu1_sdv49_last"] > 0.5)
    vu1_not_failed = sum(
        1 for c in cross if c["vu1_sdv49_last"] is not None
        and c["vu1_sdv49_last"] <= 0.5)
    missing = sum(1 for c in cross if c["vu1_sdv49_last"] is None)

    report = {
        "island_count": len(islands),
        "cross_reference": cross,
        "summary": {
            "vu1_failed_but_ghost_still_present": vu1_failed_but_ghost_alive,
            "vu1_never_failed_ghost_also_present": vu1_not_failed,
            "host_sdv49_missing_from_odb": missing,
        },
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    odb.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: abaqus python crosscheck_sdv_islands.py ODB_PATH")
    main(sys.argv[1])
