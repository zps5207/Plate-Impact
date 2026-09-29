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


def clip_segment_hex(a,b,nodes,tol=1e-9,n_samples=21,n_bisect=30):
    # Sampling/bisection against the inverse mapping; exact for affine hexes, a
    # good approximation for mildly curved/skewed ones. n_samples/n_bisect are
    # kept modest -- point_in_hex is a Newton solve, so this runs once per
    # (fiber segment, host element) pair a caller has already bbox-pruned down to.
    a=np.asarray(a,float); b=np.asarray(b,float); d=b-a
    ts=np.linspace(0,1,n_samples); inside=np.array([point_in_hex(a+t*d,nodes,tol) for t in ts])
    if not inside.any(): return 0.0
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
    return max(0.0,right-left)*np.linalg.norm(d)
