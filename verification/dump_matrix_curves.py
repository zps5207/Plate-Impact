"""Dump stress/strain/energy histories of every matrix_material ODB to CSV.
Run: abaqus python dump_matrix_curves.py <dir>   (reads <dir>/run_*/*.odb)
"""
import sys, glob, os
from odbAccess import openOdb

d = sys.argv[1]
suffix = sys.argv[2] if len(sys.argv) > 2 else ""
for path in sorted(glob.glob(os.path.join(d, "run_*", "*.odb"))):
    name = os.path.basename(path)[:-4]
    if not name.endswith(suffix):
        continue
    mode = "shear" if "shear" in name else "tension"
    odb = openOdb(path, readOnly=True)
    step = odb.steps[list(odb.steps.keys())[0]]
    pn = 3 if mode == "shear" else 2
    rows = []
    for fr in step.frames:
        u = fr.fieldOutputs["U"]; rf = fr.fieldOutputs["RF"]
        u1 = [v.data[0] for v in u.values if v.nodeLabel == pn][0]
        sel = (1, 2, 5, 6) if mode == "shear" else (1, 4, 5, 8)
        f = -sum(v.data[0] for v in rf.values if v.nodeLabel in sel)
        rows.append((fr.frameValue, u1, f))
    en = {}
    for hr in step.historyRegions.values():
        for k in ("ALLIE", "ALLPD", "ALLKE", "ALLDMD", "ALLWK"):
            if k in hr.historyOutputs:
                en[k] = hr.historyOutputs[k].data
    with open(os.path.join(d, name + "_curve.csv"), "w") as o:
        o.write("t,u1,F\n")
        for r in rows:
            o.write("%g,%g,%g\n" % r)
    with open(os.path.join(d, name + "_energy.csv"), "w") as o:
        keys = sorted(en)
        o.write("t," + ",".join(keys) + "\n")
        n = min(len(en[k]) for k in keys)
        for i in range(n):
            o.write("%g," % en[keys[0]][i][0] + ",".join("%g" % en[k][i][1] for k in keys) + "\n")
    odb.close()
    print("dumped", name)
