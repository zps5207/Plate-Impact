from __future__ import print_function
import sys, json
from odbAccess import openOdb
odb = openOdb(sys.argv[1], readOnly=True)
st = list(odb.steps.values())[0]
out = {'frames': len(st.frames), 'fields': sorted(st.frames[-1].fieldOutputs.keys()), 'hist': {}, 'csdmg': [], 'csmax': []}
for k, r in st.historyRegions.items():
    for n, h in r.historyOutputs.items():
        out['hist'][k + '|' + n] = [[float(a), float(b)] for a, b in h.data]
for f in st.frames:
    for name, key in (('CSDMG', 'csdmg'), ('CSMAXSCRT', 'csmax')):
        if name in f.fieldOutputs:
            v = [float(x.data) for x in f.fieldOutputs[name].values]
            out[key].append([float(f.frameValue), max(v) if v else None, min(v) if v else None, len(v)])
json.dump(out, open(sys.argv[2], 'w'))
print('ok', out['fields'])
odb.close()
