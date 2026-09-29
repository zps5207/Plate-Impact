from __future__ import annotations
import numpy as np

def hex_volume(points: np.ndarray) -> float:
    p = np.asarray(points, float)
    # 2x2x2 quadrature, standard Abaqus C3D8 ordering.
    signs = np.array([[-1,-1,1],[-1,1,1],[1,1,1],[1,-1,1],[-1,-1,-1],[-1,1,-1],[1,1,-1],[1,-1,-1]], float)
    v = 0.0
    for a in (-1/np.sqrt(3), 1/np.sqrt(3)):
      for b in (-1/np.sqrt(3), 1/np.sqrt(3)):
       for c in (-1/np.sqrt(3), 1/np.sqrt(3)):
        d = np.column_stack((signs[:,0]*(1+b*signs[:,1])*(1+c*signs[:,2]), signs[:,1]*(1+a*signs[:,0])*(1+c*signs[:,2]), signs[:,2]*(1+a*signs[:,0])*(1+b*signs[:,1])))/8
        v += abs(np.linalg.det(p.T @ d))
    return float(v)

def inverse_hex(point: np.ndarray, nodes: np.ndarray, tol=1e-8, max_iter=20):
    x = np.asarray(point,float); p=np.asarray(nodes,float); q=np.zeros(3)
    s=np.array([[-1,-1,1],[-1,1,1],[1,1,1],[1,-1,1],[-1,-1,-1],[-1,1,-1],[1,1,-1],[1,-1,-1]],float)
    for _ in range(max_iter):
        N=np.prod((1+q*s)/2,axis=1); r=N@p-x
        d=np.column_stack((s[:,0]*np.prod((1+q*s)[:,[1,2]]/2,axis=1)/2, s[:,1]*np.prod((1+q*s)[:,[0,2]]/2,axis=1)/2, s[:,2]*np.prod((1+q*s)[:,[0,1]]/2,axis=1)/2))
        J=p.T@d
        try: dq=np.linalg.solve(J,r)
        except np.linalg.LinAlgError: return None
        q-=dq
        if np.linalg.norm(dq)<tol: break
    return q if np.all(q >= -1-tol) and np.all(q <= 1+tol) and np.linalg.norm(N@p-x)<1e-6 else None

def point_in_hex(point,nodes,tol=1e-8): return inverse_hex(point,nodes,tol) is not None

def hex_center_jacobian(nodes):
    p=np.asarray(nodes,float); s=np.array([[-1,-1,1],[-1,1,1],[1,1,1],[1,-1,1],[-1,-1,-1],[-1,1,-1],[1,1,-1],[1,-1,-1]],float)
    d=np.column_stack((s[:,0]/8,s[:,1]/8,s[:,2]/8)); return float(np.linalg.det(p.T@d))

# Standard Abaqus C3D8 node order (indices into an 8-point array), grouped by the
# three local hex axes (xi, eta, zeta). Each entry is (face-at--1, face-at-+1).
_HEX_FACE_PAIRS = (
    ((0, 1, 4, 5), (2, 3, 6, 7)),   # xi
    ((0, 3, 4, 7), (1, 2, 5, 6)),   # eta
    ((4, 5, 6, 7), (0, 1, 2, 3)),   # zeta
)


def hex_face_pairs(hex_points):
    """For one C3D8 hex, return per local axis: (center_lo, center_hi, normal_lo->hi, span)."""
    p = np.asarray(hex_points, float)
    out = []
    for lo_idx, hi_idx in _HEX_FACE_PAIRS:
        c_lo = p[list(lo_idx)].mean(0)
        c_hi = p[list(hi_idx)].mean(0)
        d = c_hi - c_lo
        span = float(np.linalg.norm(d))
        n = d / span if span > 1e-14 else d
        out.append((c_lo, c_hi, n, span))
    return out


def hex_thickness_axis(hex_points):
    """Local axis index (0=xi,1=eta,2=zeta) whose opposite-face separation is smallest --
    i.e. the through-thickness direction for a plate-like hex. Ties broken by axis order."""
    spans = [fp[3] for fp in hex_face_pairs(hex_points)]
    return int(np.argmin(spans))


