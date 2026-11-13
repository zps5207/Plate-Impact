"""Probe how CSDMG / CDISP are stored in a plywise ODB (abaqus python q_csdmg.py job.odb)."""
from __future__ import print_function
import sys
from collections import defaultdict
import numpy as np
from odbAccess import openOdb

odb = openOdb(sys.argv[1], readOnly=True)
st = list(odb.steps.values())[0]
print('frames', len(st.frames))
for fi in (len(st.frames) // 2, len(st.frames) - 1):
    fr = st.frames[fi]
    print('--- frame', fi, 't=%.3e' % fr.frameValue)
    keys = sorted(fr.fieldOutputs.keys())
    print('n fieldOutput keys', len(keys), 'contact-like:', [k for k in keys if k.startswith('CS') or k.startswith('CD') or 'CSDMG' in k][:12])
    names = [k for k in keys if k.startswith('CSDMG')][:1] + [k for k in keys if k.startswith('CDISP')][:1]
    for name in names:
        fo = fr.fieldOutputs[name]
        print(name, 'type', fo.type, 'locations', [(str(l.position), [str(s) for s in l.sectionPoints][:2]) for l in fo.locations],
              'components', fo.componentLabels, 'nvalues', len(fo.values))
        v0 = fo.values[0]
        print('  first value attrs:', [a for a in dir(v0) if not a.startswith('_')][:30])
        print('  first: nodeLabel', getattr(v0, 'nodeLabel', None), 'elementLabel', getattr(v0, 'elementLabel', None),
              'instance', getattr(getattr(v0, 'instance', None), 'name', None), 'data', v0.data)
        blocks = fo.bulkDataBlocks
        per = defaultdict(int)
        for b in blocks:
            per[b.instance.name if b.instance is not None else None] += len(b.data)
        print('  bulk blocks:', len(blocks), 'per instance (first 6):', list(per.items())[:6], 'total instances', len(per))
        b = blocks[0]
        print('  block0: instance', b.instance.name if b.instance is not None else None,
              'nodeLabels' , None if b.nodeLabels is None else len(b.nodeLabels),
              'elementLabels', None if b.elementLabels is None else len(b.elementLabels), 'data shape', np.asarray(b.data).shape)
        if name == 'CSDMG':
            d = np.concatenate([np.asarray(b.data).ravel() for b in blocks])
            print('  CSDMG stats: n', d.size, 'min', d.min(), 'max', d.max(), '>=0.5', int((d >= 0.5).sum()), '>=0.99', int((d >= 0.99).sum()))
odb.close()
