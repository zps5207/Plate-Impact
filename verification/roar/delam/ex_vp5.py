from __future__ import print_function
import sys, json
from odbAccess import openOdb
odb = openOdb(sys.argv[1], readOnly=True)
st = list(odb.steps.values())[0]
nf = len(st.frames)
out = {'nframes': nf, 't_end': float(st.frames[-1].frameValue), 'energy': {}, 'status': [], 'cs': []}
step = max(1, nf // 40)
idx = sorted(set(list(range(0, nf, step)) + [nf - 1]))

def grp(name):
    name = name.lower()
    if name.startswith('fibers'):
        return 'fiber'
    if name.startswith('ply'):
        return 'host'
    return 'ball' if name.startswith('ball') else 'other:' + name

for i in idx:
    f = st.frames[i]
    row = {'t': float(f.frameValue), 'frame': i}
    if 'STATUS' in f.fieldOutputs:
        cnt = {}
        for b in f.fieldOutputs['STATUS'].bulkDataBlocks:
            g = grp(b.instance.name if b.instance is not None else '')
            n = len(b.data)
            dead = int((b.data.flatten() < 0.5).sum())
            c = cnt.setdefault(g, [0, 0])
            c[0] += n
            c[1] += dead
        row['cnt'] = cnt
    out['status'].append(row)

for i, f in enumerate(st.frames):
    key = [k for k in f.fieldOutputs.keys() if k.split()[0] in ('CSDMG',)]
    if not key:
        continue
    vals = []
    for b in f.fieldOutputs[key[0]].bulkDataBlocks:
        vals.extend([float(x) for x in b.data.flatten()])
    out['cs'].append({'frame': i, 't': float(f.frameValue), 'n': len(vals),
                      'max': max(vals) if vals else None,
                      'ge99': sum(1 for v in vals if v >= 0.99),
                      'ge50': sum(1 for v in vals if v >= 0.5)})

for k, r in st.historyRegions.items():
    if k.startswith('Assembly'):
        for n, h in r.historyOutputs.items():
            out['energy'][n] = [[float(a), float(b)] for a, b in h.data]
json.dump(out, open(sys.argv[2], 'w'))
print('ok', len(idx), len(out['cs']), sorted(out['energy'].keys()))
odb.close()
