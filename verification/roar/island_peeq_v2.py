"""flat_v2: for ghosts within r<=0.010, record deletion time and peak PEEQ
(sampled frames); flag islands (alive at end, >=60% of neighbours dead).
Run: abaqus python island_peeq_v2.py flat_v2.odb > island_peeq_v2.json
"""
from __future__ import print_function
import json
import sys
from odbAccess import openOdb

GHOST_ELSET = "EMBMESH_GHOST_DIAGNOSTICS"
RMAX = 0.010
STRIDE = 10


def main(path):
    odb = openOdb(path, readOnly=True)
    asm = odb.rootAssembly
    plate = asm.instances["PLATE-1"]
    gset = asm.elementSets[GHOST_ELSET]
    glabels = set(e.label for e in gset.elements[0])
    coords = dict((n.label, n.coordinates) for n in plate.nodes)
    cen = {}
    for e in plate.elements:
        if e.label in glabels:
            p = [coords[n] for n in e.connectivity]
            cx = sum(q[0] for q in p) / 8.0
            cy = sum(q[1] for q in p) / 8.0
            cz = sum(q[2] for q in p) / 8.0
            r = (cx * cx + cy * cy) ** 0.5
            if r <= RMAX:
                cen[e.label] = (cx, cy, cz, r)
    near = set(cen)
    step = list(odb.steps.values())[0]
    nfr = len(step.frames)
    peeq_max = dict((l, 0.0) for l in near)
    peeq_final_alive = {}
    death_t = {}
    last_status = {}
    for fi in sorted(set(list(range(0, nfr, STRIDE)) + [nfr - 1])):
        f = step.frames[fi]
        st = f.fieldOutputs["STATUS"].getSubset(region=gset)
        for v in st.values:
            l = v.elementLabel
            if l in near:
                last_status[l] = v.data
                if v.data <= 0.5 and l not in death_t:
                    death_t[l] = f.frameValue
        pq = f.fieldOutputs["PEEQ"].getSubset(region=gset)
        for v in pq.values:
            l = v.elementLabel
            if l in near and v.data > peeq_max[l]:
                peeq_max[l] = float(v.data)
    pitch = 0.05 / 24.0
    rows = []
    for l in sorted(near):
        alive = last_status.get(l, 1.0) > 0.5
        cx, cy, cz, r = cen[l]
        tot = dead = 0
        for o in near:
            if o == l:
                continue
            d = ((cx - cen[o][0]) ** 2 + (cy - cen[o][1]) ** 2 + (cz - cen[o][2]) ** 2) ** 0.5
            if d <= pitch * 1.6:
                tot += 1
                dead += last_status.get(o, 1.0) <= 0.5
        island = alive and tot >= 3 and dead >= 0.6 * tot
        rows.append({"e": l, "r": r, "z": cz, "alive": alive, "island": island,
                     "t_death": death_t.get(l), "peeq_max": peeq_max[l],
                     "nb": tot, "nb_dead": dead})
    print(json.dumps({"stride": STRIDE, "frames": nfr, "rows": rows}, default=float))
    odb.close()


main(sys.argv[1])
