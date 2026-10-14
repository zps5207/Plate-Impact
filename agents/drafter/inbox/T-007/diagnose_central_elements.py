"""Diagnose ghost elements near the impact point that never reach STATUS=0
while the ball visually passes through them.

Run on ROAR: abaqus python diagnose_central_elements.py flat_t006.odb
"""
from __future__ import print_function
import json
import sys

from odbAccess import openOdb

GHOST_ELSET = "EMBMESH_GHOST_DIAGNOSTICS"
PLATE_INSTANCE = "PLATE-1"
RADIUS = 0.003  # meters, around the impact corner (0, 0, -0.01)


def main(odb_path):
    odb = openOdb(odb_path, readOnly=True)
    instance = odb.rootAssembly.instances[PLATE_INSTANCE]
    ghost_set = odb.rootAssembly.elementSets[GHOST_ELSET]
    ghost_labels = set(e.label for e in ghost_set.elements[0])

    # Find elements near the impact corner (0,0) in X/Y, close to the near
    # (impacted) face in Z, using element-node centroid.
    node_coords = {n.label: n.coordinates for n in instance.nodes}
    near_labels = []
    for e in instance.elements:
        if e.label not in ghost_labels:
            continue
        pts = [node_coords[n] for n in e.connectivity]
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        if (cx * cx + cy * cy) ** 0.5 <= RADIUS:
            near_labels.append(e.label)
    near_labels.sort()

    step = list(odb.steps.values())[0]
    frames = step.frames
    first_frame = frames[0]
    last_frame = frames[-1]

    def status_at(frame):
        field = frame.fieldOutputs["STATUS"].getSubset(region=ghost_set)
        return {v.elementLabel: v.data for v in field.values}

    status_first = status_at(first_frame)
    status_last = status_at(last_frame)

    never_deleted = [lbl for lbl in near_labels
                     if status_last.get(lbl, 1.0) > 0.5]
    deleted = [lbl for lbl in near_labels
               if status_last.get(lbl, 1.0) <= 0.5]

    # PEEQ history (first/last) for the never-deleted central elements, to see
    # whether they ever plasticized at all.
    peeq_report = {}
    for lbl in never_deleted[:20]:
        try:
            peeq_last = last_frame.fieldOutputs["PEEQ"].getSubset(
                region=ghost_set).values
            peeq_val = next((v.data for v in peeq_last
                              if v.elementLabel == lbl), None)
        except Exception as exc:
            peeq_val = "error: {0}".format(exc)
        peeq_report[lbl] = peeq_val

    report = {
        "ghost_elements_near_impact": len(near_labels),
        "near_labels_sample": near_labels[:20],
        "never_deleted_count": len(never_deleted),
        "never_deleted_sample": never_deleted[:40],
        "deleted_count": len(deleted),
        "deleted_sample": deleted[:20],
        "peeq_last_for_never_deleted_sample": peeq_report,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    odb.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: abaqus python diagnose_central_elements.py ODB_PATH")
    main(sys.argv[1])
