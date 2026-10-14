"""flat_v2 full diagnostics 2/3: reconstruct the VU1 failure measure for EVERY host element from
nodal displacements (same 8-Gauss-point Green-Lagrange normal-strain + detF measure as
uel/VUEL_failure.for, props EPS_FAIL=0.1138003, JAC_FAIL=0.05) and compare with the ghost's
STATUS / PEEQ / Mises over ALL frames.
Run: abaqus python diag_elements_v2.py flat_v2.odb outprefix"""
from __future__ import print_function
import json, sys
import numpy as np
from odbAccess import openOdb

EPS_FAIL = 0.113800332690901
JAC_FAIL = 0.05
odb = openOdb(sys.argv[1], readOnly=True)
pref = sys.argv[2]
asm = odb.rootAssembly
plate = asm.instances["PLATE-1"]
glabels = set(e.label for e in asm.elementSets["EMBMESH_GHOST_DIAGNOSTICS"].elements[0])
nodes = list(plate.nodes)
nlab = np.array([n.label for n in nodes])
X = np.array([n.coordinates for n in nodes], dtype=np.float64)
nmap = -np.ones(int(nlab.max()) + 1, dtype=np.int64)
nmap[nlab] = np.arange(len(nlab))
gl, gc = [], []
for e in plate.elements:
    if e.label in glabels:
        gl.append(e.label)
        gc.append([nmap[n] for n in e.connectivity])
gl = np.array(gl)
gc = np.array(gc)
order = np.argsort(gl)
gl = gl[order]
gc = gc[order]
NE = len(gl)
emap = -np.ones(int(gl.max()) + 1, dtype=np.int64)
emap[gl] = np.arange(NE)
gmin, gmax = gl.min(), gl.max()
X0 = X[gc]
cen0 = X0.mean(axis=1)
r0 = np.hypot(cen0[:, 0], cen0[:, 1])
sg = np.array([[-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1],
               [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1]], dtype=np.float64)
gp = sg / np.sqrt(3.0)
dN = np.zeros((8, 8, 3))
for g in range(8):
    for i in range(8):
        for d in range(3):
            oth = [x for x in range(3) if x != d]
            dN[g, i, d] = 0.125 * sg[i, d] * np.prod([1 + sg[i, k] * gp[g, k] for k in oth])
J = np.einsum("eia,gib->egab", X0, dN)          # dx/dxi at each GP
Jinv = np.linalg.inv(J)
dNdX = np.einsum("gik,egkb->egib", dN, Jinv)    # (NE,8gp,8node,3)

step = list(odb.steps.values())[0]
nfr = len(step.frames)
times = np.zeros(nfr)
meas_max = np.zeros(NE)
t_meas_max = np.zeros(NE)
detmin = np.full(NE, 1e30)
first_eng = -np.ones(NE, dtype=np.int64)
first_jac = -np.ones(NE, dtype=np.int64)
death = -np.ones(NE, dtype=np.int64)
peeq_max = np.zeros(NE)
mises_max = np.zeros(NE)
t_mises_max = np.zeros(NE)
meas_at_death = np.full(NE, np.nan)
curves = []
prev_alive = np.ones(NE, dtype=bool)


def blocks(fo, inst_name):
    for b in fo.bulkDataBlocks:
        if b.instance is not None and b.instance.name == inst_name:
            yield b


