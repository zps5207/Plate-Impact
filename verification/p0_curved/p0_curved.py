"""P0: can the current pipeline handle a spherical-cap plate stacked by translation?

Builds a spherical-cap stack (front surface = sphere, back = front translated by -T in z,
N plies), lays prototype 0/90 mid-surface fibers (straight in the xy projection, height
follows the ply mid-surface), and checks the pieces the ply-wise mode relies on:
  1. fiber vertices lie inside their own ply's host hexes (inverse_hex),
  2. fiber-to-interface normal distance matches the d <= h*cos(theta) derivation,
  3. fiber_volume_rows works on the warped hexes and gives sane volume fractions.
Units: metres (matches Flatv2)."""
from __future__ import annotations
import sys, json
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from embmesh.geometry import inverse_hex, hex_volume
from embmesh.fibers import Fiber, _layer_positions
from embmesh.model import Element
from embmesh.volume import fiber_volume_rows


def cap_stack(R=0.1, half=0.024, n=12, T=1e-3, plies=3):
    """Regular xy grid over [-half,half]^2, z=f(x,y) sphere (apex at 0, convex up)."""
    xs = np.linspace(-half, half, n + 1)
    f = lambda x, y: np.sqrt(R * R - x * x - y * y) - R
    nodes, elems, ply_of = {}, {}, {}
    nid = lambda k, i, j: 1 + k * (n + 1) ** 2 + i * (n + 1) + j     # k = level 0..plies
    h = T / plies
    for k in range(plies + 1):
        for i, x in enumerate(xs):
            for j, y in enumerate(xs):
                nodes[nid(k, i, j)] = np.array([x, y, f(x, y) - k * h])  # level 0 = front (top)
    # ply p spans levels p (top) .. p+1 (bottom); duplicate interface nodes per ply
    nodes_p = {}
    eid = 1
    for p in range(plies):
        base = {}
        for lvl in (p, p + 1):
            for i in range(n + 1):
                for j in range(n + 1):
                    key = (p, lvl - p, i, j)
                    nodes_p[len(nodes_p) + 1] = nodes[nid(lvl, i, j)]
                    base[key] = len(nodes_p)
        for i in range(n):
            for j in range(n):
                b = lambda l, a, c: base[(p, l, a, c)]
                conn = [b(1, i, j), b(1, i + 1, j), b(1, i + 1, j + 1), b(1, i, j + 1),
                        b(0, i, j), b(0, i + 1, j), b(0, i + 1, j + 1), b(0, i, j + 1)]
                elems[eid] = Element(eid, tuple(conn), "C3D8R"); ply_of[eid] = p; eid += 1
    return nodes_p, elems, ply_of, h, f


def midsurface_fibers(nodes, elems, ply_of, h, f, d, gap, plies, half, first_dir=0):
    """Prototype of plan 3.3: line at fixed y (0 deg, along x) or fixed x (90 deg); polyline
    vertices at every in-plane element-edge crossing; z = f(x,y) - (p+1/2)*h."""
    fibers, label = [], 1
    xs = sorted({round(float(v[0]), 12) for v in nodes.values()})
    for p in range(plies):
        direction = (first_dir + p) % 2          # 0 -> along x, 1 -> along y
        along, across = (0, 1) if direction == 0 else (1, 0)
        lo, hi = -half, half
        for c in _layer_positions(lo, hi, d, gap):
            c = c + 0.0
            u0, u1 = lo + d / 2, hi - d / 2          # end inset d/2 (plan 3.3 / user)
            # crossings with grid lines of the other in-plane coordinate: regular grid here
            ts = [u for u in xs if u0 < u < u1]
            us = np.array([u0] + ts + [u1])
            pts = []
            for u in us:
                xy = np.zeros(2); xy[along] = u; xy[across] = c
                pts.append([xy[0], xy[1], f(xy[0], xy[1]) - (p + .5) * h])
            fibers.append(Fiber(label, np.array(pts), p, "t0" if direction == 0 else "t90")); label += 1
    return fibers


