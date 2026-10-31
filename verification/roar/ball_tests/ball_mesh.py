"""Uniform hex quarter-sphere for the Vals steel ball (replaces the pole-collapsed revolved mesh).

Part frame matches Vals.inp: sphere centre at the origin, pole axis along part y, kept quarter is x >= 0, z >= 0
(symmetry planes x = 0 and z = 0). A cube grid [0,1] x [-1,1] x [0,1] (a, c, b) is pushed onto the sphere shell by
shell, so the pole sits at a cube-face centre instead of a wedge-collapsed axis; every element is a C3D8R.
"""
import numpy as np

R = 0.009525


def build(n=28, nr=10, hc=0.5, iters=0, relax=0.5):
    """Full-sphere O-grid (inner cube + six outer blocks), cut to the x >= 0, z >= 0 quarter.

    n   cells across the inner cube edge and across each outer face (even)
    nr  radial layers per outer block
    hc  inner cube half-width as a fraction of R / sqrt(3)... see below: hc * R, must stay < 1/sqrt(3)
    Returns (nodes (N,3) m, hexes (M,8) zero-based)."""
    h = hc * R
    g = np.linspace(-1, 1, n + 1)
    keys = {}
    pts = []

    def node(p):
        k = tuple(np.round(p / 1e-9).astype(np.int64))
        i = keys.get(k)
        if i is None:
            i = keys[k] = len(pts)
            pts.append(p)
        return i

    hexes = []
    # inner cube
    ix = np.empty((n + 1,) * 3, dtype=np.int64)
    for i in range(n + 1):
        for j in range(n + 1):
            for k in range(n + 1):
                ix[i, j, k] = node(h * np.array([g[i], g[j], g[k]]))
    for i in range(n):
        for j in range(n):
            for k in range(n):
                hexes.append([ix[i, j, k], ix[i + 1, j, k], ix[i + 1, j + 1, k], ix[i, j + 1, k],
                              ix[i, j, k + 1], ix[i + 1, j, k + 1], ix[i + 1, j + 1, k + 1], ix[i, j + 1, k + 1]])
    # outer blocks: axis permutations of the +z block
    perms = [(0, 1, 2), (1, 2, 0), (2, 0, 1)]
    for perm in perms:
        for sign in (1.0, -1.0):
            lay = np.empty((n + 1, n + 1, nr + 1), dtype=np.int64)
            for a in range(n + 1):
                for b in range(n + 1):
                    t_ = np.tan(np.pi / 4 * np.array([g[a], g[b]]))
                    d = np.array([t_[0], t_[1], 1.0])
                    d = d / np.linalg.norm(d) * R
                    inner = np.array([h * g[a], h * g[b], h])
                    for r in range(nr + 1):
                        w = r / nr
                        p = (1 - w) * inner + w * d
                        q = np.empty(3)
                        q[perm[0]], q[perm[1]], q[perm[2]] = p[0], p[1], p[2] * sign
                        lay[a, b, r] = node(q)
            cells = []
            for a in range(n):
                for b in range(n):
                    for r in range(nr):
                        c = [lay[a, b, r], lay[a + 1, b, r], lay[a + 1, b + 1, r], lay[a, b + 1, r],
                             lay[a, b, r + 1], lay[a + 1, b, r + 1], lay[a + 1, b + 1, r + 1], lay[a, b + 1, r + 1]]
                        cells.append(c)
            hexes.extend(cells)
    pts = np.array(pts)
    hexes = np.array(hexes)
    # orient every hex positively
    P = pts[hexes]
    vol = np.einsum("ij,ij->i", np.cross(P[:, 1] - P[:, 0], P[:, 3] - P[:, 0]), P[:, 4] - P[:, 0])
    flip = vol < 0
    hexes[flip] = hexes[flip][:, [0, 3, 2, 1, 4, 7, 6, 5]]
    # keep the x >= 0, z >= 0 quarter
    cen = pts[hexes].mean(1)
    keep = (cen[:, 0] > 0) & (cen[:, 2] > 0)
    hexes = hexes[keep]
    used = np.unique(hexes)
    remap = -np.ones(len(pts), dtype=np.int64)
    remap[used] = np.arange(len(used))
    pts, hexes = pts[used], remap[hexes]
    if iters:
        pts, hexes = smooth(pts, hexes, iters, relax)
    return pts, hexes