for fi in range(nfr):
    f = step.frames[fi]
    times[fi] = f.frameValue
    U = np.zeros((len(nlab), 3))
    for b in blocks(f.fieldOutputs["U"], "PLATE-1"):
        U[nmap[b.nodeLabels]] = b.data
    Ue = U[gc]
    F = np.eye(3)[None, None] + np.einsum("eia,egib->egab", Ue, dNdX)
    C = np.einsum("egka,egkb->egab", F, F)
    Eii = 0.5 * (np.einsum("egaa->ega", C) - 1.0)
    eng = np.sqrt(np.maximum(2 * Eii + 1, 0)) - 1.0
    meas = np.abs(eng).max(axis=(1, 2))
    dmin = np.linalg.det(F).min(axis=1)
    upd = meas > meas_max
    meas_max[upd] = meas[upd]
    t_meas_max[upd] = f.frameValue
    detmin = np.minimum(detmin, dmin)
    m = (first_eng < 0) & (meas >= EPS_FAIL)
    first_eng[m] = fi
    m = (first_jac < 0) & ((dmin <= JAC_FAIL) | (dmin <= 0))
    first_jac[m] = fi
    st = np.ones(NE)
    for b in blocks(f.fieldOutputs["STATUS"], "PLATE-1"):
        lab = b.elementLabels
        ok = (lab >= gmin) & (lab <= gmax)
        ii = emap[lab[ok]]
        g = ii >= 0
        st[ii[g]] = b.data[ok][g, 0]
    alive = st > 0.5
    newly = prev_alive & ~alive
    death[newly & (death < 0)] = fi
    meas_at_death[newly] = meas[newly]
    prev_alive = alive
    pe = np.zeros(NE)
    mi = np.zeros(NE)
    for b in blocks(f.fieldOutputs["PEEQ"], "PLATE-1"):
        lab = b.elementLabels
        ok = (lab >= gmin) & (lab <= gmax)
        ii = emap[lab[ok]]
        g = ii >= 0
        np.maximum.at(pe, ii[g], b.data[ok][g, 0])
    for b in blocks(f.fieldOutputs["S"], "PLATE-1"):
        lab = b.elementLabels
        ok = (lab >= gmin) & (lab <= gmax)
        s = b.data[ok]
        v = np.sqrt(0.5 * ((s[:, 0] - s[:, 1]) ** 2 + (s[:, 1] - s[:, 2]) ** 2 + (s[:, 2] - s[:, 0]) ** 2)
                    + 3 * (s[:, 3] ** 2 + s[:, 4] ** 2 + s[:, 5] ** 2))
        ii = emap[lab[ok]]
        g = ii >= 0
        np.maximum.at(mi, ii[g], v[g])
    peeq_max = np.maximum(peeq_max, pe)
    um = (mi > mises_max) & alive
    mises_max[um] = mi[um]
    t_mises_max[um] = f.frameValue
    pf = first_eng >= 0
    curves.append([fi, float(f.frameValue), int(alive.sum()), int(pf.sum()), int((pf & alive).sum()),
                   int((first_jac >= 0).sum()), int((meas >= 0.5 * EPS_FAIL).sum())])
    if fi % 50 == 0:
        sys.stderr.write("frame %d alive %d predVU1fail %d\n" % (fi, int(alive.sum()), int(pf.sum())))
        sys.stderr.flush()

hdr = ("label,x,y,z,r,alive_end,death_frame,death_t,first_eng_frame,first_jac_frame,meas_max,t_meas_max,"
       "detF_min,meas_at_death,peeq_max,mises_max_alive,t_mises_max")
rows = np.column_stack([gl, cen0[:, 0], cen0[:, 1], cen0[:, 2], r0, prev_alive.astype(int), death,
                        np.where(death >= 0, times[np.maximum(death, 0)], -1.0),
                        first_eng, first_jac, meas_max, t_meas_max, detmin, meas_at_death, peeq_max,
                        mises_max, t_mises_max])
np.savetxt(pref + "_elements.csv", rows, delimiter=",", header=hdr, comments="")
json.dump({"times": times.tolist(),
           "curves_cols": ["frame", "t", "alive", "cum_pred_eng", "pred_eng_but_alive", "cum_pred_jac", "n_meas>=half_eps"],
           "curves": curves, "EPS_FAIL": EPS_FAIL, "JAC_FAIL": JAC_FAIL}, open(pref + "_curves.json", "w"))
odb.close()