def check(R, d, plies=3, T=1e-3, n=12, half=0.024, gap=0.0):
    nodes, elems, ply_of, h, f = cap_stack(R, half, n, T, plies)
    fibers = midsurface_fibers(nodes, elems, ply_of, h, f, d, gap, plies, half)
    out = dict(R=R, d=d, h=h, plies=plies, n_fibers=len(fibers))
    # worst slope from node spacing (plan 3.4)
    xs = np.linspace(-half, half, n + 1)
    th = max(np.degrees(np.arctan(np.hypot(*np.gradient(np.array([[f(x, y) for y in xs] for x in xs]), xs[1] - xs[0])))).ravel())
    out["theta_max_deg_from_nodes"] = float(th)
    out["d_max"] = float(h * np.cos(np.radians(th)))
    # 1. every fiber vertex inside a host hex of its own ply
    host = {p: [(e, [nodes[i] for i in e.connectivity[:8]]) for e in elems.values() if ply_of[e.label] == p] for p in range(plies)}
    def inside_own(ply, pt):
        for _, hp in host[ply]:
            a = np.asarray(hp)
            if np.all(pt >= a.min(0) - 1e-9) and np.all(pt <= a.max(0) + 1e-9) and inverse_hex(pt, hp) is not None:
                return True
        return False
    bad = 0; tot = 0
    for fb in fibers:
        for pt in fb.points:
            tot += 1
            if not inside_own(fb.layer, pt): bad += 1
    out["vertices_total"], out["vertices_outside_own_ply"] = tot, bad
    # mid-segment midpoints too (chord error of straight segments through warped hexes)
    badm = totm = 0
    for fb in fibers:
        for a, b in zip(fb.points[:-1], fb.points[1:]):
            totm += 1
            if not inside_own(fb.layer, (a + b) / 2): badm += 1
    out["midpoints_total"], out["midpoints_outside_own_ply"] = totm, badm
    # 2. normal distance from fiber centre to the ply's bottom/top surface vs d/2
    def dist_to_surface(pt, offset):
        # nearest point on z = f(x,y) - offset by dense local sampling around pt's xy
        g = np.linspace(-4 * h, 4 * h, 81)
        X, Y = pt[0] + g[:, None], pt[1] + g[None, :]
        Z = f(X, Y) - offset
        return float(np.sqrt((X - pt[0]) ** 2 + (Y - pt[1]) ** 2 + (Z - pt[2]) ** 2).min())
    mind = 1e9
    for fb in fibers:
        p = fb.layer
        for pt in fb.points[::max(1, len(fb.points) // 6)]:
            mind = min(mind, dist_to_surface(pt, p * h), dist_to_surface(pt, (p + 1) * h))
    out["min_center_to_interface"] = mind
    out["half_d"] = d / 2
    out["fits_numerically"] = bool(mind >= d / 2 - 1e-9)
    out["fits_by_formula"] = bool(d <= out["d_max"] + 1e-12)
    # 3. volume machinery on warped hexes (ply 0 hosts only, its own fibers)
    sub = {e.label: e for e in elems.values() if ply_of[e.label] == 0}
    rows = fiber_volume_rows(sub, nodes, [fb for fb in fibers if fb.layer == 0], d)
    vf = [r[3] for r in rows]
    out["ply0_vf_min_max_mean"] = [float(min(vf)), float(max(vf)), float(np.mean(vf))]
    out["hex_vol_ratio_min_max"] = [float(min(hex_volume(np.array([nodes[i] for i in e.connectivity[:8]])) for e in sub.values())),
                                    float(max(hex_volume(np.array([nodes[i] for i in e.connectivity[:8]])) for e in sub.values()))]
    return out


if __name__ == "__main__":
    res = []
    for R, d in [(1e9, 3.0e-4), (0.1, 2.9e-4), (0.1, 3.3e-4)]:
        res.append(check(R, d))
    print(json.dumps(res, indent=1))
