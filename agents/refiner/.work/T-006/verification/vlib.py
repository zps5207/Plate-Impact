"""Independent helpers for the verification run (no imports from embmesh)."""
import subprocess, sys, os, re, json, math
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVID = ROOT / "verification" / "evidence"
PY = sys.executable
EXE = ROOT / "dist" / "embmesh.exe"

def run_cli(args, exe=False, cwd=ROOT):
    cmd = ([str(EXE)] if exe else [PY, "-m", "embmesh.cli"]) + [str(a) for a in args]
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr

def hex_plate_deck(path, nx, ny, nz, Lx=1.0, Ly=1.0, Lz=1.0, etype="C3D8R", inst_lines=(), part="PLATE",
                   inst="PLATE-1", elset="HOST", x0=0.0, y0=0.0, z0=0.0, extra_part="", extra_asm="", tail="",
                   skip_elems=()):
    """Structured hex block, Abaqus C3D8 node order. Returns node dict and elem dict (independent of embmesh)."""
    nid = lambda i, j, k: 1 + i + (nx + 1) * (j + (ny + 1) * k)
    nodes = {}
    for k in range(nz + 1):
        for j in range(ny + 1):
            for i in range(nx + 1):
                nodes[nid(i, j, k)] = (x0 + Lx * i / nx, y0 + Ly * j / ny, z0 + Lz * k / nz)
    elems = {}
    e = 1
    for k in range(nz):
        for j in range(ny):
            for i in range(nx):
                if e not in skip_elems:
                    elems[e] = (nid(i, j, k), nid(i + 1, j, k), nid(i + 1, j + 1, k), nid(i, j + 1, k),
                                nid(i, j, k + 1), nid(i + 1, j, k + 1), nid(i + 1, j + 1, k + 1), nid(i, j + 1, k + 1))
                e += 1
    L = [f"*Heading", f"** verification deck {Path(path).name}", f"*Part, name={part}", "*Node"]
    L += [f"{n}, {c[0]:.12g}, {c[1]:.12g}, {c[2]:.12g}" for n, c in nodes.items()]
    L += [f"*Element, type={etype}, elset={elset}"] + [f"{e}, " + ", ".join(map(str, c)) for e, c in elems.items()]
    L += [extra_part] if extra_part else []
    L += ["*End Part", "*Assembly, name=Assembly", f"*Instance, name={inst}, part={part}"] + list(inst_lines) + ["*End Instance"]
    L += [extra_asm] if extra_asm else []
    L += ["*End Assembly"]
    if tail: L += [tail]
    Path(path).write_text("\n".join(L) + "\n")
    return nodes, elems

def parse_fibers_from_inp(path):
    """Extract embmesh-generated fibers (nodes 'EMBMESH_NODES', elements 'EMBMESH_FIBERS') from output deck."""
    lines = Path(path).read_text().splitlines()
    sec = None; nodes = {}; elems = {}; etype = None
    for ln in lines:
        s = ln.strip()
        if not s or s.startswith("**"): continue
        if s.startswith("*"):
            low = s.lower()
            sec = None
            if low.startswith("*node") and "embmesh_nodes" in low: sec = "n"
            elif low.startswith("*element") and "embmesh_fibers" in low:
                sec = "e"; etype = re.search(r"type=([^,\s]+)", s, re.I).group(1)
            continue
        v = [x.strip() for x in s.split(",")]
        if sec == "n": nodes[int(v[0])] = np.array([float(x) for x in v[1:4]])
        elif sec == "e": elems[int(v[0])] = [int(x) for x in v[1:]]
    fibers = {k: np.array([nodes[n] for n in c]) for k, c in elems.items()}
    return fibers, etype, nodes

def seg_seg_dist(p1, q1, p2, q2):
    """Minimum distance between segments (Ericson)."""
    d1 = q1 - p1; d2 = q2 - p2; r = p1 - p2
    a = d1 @ d1; e = d2 @ d2; f = d2 @ r
    EPS = 1e-14
    if a <= EPS and e <= EPS: return np.linalg.norm(r)
    if a <= EPS: s = 0.0; t = np.clip(f / e, 0, 1)
    else:
        c = d1 @ r
        if e <= EPS: t = 0.0; s = np.clip(-c / a, 0, 1)
        else:
            b = d1 @ d2; den = a * e - b * b
            s = np.clip((b * f - c * e) / den, 0, 1) if den > EPS else 0.0
            t = (b * s + f) / e
            if t < 0: t = 0.0; s = np.clip(-c / a, 0, 1)
            elif t > 1: t = 1.0; s = np.clip((b - c) / a, 0, 1)
    return np.linalg.norm((p1 + d1 * s) - (p2 + d2 * t))