def smooth(pts, hexes, iters=60, relax=0.5):
    """Laplacian smoothing that keeps the geometry: surface nodes slide on the sphere, nodes on the x = 0 / z = 0
    symmetry planes stay in their plane, nodes on the pole axis move along it."""
    edges = np.array([(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4), (0, 4), (1, 5), (2, 6), (3, 7)])
    e = np.unique(np.sort(hexes[:, edges].reshape(-1, 2), axis=1), axis=0)
    n = len(pts)
    deg = np.bincount(e.ravel(), minlength=n).astype(float)
    r = np.linalg.norm(pts, axis=1)
    surf = r > R * (1 - 1e-9)
    onx = pts[:, 0] < 1e-12
    onz = pts[:, 2] < 1e-12
    pts = pts.copy()
    for _ in range(iters):
        acc = np.zeros_like(pts)
        np.add.at(acc, e[:, 0], pts[e[:, 1]])
        np.add.at(acc, e[:, 1], pts[e[:, 0]])
        new = pts + relax * (acc / deg[:, None] - pts)
        new[onx, 0] = 0.0
        new[onz, 2] = 0.0
        rr = np.linalg.norm(new[surf], axis=1, keepdims=True)
        new[surf] *= R / rr
        pts = new
    return pts, hexes


def quality(pts, hexes):
    """Per-element min scaled Jacobian (corner), edge lengths (min, max), and signed total volume."""
    sgn = [(-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1), (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)]
    P = pts[hexes]
    edges = [(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4), (0, 4), (1, 5), (2, 6), (3, 7)]
    el = np.stack([np.linalg.norm(P[:, i] - P[:, j], axis=1) for i, j in edges], 1)
    nbr = {0: (1, 3, 4), 1: (2, 0, 5), 2: (3, 1, 6), 3: (0, 2, 7), 4: (7, 5, 0), 5: (4, 6, 1), 6: (5, 7, 2), 7: (6, 4, 3)}
    sj = np.full(len(hexes), 9.0)
    for v, (p1, p2, p3) in nbr.items():
        e1, e2, e3 = P[:, p1] - P[:, v], P[:, p2] - P[:, v], P[:, p3] - P[:, v]
        t = np.einsum("ij,ij->i", np.cross(e1, e2), e3)
        n = np.linalg.norm(e1, axis=1) * np.linalg.norm(e2, axis=1) * np.linalg.norm(e3, axis=1)
        sj = np.minimum(sj, t / n)
    vol = np.einsum("ij,ij->i", np.cross(P[:, 1] - P[:, 0], P[:, 3] - P[:, 0]), P[:, 4] - P[:, 0])
    return dict(sj=sj, emin=el.min(1), emax=el.max(1), vol_total=float(vol.sum()))


if __name__ == "__main__":
    import sys
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 28
    nr = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    hc = float(sys.argv[3]) if len(sys.argv) > 3 else 0.5
    pts, hx = build(n, nr, hc)
    q = quality(pts, hx)
    print(len(pts), "nodes", len(hx), "hexes")
    print("edge mm min/median/max", q["emin"].min() * 1e3, np.median(q["emin"]) * 1e3, q["emax"].max() * 1e3)
    print("scaled jac min/1%/median", q["sj"].min(), np.percentile(q["sj"], 1), np.median(q["sj"]))
    print("quarter volume ratio to exact", q["vol_total"] / (np.pi * R ** 3 / 3.0))
