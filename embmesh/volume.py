from __future__ import annotations
import numpy as np
from .geometry import clip_segment_hex, clip_segment_hex_bounds, hex_volume, swept_cylinder_hex_volume

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

def fiber_volume_rows(elements, nodes, fibers, diameter, progress=None):
    area=np.pi*diameter**2/4; out=[]
    fiber_bbox = [(f, f.points.min(0), f.points.max(0)) for f in fibers]
    total_hosts = len(elements)
    for index, (label, e) in enumerate(elements.items(), start=1):
        hp=np.array([nodes[i] for i in e.connectivity[:8]],float); host=hex_volume(hp); l0=l90=0.
        hmin,hmax=hp.min(0),hp.max(0)
        for f, fmin, fmax in fiber_bbox:
            if np.any(fmax < hmin - 1e-9) or np.any(fmin > hmax + 1e-9): continue
            L=_polyline_clip_len(f.points, hp, hmin, hmax)
            if L == 0.0: continue
            if f.direction=="t0": l0+=L
            else: l90+=L
        fv=(l0+l90)*area; out.append((label,host,fv,fv/host if host else 0.,l0,l90))
        if progress and (index == total_hosts or index % max(1, total_hosts // 100) == 0):
            progress(index, total_hosts)
    return out


def fiber_volume_rows_precise(elements, nodes, fibers, diameter, n_along=7, progress=None):
    """Per-host fiber volume using true cross-section-weighted cylinder/hex
    intersection (`swept_cylinder_hex_volume`) instead of `fiber_volume_rows`'s
    centerline-length x full-cross-section-area approximation. Slower (each
    candidate segment/host pair costs ~n_along*24 point-in-hex evaluations
    instead of ~1), but accounts for a fiber running near a host face/edge/
    corner -- where the length-based method silently assigns the *whole* disk
    to one host even though part of it geometrically belongs to a neighbor.
    Same row layout as `fiber_volume_rows` (t0/t90 columns hold volume, not
    length, here -- since a fiber's in-host cross-section fraction can vary
    along its own length, a single "length" number is no longer meaningful).
    Radius is bumped by a small margin when bbox-pruning so cross-sections
    whose *disk* pokes into a host, even though the centerline itself does
    not, are not missed. For each candidate segment, the *centerline*'s
    clipped range against this host (from `clip_segment_hex_bounds`, padded by
    roughly one fiber diameter in parametric terms) is used to restrict where
    the `n_along`-station quadrature actually looks -- important because a
    single fiber segment is very often much longer than any one host (the
    common flat-plate case), and spending all n_along stations on the *whole*
    segment for every host it merely touches wastes almost all of them and
    reintroduces the along-axis alignment error `swept_cylinder_hex_volume`
    documents. When the centerline never enters this host at all (only the
    disk might, near a face), the full segment is scanned as a fallback.
    """
    radius = diameter / 2
    out = []
    fiber_bbox = [(f, f.points.min(0) - radius, f.points.max(0) + radius) for f in fibers]
    total_hosts = len(elements)
    for index, (label, e) in enumerate(elements.items(), start=1):
        hp = np.array([nodes[i] for i in e.connectivity[:8]], float)
        host = hex_volume(hp); v0 = v90 = 0.0
        hmin, hmax = hp.min(0), hp.max(0)
        for f, fmin, fmax in fiber_bbox:
            if np.any(fmax < hmin - 1e-9) or np.any(fmin > hmax + 1e-9): continue
            pts = f.points
            V = 0.0
            for a, b in zip(pts[:-1], pts[1:]):
                if np.any(np.maximum(a, b) + radius < hmin - 1e-9) or np.any(np.minimum(a, b) - radius > hmax + 1e-9):
                    continue
                seg_len = np.linalg.norm(b - a)
                margin = min(0.5, 2 * radius / seg_len) if seg_len > 1e-12 else 0.5
                bounds = clip_segment_hex_bounds(a, b, hp)
                t_range = (max(0.0, bounds[0] - margin), min(1.0, bounds[1] + margin)) if bounds else None
                V += swept_cylinder_hex_volume(a, b, radius, hp, n_along=n_along, t_range=t_range)
            if V == 0.0: continue
            if f.direction == "t0": v0 += V
            else: v90 += V
        fv = v0 + v90
        out.append((label, host, fv, fv / host if host else 0., v0, v90))
        if progress and (index == total_hosts or index % max(1, total_hosts // 100) == 0):
            progress(index, total_hosts)
    return out
