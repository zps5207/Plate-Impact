"""Turn an embmesh plywise .inp deck into a static (undeformed) viewer .npz, so the mesh can be inspected in the
WebGL viewer (pack_viewer_data.py -> serve_viewer.py) before any solve.

Handles: Part Node/Element blocks, Assembly Instances with a plain translation line (no rotation), and the roles
Plate/Ply-* -> host, Ball-* -> ball, Fibers-* -> fiber. Two identical frames are written so playback controls work.
Usage: python deck_to_viewer_npz.py <deck.inp> <out.npz>
"""
import json
import re
import sys

import numpy as np


def parse(path):
    parts, insts = {}, []
    cur_part = cur_inst = None
    mode = None
    pend = None
    for raw in open(path, encoding="utf-8", errors="replace"):
        ln = raw.strip()
        if not ln or ln.startswith("**"):
            continue
        if ln.startswith("*"):
            kw = ln.split(",")[0].strip().lower()
            opts = dict(p.strip().split("=", 1) if "=" in p else (p.strip(), "") for p in ln.split(",")[1:])
            mode = None
            pend = None
            if kw == "*part":
                cur_part = parts.setdefault(opts["name"], {"nodes": {}, "elems": {}})
                cur_inst = None
            elif kw == "*end part":
                cur_part = None
            elif kw == "*instance":
                cur_inst = {"name": opts["name"], "part": opts["part"], "t": [0.0, 0.0, 0.0], "got_t": False}
                insts.append(cur_inst)
            elif kw == "*end instance":
                cur_inst = None
            elif kw == "*node" and cur_part is not None:
                mode = "node"
            elif kw == "*element" and cur_part is not None:
                mode = "elem"
                etype = opts.get("type", "")
            continue
        if mode == "node":
            v = ln.split(",")
            cur_part["nodes"][int(v[0])] = (float(v[1]), float(v[2]), float(v[3]))
        elif mode == "elem":
            v = [int(x) for x in ln.replace(" ", "").strip(",").split(",") if x]
            if pend:
                pend.extend(v)
                v = pend
            need = {"C3D8R": 9, "C3D8": 9, "C3D6R": 7, "C3D6": 7, "T3D2": 3, "B31": 3}.get(etype, len(v))
            if len(v) < need:
                pend = v
                continue
            pend = None
            cur_part["elems"].setdefault(etype, []).append(v)
        elif cur_inst is not None and not cur_inst["got_t"]:
            cur_inst["t"] = [float(x) for x in ln.split(",")[:3]]
            cur_inst["got_t"] = True
    return parts, insts


def role(inst):
    n = inst["name"].lower()
    return "ball" if n.startswith("ball") else "fiber" if n.startswith("fiber") else "host"


def main(deck, out):
    parts, insts = parse(deck)
    data, coords = {}, {"host": [], "ball": [], "fiber": []}
    conns = {"host": {}, "ball": {}, "fiber": {}}
    counts = {"host": 0, "ball": 0, "fiber": 0}
    for inst in insts:
        r = role(inst)
        p = parts[inst["part"]]
        ids = sorted(p["nodes"])
        idx = {n: counts[r] + i for i, n in enumerate(ids)}
        xyz = np.array([p["nodes"][n] for n in ids], dtype=np.float64) + np.array(inst["t"])
        coords[r].append(xyz)
        for et, rows in p["elems"].items():
            arr = np.array([[idx[n] for n in row[1:]] for row in rows], dtype=np.int32)
            conns[r].setdefault(et, []).append(arr)
        counts[r] += len(ids)
    for r in coords:
        if not coords[r]:
            continue
        c = np.concatenate(coords[r]).astype(np.float32)
        data[f"{r}_coords0"] = c
        data[f"{r}_pos"] = np.stack([c, c])
        for et, arrs in conns[r].items():
            data[f"{r}_conn_{et}"] = np.concatenate(arrs)
    nh = sum(len(v) for k, v in data.items() if k.startswith("host_conn_"))
    nf = sum(len(v) for k, v in data.items() if k.startswith("fiber_conn_"))
    data["host_status"] = np.ones((2, nh), dtype=np.uint8)
    data["fiber_status"] = np.ones((2, nf), dtype=np.uint8)
    data["times"] = np.array([0.0, 1e-9])
    data["meta"] = np.array(json.dumps({"odb": deck.replace("\\", "/").split("/")[-1] + " (undeformed mesh preview)"}))
    np.savez(out, **data)
    print({k: tuple(v.shape) for k, v in data.items()})


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
