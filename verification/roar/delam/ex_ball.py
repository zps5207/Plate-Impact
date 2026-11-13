"""Ball-focused ODB extraction for the vp5/vp6 impactor-failure investigation.

Usage: abaqus python ex_ball.py <odb> <out.npz> [nframes]

Per sampled frame, for instance BALL-1: nodal U, element STATUS, element Mises and PEEQ,
nodal CPRESS (contact pressure on ball nodes). For the rest of the model: the 60 largest
CPRESS values per frame with instance name, node label and original node coordinates, and
the count of loaded nodes per instance group. Node/element connectivity of the ball is saved
once. Works on a partial ODB (reads whatever frames exist).
"""
from __future__ import print_function
import sys
import numpy as np
from odbAccess import openOdb

odb = openOdb(sys.argv[1], readOnly=True)
nsel = int(sys.argv[3]) if len(sys.argv) > 3 else 80
st = list(odb.steps.values())[0]
nf = len(st.frames)
step = max(1, nf // nsel)
idx = sorted(set(list(range(0, nf, step)) + [nf - 1]))
root = odb.rootAssembly
ball = root.instances['BALL-1']

nlab = np.array([n.label for n in ball.nodes], dtype=np.int64)
ncoord = np.array([n.coordinates for n in ball.nodes], dtype=np.float64)
nmap = dict((int(l), i) for i, l in enumerate(nlab))
elab = np.array([e.label for e in ball.elements], dtype=np.int64)
emap = dict((int(l), i) for i, l in enumerate(elab))
econn = [list(e.connectivity) for e in ball.elements]
maxc = max(len(c) for c in econn)
econn_arr = np.full((len(econn), maxc), -1, dtype=np.int64)
for i, c in enumerate(econn):
    econn_arr[i, :len(c)] = c


def grp(name):
    n = name.lower()
    if n.startswith('fibers'):
        return 'fiber'
    if n.startswith('ply'):
        return 'host'
    return 'ball' if n.startswith('ball') else 'other'


def blocks(f, prefix, region=None):
    keys = [k for k in f.fieldOutputs.keys() if k.split()[0] == prefix]
    if not keys:
        return []
    fo = f.fieldOutputs[keys[0]]
    if region is not None:
        fo = fo.getSubset(region=region)
    return list(fo.bulkDataBlocks)


times, U, STATUS, MISES, PEEQ, CP = [], [], [], [], [], []
top_val, top_inst, top_lab, top_xyz, loaded = [], [], [], [], []
for i in idx:
    f = st.frames[i]
    times.append(float(f.frameValue))
    u = np.full((len(nlab), 3), np.nan)
    for b in blocks(f, 'U', ball):
        for lab, row in zip(b.nodeLabels, b.data):
            u[nmap[int(lab)]] = row
    U.append(u)
    s = np.full(len(elab), np.nan)
    for b in blocks(f, 'STATUS', ball):
        for lab, v in zip(b.elementLabels, b.data.flatten()):
            s[emap[int(lab)]] = v
    STATUS.append(s)
    m = np.full(len(elab), np.nan)
    for b in blocks(f, 'S', ball):
        try:
            for lab, v in zip(b.elementLabels, b.mises):
                m[emap[int(lab)]] = max(m[emap[int(lab)]], v) if m[emap[int(lab)]] == m[emap[int(lab)]] else v
        except Exception:
            pass
    MISES.append(m)
    p = np.full(len(elab), np.nan)
    for b in blocks(f, 'PEEQ', ball):
        try:
            for lab, v in zip(b.elementLabels, b.data.flatten()):
                p[emap[int(lab)]] = v
        except Exception:
            pass
    PEEQ.append(p)
    cb = np.full(len(nlab), np.nan)
    allv = []
    cnt = {}
    for b in blocks(f, 'CPRESS'):
        iname = b.instance.name if b.instance is not None else ''
        g = grp(iname)
        data = b.data.flatten()
        cnt[g] = cnt.get(g, 0) + int((data > 0).sum())
        if g == 'ball':
            for lab, v in zip(b.nodeLabels, data):
                cb[nmap[int(lab)]] = v
        order = np.argsort(-data)[:60]
        for o in order:
            allv.append((float(data[o]), iname, int(b.nodeLabels[o])))
    CP.append(cb)
    allv.sort(reverse=True)
    allv = allv[:60]
    tv, ti, tl, tx = [], [], [], []
    for v, iname, lab in allv:
        xyz = [np.nan, np.nan, np.nan]
        try:
            xyz = list(root.instances[iname].getNodeFromLabel(lab).coordinates)
        except Exception:
            pass
        tv.append(v)
        ti.append(iname)
        tl.append(lab)
        tx.append(xyz)
    top_val.append(tv)
    top_inst.append(ti)
    top_lab.append(tl)
    top_xyz.append(tx)
    loaded.append([cnt.get('ball', 0), cnt.get('host', 0), cnt.get('fiber', 0)])
    print('frame', i, 't=%.3e' % times[-1], flush=True)


def pad(rows, fill):
    n = max(len(r) for r in rows)
    return [list(r) + [fill] * (n - len(r)) for r in rows]


np.savez_compressed(
    sys.argv[2], frame_idx=np.array(idx), times=np.array(times), nframes_in_odb=nf,
    ball_node_labels=nlab, ball_node_coords0=ncoord, ball_elem_labels=elab, ball_elem_conn=econn_arr,
    U=np.array(U, dtype=np.float32), STATUS=np.array(STATUS, dtype=np.float32),
    MISES=np.array(MISES, dtype=np.float32), PEEQ=np.array(PEEQ, dtype=np.float32),
    CPRESS_ball=np.array(CP, dtype=np.float32), loaded_nodes_ball_host_fiber=np.array(loaded),
    top_cpress=np.array(pad(top_val, 0.0), dtype=np.float32), top_inst=np.array(pad(top_inst, '')),
    top_label=np.array(pad(top_lab, 0)), top_xyz0=np.array(pad(top_xyz, [np.nan] * 3), dtype=np.float32))
print('ok', len(idx), 'frames of', nf)
odb.close()
