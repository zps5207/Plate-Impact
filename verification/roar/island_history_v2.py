"""flat_v2: per-frame histories for island ghosts (alive at end, >=60% of
neighbours dead, r<=0.010) and for the deleted ghosts adjacent to them.
Per sampled frame: STATUS, PEEQ (max over IPs), pressure and Mises from the
IP-averaged stress, IP-averaged log-strain trace, and centroid displacement
and velocity (mean over the 8 nodes). Hub-run on ROAR.
Run: abaqus python island_history_v2.py flat_v2.odb > island_history_v2.json
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
    conn, cen = {}, {}
    for e in plate.elements:
        if e.label in glabels:
            p = [coords[n] for n in e.connectivity]
            c = tuple(sum(q[i] for q in p) / 8.0 for i in range(3))
            r = (c[0] ** 2 + c[1] ** 2) ** 0.5
            if r <= RMAX:
                cen[e.label] = c + (r,)
                conn[e.label] = e.connectivity
    near = set(cen)
    step = list(odb.steps.values())[0]
    nfr = len(step.frames)
    last = step.frames[-1]
    st_last = dict((v.elementLabel, v.data) for v in last.fieldOutputs["STATUS"].getSubset(region=gset).values if v.elementLabel in near)
    pitch = 0.05 / 24.0
    nbrs = dict((l, []) for l in near)
    for l in near:
        for o in near:
            if o != l:
                d = sum((cen[l][i] - cen[o][i]) ** 2 for i in range(3)) ** 0.5
                if d <= pitch * 1.6:
                    nbrs[l].append(o)
    islands = [l for l in near if st_last.get(l, 1.0) > 0.5 and len(nbrs[l]) >= 3
               and sum(st_last.get(o, 1.0) <= 0.5 for o in nbrs[l]) >= 0.6 * len(nbrs[l])]
    dead_adj = sorted(set(o for l in islands for o in nbrs[l] if st_last.get(o, 1.0) <= 0.5))
    track = set(islands) | set(dead_adj)
    node_need = set(n for l in track for n in conn[l])
    hist = dict((l, {"t": [], "status": [], "peeq": [], "p": [], "mises": [], "le_vol": [],
                     "uz": [], "u_r": [], "vz": []}) for l in track)
    for fi in sorted(set(list(range(0, nfr, STRIDE)) + [nfr - 1])):
        f = step.frames[fi]
        stv = dict((v.elementLabel, v.data) for v in f.fieldOutputs["STATUS"].getSubset(region=gset).values if v.elementLabel in track)
        pq, S, LE = {}, {}, {}
        for v in f.fieldOutputs["PEEQ"].getSubset(region=gset).values:
            if v.elementLabel in track:
                pq[v.elementLabel] = max(pq.get(v.elementLabel, 0.0), float(v.data))
        for v in f.fieldOutputs["S"].getSubset(region=gset).values:
            if v.elementLabel in track:
                a = S.setdefault(v.elementLabel, [0.0] * 6 + [0])
                for i in range(6):
                    a[i] += float(v.data[i])
                a[6] += 1
        for v in f.fieldOutputs["LE"].getSubset(region=gset).values:
            if v.elementLabel in track:
                a = LE.setdefault(v.elementLabel, [0.0, 0])
                a[0] += float(v.data[0] + v.data[1] + v.data[2])
                a[1] += 1
        U = dict((v.nodeLabel, v.data) for v in f.fieldOutputs["U"].getSubset(region=plate).values if v.nodeLabel in node_need)
        V = dict((v.nodeLabel, v.data) for v in f.fieldOutputs["V"].getSubset(region=plate).values if v.nodeLabel in node_need)
        for l in track:
            h = hist[l]
            h["t"].append(float(f.frameValue))
            h["status"].append(float(stv.get(l, 0.0)))
            h["peeq"].append(pq.get(l, 0.0))
            if l in S:
                s = [x / S[l][6] for x in S[l][:6]]
                p = -(s[0] + s[1] + s[2]) / 3.0
                m = (0.5 * ((s[0] - s[1]) ** 2 + (s[1] - s[2]) ** 2 + (s[2] - s[0]) ** 2) + 3 * (s[3] ** 2 + s[4] ** 2 + s[5] ** 2)) ** 0.5
                h["p"].append(p); h["mises"].append(m)
            else:
                h["p"].append(None); h["mises"].append(None)
            h["le_vol"].append(LE[l][0] / LE[l][1] if l in LE else None)
            ns = conn[l]
            uz = sum(U[n][2] for n in ns if n in U) / 8.0
            ur = sum((U[n][0] ** 2 + U[n][1] ** 2) ** 0.5 for n in ns if n in U) / 8.0
            vz = sum(V[n][2] for n in ns if n in V) / 8.0
            h["uz"].append(uz); h["u_r"].append(ur); h["vz"].append(vz)
    out = {"stride": STRIDE, "islands": islands, "dead_adjacent": dead_adj,
           "centroid": dict((str(l), cen[l]) for l in track), "hist": dict((str(l), hist[l]) for l in track)}
    print(json.dumps(out, default=float))
    odb.close()


main(sys.argv[1])
