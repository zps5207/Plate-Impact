from __future__ import annotations
import numpy as np
from .geometry import clip_segment_hex, hex_volume

def _polyline_clip_len(points, hp, hmin=None, hmax=None):
    """Length of a (possibly multi-segment) fiber polyline clipped to one host hex.
    Segments are pruned against the host's own bbox individually -- pruning by the
    *whole polyline's* bbox (as a single straight-line check would) does nothing
    for a closed loop (e.g. a hoop fiber circling a cylindrical shell), whose
    overall bbox touches nearly every host in the ring even though any one
    segment only passes near a handful of them."""
    if hmin is None: hmin, hmax = hp.min(0), hp.max(0)
    total = 0.0
    for a, b in zip(points[:-1], points[1:]):
        if np.any(np.maximum(a, b) < hmin - 1e-9) or np.any(np.minimum(a, b) > hmax + 1e-9):
            continue
        total += clip_segment_hex(a, b, hp)
    return total

def host_volume_rows(elements, nodes, fibers):
    rows=[]
    for label,e in elements.items():
        hp=np.array([nodes[i] for i in e.connectivity[:8]],float)
        total=t0=t90=0.0
        for f in fibers:
            L=_polyline_clip_len(f.points, hp)
            total+=L
            if f.direction=="t0": t0+=L
            else: t90+=L
        area=getattr(fibers[0],"diameter",0.0) # optional metadata
        rows.append((label,hex_volume(hp),total*area if area else total,t0,t90))
    return rows

def fiber_volume_rows(elements,nodes,fibers,diameter):
    area=np.pi*diameter**2/4; out=[]
    fiber_bbox = [(f, f.points.min(0), f.points.max(0)) for f in fibers]
    for label,e in elements.items():
        hp=np.array([nodes[i] for i in e.connectivity[:8]],float); host=hex_volume(hp); l0=l90=0.
        hmin,hmax=hp.min(0),hp.max(0)
        for f, fmin, fmax in fiber_bbox:
            if np.any(fmax < hmin - 1e-9) or np.any(fmin > hmax + 1e-9): continue
            L=_polyline_clip_len(f.points, hp, hmin, hmax)
            if L == 0.0: continue
            if f.direction=="t0": l0+=L
            else: l90+=L
        fv=(l0+l90)*area; out.append((label,host,fv,fv/host if host else 0.,l0,l90))
    return out
