"""Read-only v500 deck audit. Run from any directory with Python + numpy."""
from collections import Counter, defaultdict
from pathlib import Path
import json
import math
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from embmesh.geometry import clip_segment_hex, hex_volume, swept_cylinder_hex_volume

DECK = ROOT / "verification/roar/t_nc/v500/v500_deck.inp"


def parse_deck():
    nodes = {"Plate": {}, "EMBFIB": {}}
    elements = {"VU1": {}, "T3D2": {}}
    fiber_type = {}
    vf = {}
    part = mode = element_type = None
    element_set = None
    current_label = None
    values = []
    with DECK.open(encoding="utf-8", errors="replace") as stream:
        for line in stream:
            line = line.strip()
            if not line or line.startswith("**"):
                continue
            if line.startswith("*"):
                if mode == "status" and current_label is not None:
                    assert len(values) == 107
                    vf[current_label] = values[106]
                current_label = None
                if line.lower().startswith("*part,"):
                    part = line.split("name=", 1)[1].split(",")[0]
                elif line.lower().startswith("*end part"):
                    part = None
                if line.lower().startswith("*node"):
                    mode = "node"
                elif line.lower().startswith("*element,"):
                    mode = "element"
                    element_type = line.lower().split("type=", 1)[1].split(",")[0].upper()
                    element_set = line.lower().split("elset=", 1)[1].split(",")[0] if "elset=" in line.lower() else ""
                elif line.lower().startswith("*initial conditions, type=solution"):
                    mode = "status"
                else:
                    mode = None
                continue
            parts = [p.strip() for p in line.split(",") if p.strip()]
            if mode == "node" and part in nodes:
                nodes[part][int(parts[0])] = np.array([float(x) for x in parts[1:4]])
            elif mode == "element" and element_type in elements:
                label = int(parts[0])
                elements[element_type][label] = tuple(int(x) for x in parts[1:])
                if element_type == "T3D2":
                    fiber_type[label] = "T0" if element_set.endswith("t0") else "T90"
            elif mode == "status":
                if parts[0].startswith("Plate-1."):
                    if current_label is not None:
                        assert len(values) == 107, (current_label, len(values))
                        vf[current_label] = values[106]
                    current_label = int(parts[0].split(".")[1])
                    values = [float(x) for x in parts[1:]]
                elif current_label is not None:
                    values.extend(float(x) for x in parts)
    return nodes, elements, vf, fiber_type


def main():
    nodes, elems, vf, fiber_type = parse_deck()
    host_nodes = nodes["Plate"]
    fiber_nodes = nodes["EMBFIB"]
    # Plate-1 has +0.01 z translation followed by +90 degrees about the
    # negative x axis through (0,0,0.01); EMBFIB is at assembly coordinates.
    host_nodes = {k: np.array([v[0], v[2], .01-v[1]]) for k, v in host_nodes.items()}
    hosts = elems["VU1"]
    fibers = elems["T3D2"]
    assert len(hosts) == len(vf) == 24000
    vals = np.array([vf[k] for k in sorted(hosts)])
    bins = [0, 1e-12, .1, .25, .5, .75, 1, 1.25, 1.5, 2, 2.5]
    hist = np.histogram(vals, bins=bins)[0]
    print("nodes/elements", len(host_nodes), len(fiber_nodes), len(hosts), len(fibers))
    print("vf positive/ge1/max", int((vals > 0).sum()), int((vals >= 1).sum()), float(vals.max()))
    print("histogram", [(bins[i], bins[i+1], int(hist[i])) for i in range(len(hist))])
    labels = sorted(hosts)
    centers = np.array([np.mean([host_nodes[n] for n in hosts[k]], axis=0) for k in labels])
    volumes = np.array([hex_volume(np.array([host_nodes[n] for n in hosts[k]])) for k in labels])
    crowd = vals >= 1
    print("global xyz range", centers.min(0), centers.max(0))
    print("crowded xyz range", centers[crowd].min(0), centers[crowd].max(0))
    print("global vol q", np.quantile(volumes, [0,.1,.5,.9,1]))
    print("crowded vol q", np.quantile(volumes[crowd], [0,.1,.5,.9,1]))
    print("crowded center radius q", np.quantile(np.linalg.norm(centers[crowd, :2], axis=1), [0,.25,.5,.75,1]))
    print("all center radius q", np.quantile(np.linalg.norm(centers[:, :2], axis=1), [0,.25,.5,.75,1]))
    radii = np.linalg.norm(centers[:, :2], axis=1)
    for lo, hi in ((0,.02),(.02,.03),(.03,.04),(.04,.045),(.045,.05)):
        mask = (radii >= lo) & (radii < hi)
        print("radial bin", lo, hi, "crowded/total", int((crowd & mask).sum()), int(mask.sum()),
              "median volume", float(np.median(volumes[mask])) if mask.any() else None)
    print("crowded by z layer", sorted(Counter(np.round(centers[crowd,2], 4)).items()))
    z_levels = sorted(set(round(float(p[2]), 7) for p in fiber_nodes.values()))
    print("fiber z levels", z_levels)
    print("fiber segments by set", dict(Counter(fiber_type.values())))
    print("fiber z by set", {kind: sorted(set(round(float(fiber_nodes[fibers[label][0]][2]), 7)
                                                  for label, value in fiber_type.items() if value == kind))
                            for kind in ("T0", "T90")})
    for axis in range(3):
        lo, hi = centers[:,axis].min(), centers[:,axis].max()
        near = (centers[:,axis] <= lo+.002) | (centers[:,axis] >= hi-.002)
        print("near axis", axis, int((crowd & near).sum()), int(near.sum()))
    top = sorted(vf, key=vf.get, reverse=True)[:8]
    sample = [402] + top[:3] + [labels[i] for i in np.flatnonzero(crowd)[::max(1,int(crowd.sum()/4))][:4]]
    sample = list(dict.fromkeys(sample))
    # Bbox-pruned independent re-sum of every deck T3D2 segment.
    a = np.array([fiber_nodes[c[0]] for c in fibers.values()])
    b = np.array([fiber_nodes[c[1]] for c in fibers.values()])
    segment_keys = [tuple(sorted(c)) for c in fibers.values()]
    print("duplicate node-pair segments", sum(n-1 for n in Counter(segment_keys).values() if n>1))
    # Abaqus *Solid Section's area: pi*(0.001 m)^2/4.
    area = math.pi * (.001 ** 2) / 4
    for label in sample:
        hp = np.array([host_nodes[n] for n in hosts[label]])
        hmin, hmax = hp.min(0), hp.max(0)
        candidate = np.flatnonzero(np.all(np.maximum(a,b)>=hmin-1e-9,axis=1)
                                & np.all(np.minimum(a,b)<=hmax+1e-9,axis=1))
        contributions = []
        fiber_labels = list(fibers)
        for index in candidate:
            length = clip_segment_hex(a[index], b[index], hp)
            if length > 1e-10:
                contributions.append((fiber_labels[index], length))
        total_len = sum(length for _, length in contributions)
        computed = total_len*area/hex_volume(hp)
        precise = None
        if label in sample[:4]:
            precise = sum(swept_cylinder_hex_volume(a[index], b[index], .0005, hp, n_along=21)
                          for index in candidate) / hex_volume(hp)
        print("sample", label, "center", hp.mean(0), "volume", hex_volume(hp),
              "Vf deck/recalc", vf[label], computed, "segment count", len(contributions),
              "length sum", total_len, "precise approx", precise, "lengths", contributions)


if __name__ == "__main__":
    main()