def min_center_dist(fibers):
    keys = list(fibers); m = math.inf; pair = None
    P = [fibers[k] for k in keys]
    lo = np.array([p.min(0) for p in P]); hi = np.array([p.max(0) for p in P])
    for i in range(len(P)):
        for j in range(i + 1, len(P)):
            # coarse reject if bboxes are farther than current min
            gap = np.maximum(0, np.maximum(lo[i] - hi[j], lo[j] - hi[i]))
            if np.linalg.norm(gap) >= m: continue
            d = seg_seg_dist(P[i][0], P[i][-1], P[j][0], P[j][-1])
            if d < m: m = d; pair = (keys[i], keys[j])
    return m, pair

def read_csv(path):
    rows = [ln.split(",") for ln in Path(path).read_text().strip().splitlines()]
    hdr = rows[0]
    numeric_cols = [i for i, h in enumerate(hdr) if h.strip() != "instance"]
    hdr = [hdr[i] for i in numeric_cols]
    data = np.array([[float(r[i]) for i in numeric_cols] for r in rows[1:]])
    return hdr, data

def clip_len_box(a, b, lo, hi):
    """Length of segment a->b inside axis-aligned box (slab method)."""
    d = b - a; t0, t1 = 0.0, 1.0
    for ax in range(3):
        if abs(d[ax]) < 1e-15:
            if a[ax] < lo[ax] - 1e-12 or a[ax] > hi[ax] + 1e-12: return 0.0
        else:
            u = (lo[ax] - a[ax]) / d[ax]; v = (hi[ax] - a[ax]) / d[ax]
            if u > v: u, v = v, u
            t0 = max(t0, u); t1 = min(t1, v)
            if t0 > t1: return 0.0
    return (t1 - t0) * np.linalg.norm(d)

# ---------------- independent hex geometry (own implementation) ----------------
_S = np.array([[-1,-1,-1],[1,-1,-1],[1,1,-1],[-1,1,-1],[-1,-1,1],[1,-1,1],[1,1,1],[-1,1,1]], float)  # Abaqus C3D8 node order (bottom face first)
def _N(xi):
    xi = np.atleast_2d(xi)
    return np.prod(1 + xi[:, None, :] * _S[None], axis=2) / 8.0          # (n,8)
def _dN(xi):
    xi = np.atleast_2d(xi); n = xi.shape[0]; out = np.zeros((n, 8, 3))
    f = 1 + xi[:, None, :] * _S[None]
    for a in range(3):
        o = [b for b in range(3) if b != a]
        out[:, :, a] = _S[None, :, a] * f[:, :, o[0]] * f[:, :, o[1]] / 8.0
    return out
def hex_volume_own(P):
    g = 1 / math.sqrt(3); v = 0.0
    for a in (-g, g):
        for b in (-g, g):
            for c in (-g, g):
                J = np.einsum("nia,ib->nab", _dN(np.array([a, b, c])), np.asarray(P))[0]
                v += abs(np.linalg.det(J))
    return v
def inv_hex_own(X, P, it=40):
    """Vectorised Newton inverse isoparametric map. Returns xi (n,3) and converged mask."""
    X = np.atleast_2d(X); P = np.asarray(P); xi = np.zeros_like(X)
    for _ in range(it):
        r = _N(xi) @ P - X
        J = np.einsum("nia,ib->nab", _dN(xi), P)                       # d x_b / d xi_a
        dxi = np.linalg.solve(np.transpose(J, (0, 2, 1)), r[:, :, None])[:, :, 0]
        xi = xi - dxi
        if np.max(np.abs(dxi)) < 1e-13: break
    ok = np.linalg.norm(_N(xi) @ P - X, axis=1) < 1e-9
    return xi, ok
def clip_len_hex_own(a, b, P, n=20001):
    """Length of segment a->b inside a general hex by dense sampling + inverse map (error ~ L/n)."""
    t = np.linspace(0, 1, n); X = a[None] + t[:, None] * (b - a)[None]
    lo, hi = P.min(0) - 1e-9, P.max(0) + 1e-9
    m = np.all((X >= lo) & (X <= hi), axis=1)
    if not m.any(): return 0.0
    xi, ok = inv_hex_own(X[m], P)
    inside = ok & np.all(np.abs(xi) <= 1 + 1e-9, axis=1)
    return inside.sum() / (n - 1) * np.linalg.norm(b - a)   # trapezoid-ish; ends contribute half weight -> fine at 1e-4

def parse_vtk_polydata(path):
    L = Path(path).read_text().splitlines(); i = 0; pts = []; lines = []; scal = []
    while i < len(L):
        s = L[i].split()
        if s and s[0] == "POINTS":
            n = int(s[1]); pts = np.array([[float(x) for x in L[i + 1 + k].split()] for k in range(n)]); i += n
        elif s and s[0] == "LINES":
            n = int(s[1]); lines = [[int(x) for x in L[i + 1 + k].split()[1:]] for k in range(n)]; i += n
        elif s and s[0] == "LOOKUP_TABLE":
            scal = [float(x) for x in L[i + 1:] if x.strip()]; break
        i += 1
    return pts, lines, np.array(scal)

def wall(fn, *a, **k):
    import time; t = time.time(); r = fn(*a, **k); return r, time.time() - t
