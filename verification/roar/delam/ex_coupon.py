from __future__ import print_function
import sys, json
from odbAccess import openOdb
odb = openOdb(sys.argv[1], readOnly=True)
st = list(odb.steps.values())[0]
out = {'nframes': len(st.frames), 't_end': float(st.frames[-1].frameValue), 'cs': [], 'host': [], 'fiber': [], 'energy': {}}
f0 = st.frames[-1]
out['fields'] = sorted(f0.fieldOutputs.keys())
for f in st.frames:
    row = {'t': float(f.frameValue)}
    for name in ('CSDMG', 'CSMAXSCRT'):
        key = [k for k in f.fieldOutputs.keys() if k.split()[0] == name]
        if key:
            fo = f.fieldOutputs[key[0]]
            vals = []
            try:
                for b in fo.bulkDataBlocks:
                    vals.extend([float(x) for x in b.data.flatten()])
            except Exception as e:
                row['err_' + name] = str(e)
            if not vals:
                vals = [float(v.data) for v in fo.values]
            row[name] = [len(vals), max(vals) if vals else None, sum(1 for v in vals if v >= 0.99), sum(1 for v in vals if v >= 0.5)]
    for key, setn in (('host', 'HOST'), ('fiber', 'FIBERS')):
        if 'STATUS' in f.fieldOutputs:
            pass
    out['cs'].append(row)
# element status by set
inst = odb.rootAssembly.instances.values()[0]
for key, setn in (('host', 'HOST'), ('fiber', 'FIBERS')):
    try:
        es = inst.elementSets[setn]
    except KeyError:
        es = odb.rootAssembly.elementSets[setn]
    for f in st.frames:
        if 'STATUS' in f.fieldOutputs:
            v = f.fieldOutputs['STATUS'].getSubset(region=es).values
            out[key].append([float(f.frameValue), len(v), sum(1 for x in v if x.data < 0.5)])
for k, r in st.historyRegions.items():
    if k.startswith('Assembly'):
        for n, h in r.historyOutputs.items():
            out['energy'][n] = [[float(a), float(b)] for a, b in h.data]
json.dump(out, open(sys.argv[2], 'w'))
print('ok', out['fields'])
odb.close()
