"""flat_v2: core-region ghost STATUS by depth, island count, ball tip depth.
Run: abaqus python diagnose_v2.py flat_v2.odb
"""
from __future__ import print_function
import json
import sys
from collections import defaultdict
from odbAccess import openOdb

GHOST_ELSET = "EMBMESH_GHOST_DIAGNOSTICS"


def main(path):
    odb = openOdb(path, readOnly=True)
    asm = odb.rootAssembly
    plate = asm.instances["PLATE-1"]
    ball = asm.instances["BALL-1"]
    ghost_set = asm.elementSets[GHOST_ELSET]
    ghost_labels = set(e.label for e in ghost_set.elements[0])
    coords = dict((n.label, n.coordinates) for n in plate.nodes)
    cen = {}
    for e in plate.elements:
        if e.label in ghost_labels:
            p = [coords[n] for n in e.connectivity]
            cx = sum(q[0] for q in p) / 8.0
            cy = sum(q[1] for q in p) / 8.0
            cz = sum(q[2] for q in p) / 8.0
            cen[e.label] = (cx, cy, cz, (cx * cx + cy * cy) ** 0.5)
    zs = sorted(set(round(c[2], 6) for c in cen.values()))
    step = list(asm.instances.keys()) and list(odb.steps.values())[0]
    out = {"z_layers": zs}
    times = [0, len(step.frames) // 2, len(step.frames) - 1]
    status_by_frame = {}
    for fi in times:
        f = step.frames[fi]
        st = f.fieldOutputs["STATUS"].getSubset(region=ghost_set)
        status_by_frame[fi] = (f.frameValue, dict((v.elementLabel, v.data) for v in st.values))
    last_t, last = status_by_frame[times[-1]]
    layers = defaultdict(lambda: [0, 0])
    for lbl, c in cen.items():
        if c[3] <= 0.004:
            k = round(c[2], 6)
            layers[k][0 if last.get(lbl, 1.0) > 0.5 else 1] += 1
    out["core_r<=0.004_by_z (alive, dead)"] = [[k, layers[k][0], layers[k][1]] for k in sorted(layers)]
    out["alive_total_by_frame"] = [[status_by_frame[fi][0], sum(1 for v in status_by_frame[fi][1].values() if v > 0.5)] for fi in times]
    # islands
    near = [l for l, c in cen.items() if c[3] <= 0.010]
    pitch = 0.05 / 24.0
    isl = 0
    for l in near:
        if last.get(l, 1.0) <= 0.5:
            continue
        cx, cy, cz, _ = cen[l]
        tot = dead = 0
        for o in near:
            if o == l:
                continue
            d = ((cx - cen[o][0]) ** 2 + (cy - cen[o][1]) ** 2 + (cz - cen[o][2]) ** 2) ** 0.5
            if d <= pitch * 1.6:
                tot += 1
                dead += last.get(o, 1.0) <= 0.5
        if tot >= 3 and dead >= 0.6 * tot:
            isl += 1
    out["island_count"] = isl
    # ball tip depth through time
    bc = dict((n.label, n.coordinates) for n in ball.nodes)
    tip = []
    for fi in sorted(set(list(range(0, len(step.frames), max(1, len(step.frames) // 10))) + [len(step.frames) - 1])):
        f = step.frames[fi]
        U = f.fieldOutputs["U"].getSubset(region=ball)
        zmin = min(bc[v.nodeLabel][2] + v.data[2] for v in U.values)
        tip.append([f.frameValue, zmin])
    out["ball_tip_z_vs_time"] = tip
    out["plate_z_range_initial"] = [min(zs), max(zs)]
    # contact pressure: max CPRESS at last frame
    try:
        cp = step.frames[-1].fieldOutputs["CPRESS"]
        out["cpress_max_last"] = max(v.data for v in cp.values)
    except Exception as ex:
        out["cpress_err"] = str(ex)
    print(json.dumps(out, indent=1, default=float))
    odb.close()


main(sys.argv[1])
