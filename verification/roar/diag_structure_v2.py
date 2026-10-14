"""flat_v2 full diagnostics 1/3: ODB inventory + history outputs.
Run: abaqus python diag_structure_v2.py flat_v2.odb > structure_v2.json"""
from __future__ import print_function
import json, sys, collections
from odbAccess import openOdb

odb = openOdb(sys.argv[1], readOnly=True)
asm = odb.rootAssembly
out = {}
out["steps"] = {}
for sn, st in odb.steps.items():
    fr = st.frames
    fo = {}
    for k, v in fr[-1].fieldOutputs.items():
        try:
            fo[k] = {"type": str(v.type), "components": list(v.componentLabels),
                     "positions": [str(l.position) for l in v.locations]}
        except Exception as e:
            fo[k] = str(e)
    out["steps"][sn] = {"nframes": len(fr), "t0": fr[0].frameValue, "t1": fr[-1].frameValue,
                        "nHistoryRegions": len(st.historyRegions), "fieldOutputs_last": fo,
                        "description": st.description}
out["instances"] = {}
for n, inst in asm.instances.items():
    c = collections.Counter(e.type for e in inst.elements)
    out["instances"][n] = {"nnodes": len(inst.nodes), "nelements": len(inst.elements), "types": dict(c),
                           "elementSets": list(inst.elementSets.keys()), "nodeSets": list(inst.nodeSets.keys())}
    try:
        out["instances"][n]["surfaces"] = list(inst.surfaces.keys())
    except Exception:
        pass
out["assembly_elementSets"] = dict((k, sum(len(b) for b in v.elements)) for k, v in asm.elementSets.items())
out["assembly_nodeSets"] = dict((k, sum(len(b) for b in v.nodes)) for k, v in asm.nodeSets.items())
try:
    out["assembly_surfaces"] = list(asm.surfaces.keys())
except Exception as e:
    out["assembly_surfaces"] = str(e)
try:
    out["sectionCategories"] = dict((k, v.description) for k, v in odb.sectionCategories.items())
except Exception as e:
    out["sectionCategories"] = str(e)
hist = {}
for sn, st in odb.steps.items():
    for rn, reg in st.historyRegions.items():
        entry = {}
        for hn, ho in reg.historyOutputs.items():
            d = ho.data
            if not d:
                continue
            ys = [float(p[1]) for p in d]
            n = len(d)
            k = max(1, n // 150)
            entry[hn] = {"n": n, "first": ys[0], "last": ys[-1], "min": min(ys), "max": max(ys),
                         "series": [(float(d[i][0]), float(d[i][1])) for i in range(0, n, k)]}
        hist[rn] = entry
        if len(hist) > 60:
            break
out["history"] = hist
print(json.dumps(out, default=float))
odb.close()
