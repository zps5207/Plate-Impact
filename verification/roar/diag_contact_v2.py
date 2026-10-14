"""flat_v2 full diagnostics 3/3: contact (CPRESS/CSHEARMAG) footprint on the plate, ball penetration
into ALIVE ghost elements, closest approach of the ball surface to every near-axis ghost, ball erosion
and ball velocity.
Run: abaqus python diag_contact_v2.py flat_v2.odb outprefix"""
from __future__ import print_function
import json, sys
import numpy as np
from odbAccess import openOdb

odb = openOdb(sys.argv[1], readOnly=True)
pref = sys.argv[2]
asm = odb.rootAssembly
plate = asm.instances["PLATE-1"]
ball = asm.instances["BALL-1"]
glabels = set(e.label for e in asm.elementSets["EMBMESH_GHOST_DIAGNOSTICS"].elements[0])
pn = list(plate.nodes)
bn = list(ball.nodes)
plab = np.array([n.label for n in pn])
blab = np.array([n.label for n in bn])
PX = np.array([n.coordinates for n in pn], dtype=np.float64)
BX = np.array([n.coordinates for n in bn], dtype=np.float64)
pmap = -np.ones(int(plab.max()) + 1, dtype=np.int64)
pmap[plab] = np.arange(len(plab))
bmap = -np.ones(int(blab.max()) + 1, dtype=np.int64)
bmap[blab] = np.arange(len(blab))
gl, gc = [], []
for e in plate.elements:
    if e.label in glabels:
        gl.append(e.label)
        gc.append([pmap[n] for n in e.connectivity])
gl = np.array(gl)
o = np.argsort(gl)
gl = gl[o]
gc = np.array(gc)[o]
NE = len(gl)
emap = -np.ones(int(gl.max()) + 1, dtype=np.int64)
emap[gl] = np.arange(NE)
gmin, gmax = gl.min(), gl.max()
cen0 = PX[gc].mean(axis=1)
r0 = np.hypot(cen0[:, 0], cen0[:, 1])
near = np.where(r0 <= 0.010)[0]
step = list(odb.steps.values())[0]
nfr = len(step.frames)

cp_max = np.zeros(len(plab))
cp_first = -np.ones(len(plab), dtype=np.int64)
cp_frames = np.zeros(len(plab), dtype=np.int64)
cs_max = np.zeros(len(plab))
b_cp_max = np.zeros(len(blab))
per_frame = []
closest = np.full(NE, 1e9)
closest_t = np.zeros(NE)
pen_summary = []
hit_ever = {}
pen_last = None
STR = 5


def blocks(fo, inst):
    for b in fo.bulkDataBlocks:
        if b.instance is not None and b.instance.name == inst:
            yield b


