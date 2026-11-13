"""Abaqus Python: plate (HOST) extraction from a T-052 coupon ODB.

Usage: abaqus python ex_coupon_plate.py <odb> <out.npz>
Per frame: host node positions (initial + U), host element STATUS and PEEQ, fiber element STATUS.
Host = elset HOST (C3D8R matrix hexes of all 6 plies); fibers = elset FIBERS.
"""
from __future__ import print_function
import sys
import numpy as np
from odbAccess import openOdb

odb = openOdb(sys.argv[1], readOnly=True)
step = list(odb.steps.values())[0]
inst = None
for ins in odb.rootAssembly.instances.values():
    if 'HOST' in ins.elementSets.keys():
        inst = ins
if inst is None:
    raise SystemExit('no instance with HOST: %s' % list(odb.rootAssembly.instances.keys()))
hosts = list(inst.elementSets['HOST'].elements)
fibers = list(inst.elementSets['FIBERS'].elements) if 'FIBERS' in inst.elementSets.keys() else []
hl = np.array([e.label for e in hosts], dtype=np.int64)
hm = dict((int(v), i) for i, v in enumerate(hl))
fm = dict((int(e.label), i) for i, e in enumerate(fibers))
nodes = sorted(set(int(n) for e in hosts for n in e.connectivity))
nm = dict((v, i) for i, v in enumerate(nodes))
conn = np.array([[nm[int(n)] for n in e.connectivity] for e in hosts], dtype=np.int32)
coord = {}
for n in inst.nodes:
    if n.label in nm:
        coord[n.label] = n.coordinates
c0 = np.array([coord[v] for v in nodes], dtype=np.float64)
times, pos, hstat, hpeeq, fstat = [], [], [], [], []
for fi in range(len(step.frames)):
    try:
        fr = step.frames[fi]
        if 'STATUS' not in fr.fieldOutputs or 'U' not in fr.fieldOutputs:
            continue
        u = np.zeros((len(nodes), 3))
        for v in fr.fieldOutputs['U'].getSubset(region=inst).values:
            i = nm.get(int(v.nodeLabel))
            if i is not None:
                u[i] = v.data
        hs = np.ones(len(hosts), dtype=np.float32)
        fs = np.ones(len(fibers), dtype=np.float32)
        for v in fr.fieldOutputs['STATUS'].getSubset(region=inst).values:
            lab = int(v.elementLabel)
            if lab in hm:
                hs[hm[lab]] = v.data
            elif lab in fm:
                fs[fm[lab]] = v.data
        pe = np.full(len(hosts), np.nan, dtype=np.float32)
        if 'PEEQ' in fr.fieldOutputs:
            for v in fr.fieldOutputs['PEEQ'].getSubset(region=inst).values:
                i = hm.get(int(v.elementLabel))
                if i is not None:
                    pe[i] = v.data
        times.append(fr.frameValue)
        pos.append((c0 + u).astype(np.float32))
        hstat.append(hs)
        hpeeq.append(pe)
        fstat.append(fs)
    except Exception as ex:
        print('skipped frame index', fi, str(ex)[:60])
        continue
np.savez_compressed(sys.argv[2], times=np.array(times), pos=np.array(pos), conn=conn, c0=c0, host_status=np.array(hstat),
                    host_peeq=np.array(hpeeq), fiber_status=np.array(fstat))
print('saved', sys.argv[2], len(times), 'frames', len(hosts), 'host elems', len(fibers), 'fibers')
