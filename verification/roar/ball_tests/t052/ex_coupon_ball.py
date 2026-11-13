"""Abaqus Python: ball extraction from a T-052 coupon ODB (part-less deck, ball elsets BALL_C3D8R / BALL_C3D6).

Usage: abaqus python ex_coupon_ball.py <odb> <out.npz>
Saves per frame: ball hex node coordinates (initial + U), ball element STATUS, plus energy histories.
"""
from __future__ import print_function
import sys
import numpy as np
from odbAccess import openOdb

odb = openOdb(sys.argv[1], readOnly=True)
step = list(odb.steps.values())[0]
root = odb.rootAssembly
inst = None
for ins in root.instances.values():
    if 'BALL_C3D8R' in ins.elementSets.keys():
        inst = ins
if inst is None:
    raise SystemExit('no instance with BALL_C3D8R: %s' % list(root.instances.keys()))
els = list(inst.elementSets['BALL_C3D8R'].elements)
if 'BALL_C3D6' in inst.elementSets.keys():
    els += list(inst.elementSets['BALL_C3D6'].elements)
el = np.array([e.label for e in els], dtype=np.int64)
ty = np.array([e.type for e in els])
nodes = {}
for e in els:
    for n in e.connectivity:
        nodes[int(n)] = None
nl = np.array(sorted(nodes), dtype=np.int64)
nm = dict((int(v), i) for i, v in enumerate(nl))
conn = np.full((len(els), 8), -1, dtype=np.int32)
for i, e in enumerate(els):
    for j, n in enumerate(e.connectivity):
        conn[i, j] = nm[int(n)]
ncoord = {}
for n in inst.nodes:
    if n.label in nodes:
        ncoord[n.label] = n.coordinates
c0 = np.array([ncoord[int(v)] for v in nl], dtype=np.float64)
em = dict((int(v), i) for i, v in enumerate(el))
ball_nodes = inst.nodeSets['BALL_NODES'] if 'BALL_NODES' in inst.nodeSets.keys() else None
times, status, pos = [], [], []
for fr in step.frames:
    if 'STATUS' not in fr.fieldOutputs or 'U' not in fr.fieldOutputs:
        continue
    st = np.ones(len(els), dtype=np.float32)
    for v in fr.fieldOutputs['STATUS'].getSubset(region=inst).values:
        i = em.get(int(v.elementLabel))
        if i is not None:
            st[i] = v.data
    u = np.zeros((len(nl), 3))
    for v in fr.fieldOutputs['U'].getSubset(region=inst).values:
        i = nm.get(int(v.nodeLabel))
        if i is not None:
            u[i] = v.data
    times.append(fr.frameValue)
    status.append(st)
    pos.append((c0 + u).astype(np.float32))
energy = {}
for hn, hr in step.historyRegions.items():
    if 'Assembly' in hn:
        for k in ('ALLKE', 'ETOTAL', 'ALLAE'):
            if k in hr.historyOutputs:
                energy[k] = np.array(hr.historyOutputs[k].data, dtype=np.float64)
np.savez_compressed(sys.argv[2], times=np.array(times), status=np.array(status), pos=np.array(pos), conn=conn,
                    etype=ty, c0=c0, **dict(('E_' + k, v) for k, v in energy.items()))
print('saved', sys.argv[2], len(times), 'frames', len(els), 'ball elems')