for fi in range(nfr):
    f = step.frames[fi]
    c_on = 0
    fos = f.fieldOutputs
    if "CPRESS" in fos:
        for b in blocks(fos["CPRESS"], "PLATE-1"):
            ii = pmap[b.nodeLabels]
            v = b.data[:, 0]
            cp_max[ii] = np.maximum(cp_max[ii], v)
            on = v > 0
            first = on & (cp_first[ii] < 0)
            cp_first[ii[first]] = fi
            cp_frames[ii[on]] += 1
            c_on += int(on.sum())
        for b in blocks(fos["CPRESS"], "BALL-1"):
            ii = bmap[b.nodeLabels]
            b_cp_max[ii] = np.maximum(b_cp_max[ii], b.data[:, 0])
    if "CSHEARMAG" in fos:
        for b in blocks(fos["CSHEARMAG"], "PLATE-1"):
            ii = pmap[b.nodeLabels]
            cs_max[ii] = np.maximum(cs_max[ii], b.data[:, 0])
    per_frame.append([fi, float(f.frameValue), c_on])
    if fi % STR and fi != nfr - 1:
        continue
    U = np.zeros((len(plab), 3))
    BU = np.zeros((len(blab), 3))
    BV = np.zeros((len(blab), 3))
    for b in blocks(fos["U"], "PLATE-1"):
        U[pmap[b.nodeLabels]] = b.data
    for b in blocks(fos["U"], "BALL-1"):
        BU[bmap[b.nodeLabels]] = b.data
    for b in blocks(fos["V"], "BALL-1"):
        BV[bmap[b.nodeLabels]] = b.data
    st = np.ones(NE)
    for b in blocks(fos["STATUS"], "PLATE-1"):
        lab = b.elementLabels
        ok = (lab >= gmin) & (lab <= gmax)
        ii = emap[lab[ok]]
        g = ii >= 0
        st[ii[g]] = b.data[ok][g, 0]
    alive = st > 0.5
    bst = None
    for b in blocks(fos["STATUS"], "BALL-1"):
        bst = b.data[:, 0].copy() if bst is None else np.concatenate([bst, b.data[:, 0]])
    xp = PX + U
    xb = BX + BU
    ec = xp[gc]
    lo = ec.min(axis=1)
    hi = ec.max(axis=1)
    sh = 0.1 * (hi - lo)
    lo = lo + sh
    hi = hi - sh
    cand = np.where((xb[:, 2] < 0.0005) & (xb[:, 2] > -0.0105) & (np.hypot(xb[:, 0], xb[:, 1]) < 0.0105))[0]
    ai = np.where(alive)[0]
    inside = 0
    hits = set()
    for s in range(0, len(cand), 1000):
        p = xb[cand[s:s + 1000]]
        m = ((p[:, None, :] >= lo[ai][None]) & (p[:, None, :] <= hi[ai][None])).all(axis=2)
        k = np.where(m.any(axis=1))[0]
        inside += len(k)
        for q in k:
            hits.update(gl[ai[np.where(m[q])[0]]].tolist())
    for h in hits:
        hit_ever[h] = hit_ever.get(h, 0) + 1
    cc = ec.mean(axis=1)[near]
    bsel = xb[(xb[:, 2] < 0.002) & (xb[:, 2] > -0.0105)]
    if len(bsel):
        for s in range(0, len(near), 100):
            d = np.sqrt(((cc[s:s + 100, None, :] - bsel[None]) ** 2).sum(axis=2)).min(axis=1)
            idx = near[s:s + 100]
            upd = d < closest[idx]
            closest[idx[upd]] = d[upd]
            closest_t[idx[upd]] = f.frameValue
    pen_summary.append({"fi": fi, "t": float(f.frameValue), "ball_nodes_inside_alive_ghost": int(inside),
                        "n_cand": int(len(cand)), "ball_zmin": float(xb[:, 2].min()),
                        "ball_mean_vz": float(BV[:, 2].mean()),
                        "ball_elems_alive": (int((bst > 0.5).sum()) if bst is not None else None),
                        "ball_elems_total": (int(len(bst)) if bst is not None else None),
                        "plate_nodes_in_contact": c_on, "n_distinct_hit_elems": len(hits)})
    if fi % 50 == 0:
        sys.stderr.write("frame %d inside %d contact nodes %d\n" % (fi, inside, c_on))
        sys.stderr.flush()
    if fi == nfr - 1:
        pen_last = sorted(hits)

ever = cp_frames > 0
layers = np.round(PX[:, 2] * 1000, 1)
by_z = {}
for zl in sorted(set(layers.tolist()), reverse=True):
    m = layers == zl
    by_z[str(zl)] = {"nodes": int(m.sum()), "ever_in_contact": int((ever & m).sum()),
                     "max_cpress": float(cp_max[m].max())}
out = {"contact_by_depth": by_z, "plate_nodes_ever_contact": int(ever.sum()), "plate_nodes": int(len(plab)),
       "ball_nodes_ever_contact": int((b_cp_max > 0).sum()), "ball_nodes": int(len(blab)),
       "per_frame_contact_nodes": per_frame, "penetration": pen_summary,
       "hit_elems_last_frame": pen_last,
       "hit_ever_counts": dict((str(k), v) for k, v in hit_ever.items())}
json.dump(out, open(pref + "_contact.json", "w"), default=float)
rr = np.hypot(PX[:, 0], PX[:, 1])
np.savetxt(pref + "_plate_nodes_contact.csv",
           np.column_stack([plab, PX[:, 0], PX[:, 1], PX[:, 2], rr, ever.astype(int), cp_max, cp_first, cp_frames, cs_max]),
           delimiter=",", header="label,x,y,z,r,ever_contact,cp_max,cp_first_frame,cp_frames,cshear_max", comments="")
np.savetxt(pref + "_closest_approach.csv",
           np.column_stack([gl[near], cen0[near], r0[near], closest[near], closest_t[near]]),
           delimiter=",", header="label,x,y,z,r,closest_ball_node_dist,t", comments="")
odb.close()
