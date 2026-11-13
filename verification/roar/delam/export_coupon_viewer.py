"""Export a coupon ODB (flat deck: one instance, elsets HOST / BALL / FIBERS) to the viewer .npz layout
used by agents/drafter/outbox/T-021/pack_viewer_data.py.  Run with abaqus python:
    abaqus python export_coupon_viewer.py job.odb out.npz
"""
from __future__ import print_function
import json
import sys
sys.path.insert(0, "/scratch/zps5207/ctv/delam")
import numpy as np
from odbAccess import openOdb
from export_odb_viewer import build_role, flatten_elements


def main():
    odb = openOdb(sys.argv[1], readOnly=True)
    try:
        step = list(odb.steps.values())[0]
        root = odb.rootAssembly
        inst = list(root.instances.values())[0]
        iname = inst.name

        def elems(setname):
            es = inst.elementSets[setname] if setname in inst.elementSets.keys() else root.elementSets[setname]
            return sorted(flatten_elements(es.elements), key=lambda e: e.label)

        host_el, ball_el, fib_el = elems("HOST"), elems("BALL"), elems("FIBERS")
        roles = [build_role(odb, "host", {iname: host_el}), build_role(odb, "ball", {iname: ball_el}),
                 build_role(odb, "fiber", {iname: fib_el})]
        nfr = len(step.frames)
        times = np.array([f.frameValue for f in step.frames])
        for r in roles:
            r["pos"] = np.zeros((nfr, len(r["coords0"]), 3), dtype=np.float32)
        host_index = dict(((n, l), i) for i, (n, l, _t) in enumerate(roles[0]["element_order"]))
        status = np.ones((nfr, len(host_index)), dtype=np.uint8)
        for fi, frame in enumerate(step.frames):
            for r in roles:
                r["pos"][fi] = r["coords0"]
            for block in frame.fieldOutputs["U"].bulkDataBlocks:
                labels = np.asarray(block.nodeLabels)
                data = np.asarray(block.data)[:, :3]
                for r in roles:
                    off, rl = r["blocks"][iname]
                    idx = np.searchsorted(rl, labels)
                    idx[idx >= len(rl)] = 0
                    ok = rl[idx] == labels
                    rows = off + idx[ok]
                    r["pos"][fi, rows, :] = (r["coords0"][rows] + data[ok]).astype(np.float32)
            if "STATUS" in frame.fieldOutputs:
                for block in frame.fieldOutputs["STATUS"].bulkDataBlocks:
                    labels = np.asarray(block.elementLabels)
                    vals = np.asarray(block.data).reshape(len(labels), -1).min(axis=1)
                    for l, v in zip(labels, vals):
                        k = (iname, int(l))
                        if k in host_index:
                            status[fi, host_index[k]] = 1 if v >= 0.5 else 0
        out = {"times": times, "host_status": status,
               "meta": np.array(json.dumps({"odb": sys.argv[1], "roles": ["host", "ball", "fiber"],
                                            "types": dict((r["name"], sorted(r["conn"])) for r in roles)}))}
        for r in roles:
            out[r["name"] + "_coords0"] = r["coords0"].astype(np.float32)
            out[r["name"] + "_pos"] = r["pos"]
            for t, c in r["conn"].items():
                out["%s_conn_%s" % (r["name"], t)] = c
        np.savez_compressed(sys.argv[2], **out)
        print("wrote", sys.argv[2], "frames", nfr)
    finally:
        odb.close()


if __name__ == "__main__":
    main()