def hex_face_normal(hex_points, face_indices):
    """Outward-ish normal of a quad face (four node indices, CCW as seen from outside)."""
    p = np.asarray(hex_points, float)[list(face_indices)]
    n = np.cross(p[1] - p[0], p[2] - p[0])
    m = np.linalg.norm(n)
    return n / m if m > 1e-14 else n


def clip_segment_hex_bounds(a,b,nodes,tol=1e-9,n_samples=21,n_bisect=30):
    """Parametric (left, right) in [0,1] where segment a->b's *centerline* is
    inside the hex, or None if it never enters. Sampling/bisection against the
    inverse mapping; exact for affine hexes, a good approximation for mildly
    curved/skewed ones. n_samples/n_bisect are kept modest -- point_in_hex is a
    Newton solve, so this runs once per (fiber segment, host element) pair a
    caller has already bbox-pruned down to."""
    a=np.asarray(a,float); b=np.asarray(b,float); d=b-a
    ts=np.linspace(0,1,n_samples); inside=np.array([point_in_hex(a+t*d,nodes,tol) for t in ts])
    if not inside.any(): return None
    # refine each transition with binary search
    def edge(t0,t1, want):
      for _ in range(n_bisect):
       m=(t0+t1)/2
       if point_in_hex(a+m*d,nodes,tol)==want: t1=m
       else: t0=m
      return t1 if want else t0
    i=np.where(inside)[0][0]; j=np.where(inside)[0][-1]
    left=0 if i==0 else edge(ts[i-1],ts[i],True)
    right=1 if j==len(ts)-1 else edge(ts[j],ts[j+1],False)
    return (left, right) if right > left else None

def clip_segment_hex(a,b,nodes,tol=1e-9,n_samples=21,n_bisect=30):
    bounds = clip_segment_hex_bounds(a,b,nodes,tol,n_samples,n_bisect)
    if bounds is None: return 0.0
    left, right = bounds
    return (right-left)*np.linalg.norm(np.asarray(b,float)-np.asarray(a,float))


_DISK_RINGS = 3
_DISK_ANGLES = 8
# A deliberately non-axis-aligned, non-diagonal *direction* applied (scaled by
# the fiber radius, the one length scale always meaningful here regardless of
# the model's unit system) to every swept-volume sample point before the
# inside/outside test. Structured meshes (this tool's main use case) very
# often put adjacent hosts' shared faces at "nice" coordinates, and fiber
# layers/rows are placed at exact pitch multiples -- so *both* the disk
# cross-section samples and the along-axis Simpson stations can land exactly
# on a shared host face, where floating-point tolerance would count the point
# as "inside" both neighboring hosts (over-count) or neither (under-count).
# Nudging every sample point by the same small, generic vector breaks that
# tie consistently, one way, everywhere.
_TIE_BREAK_DIR = np.array([0.53, 0.68, 0.84])   # arbitrary, no special alignment; not unit length on purpose


def _disk_offsets(e1, e2, radius):
    """Deterministic equal-area polar sample points on a disk of given radius, as
    offsets from the disk center (e1, e2 span the disk's plane). Ring radii are
    spaced so every ring covers equal disk area (r_k = R*sqrt((k+0.5)/n_rings)),
    so a plain unweighted average over all points is already an unbiased area
    estimator -- no separate per-ring area weights are needed. The whole pattern
    carries a fixed irrational-ish phase offset so no sample point ever lands
    exactly on a 0/90/180/270 degree angle: e1/e2 are built from global axes
    (see swept_cylinder_hex_volume), so for a fiber running along an axis-aligned
    host boundary (the common case for this tool's structured meshes) an
    unshifted pattern would put several sample points exactly ON that shared
    face, double-counting them as "inside" both neighboring hosts."""
    phase = 0.37   # radians; arbitrary, just far from any multiple of pi/2
    pts = []
    for k in range(_DISK_RINGS):
        rk = radius * np.sqrt((k + 0.5) / _DISK_RINGS)
        for m in range(_DISK_ANGLES):
            ang = phase + 2 * np.pi * (m + 0.5 * (k % 2)) / _DISK_ANGLES   # stagger rings to avoid radial alignment
            pts.append(rk * (np.cos(ang) * e1 + np.sin(ang) * e2))
    return np.asarray(pts)


def swept_cylinder_hex_volume(a, b, radius, nodes, tol=1e-8, n_along=7, t_range=None):
    """Volume of the intersection between a straight cylinder (centerline a->b,
    the given radius) and one host hex -- unlike `clip_segment_hex`'s length x
    area approximation (which implicitly assumes the *entire* cross-section is
    inside wherever the centerline is), this weights each cross-section by the
    actual fraction of the fiber's disk that lies inside the host, using a
    deterministic equal-area polar sample of the disk at each of `n_along`
    stations along the segment (composite Simpson's rule along the axis). This
    matters most for a fiber running near a host face/edge/corner, or for a
    host smaller than the fiber pitch, where the length-based approximation
    over- or under-counts one host's share relative to its neighbors.

    Known residual limitation: the tie-break jitter (see _TIE_BREAK_DIR) that
    keeps adjacent hosts from double-counting a shared face only acts across
    the fiber's own cross-section, never along its tangent -- a jitter with a
    tangential component would just as easily shift a station that sits on
    the model's true *outer* surface, silently losing real volume there,
    which is worse than the bounded over-count this leaves in one specific
    case: when one of the `n_along` Simpson stations lands exactly on a
    host-to-host boundary *along the fiber's own length* (two hosts stacked
    end-to-end on a single long straight segment, on a sufficiently regular
    grid that a pitch fraction lines up with a station fraction). That
    over-count is bounded by roughly 1/(n_along-1) of the segment's
    contribution to the two hosts sharing that boundary; raising n_along
    shrinks it. It does not accumulate silently outside that specific
    alignment, and does not affect the fully-inside or cross-section-tie
    cases (both exact, see tests).

    `t_range`, an optional (t0, t1) in [0, 1], restricts the along-axis
    quadrature to that sub-interval of the full a->b segment instead of the
    whole thing. A fiber is very often a single long segment spanning many
    hosts (the common case for a flat-plate layup); calling this once per
    host with the *whole* segment and a small fixed n_along wastes almost all
    the quadrature resolution on parts of the segment nowhere near that host,
    and starves the part that matters -- which is exactly what causes the
    along-axis alignment case above. Callers that already know roughly where
    the segment is near a given host (e.g. from `clip_segment_hex_bounds`,
    padded by a margin) should pass that range in."""
    a = np.asarray(a, float); b = np.asarray(b, float); p = np.asarray(nodes, float)
    d = b - a; L = np.linalg.norm(d)
    if L < 1e-14 or radius <= 0: return 0.0
    t = d / L
    t0, t1 = (0.0, 1.0) if t_range is None else t_range
    if t1 <= t0: return 0.0
    ref = np.array([0., 0., 1.]) if abs(t[2]) < 0.9 else np.array([1., 0., 0.])
    e1 = np.cross(t, ref); e1 /= np.linalg.norm(e1)
    e2 = np.cross(t, e1)
    offsets = _disk_offsets(e1, e2, radius)
    # Tie-break jitter is confined to the cross-section plane (e1/e2), never
    # along the fiber's own tangent t: a component along t would shift *every*
    # along-axis Simpson station, including the segment's own true endpoints,
    # which can coincide with the model's genuine outer surface (not a shared
    # host-to-host face) -- shifting those outward silently drops real volume
    # instead of just resolving a tie between two neighbors. See BUGS.md.
    jit_dir = _TIE_BREAK_DIR - (_TIE_BREAK_DIR @ t) * t
    jn = np.linalg.norm(jit_dir)
    jitter = radius * 1e-6 * (jit_dir / jn if jn > 1e-9 else e1)
    hmin, hmax = p.min(0), p.max(0)
    n = n_along if n_along % 2 == 1 else n_along + 1   # Simpson needs an odd point count
    ss = np.linspace(t0, t1, n)
    fracs = np.empty(n)
    for i, s in enumerate(ss):
        c = a + s * d
        if np.any(c + radius < hmin - tol) or np.any(c - radius > hmax + tol):
            fracs[i] = 0.0; continue
        pts = c + offsets + jitter
        fracs[i] = np.mean([point_in_hex(q, p, tol) for q in pts])
    if not fracs.any(): return 0.0
    w = np.ones(n); w[1:-1:2] = 4; w[2:-1:2] = 2   # Simpson's composite weights
    sub_L = (t1 - t0) * L
    integral = (sub_L / (n - 1) / 3.0) * float(np.dot(w, fracs))
    return max(0.0, integral) * (np.pi * radius ** 2)
