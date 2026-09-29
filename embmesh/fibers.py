from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np
from .layup import orthogonal_directions
from .geometry import clip_segment_hex_bounds

_AXES = {"x": np.array([1., 0, 0]), "y": np.array([0., 1, 0]), "z": np.array([0., 0, 1])}


@dataclass
class Fiber:
    label: int
    points: np.ndarray          # (N, 3), N >= 2: a polyline (2 points for a straight fiber)
    layer: int
    direction: str
    curvature_data: dict = field(default_factory=dict)


def _parse_axis(spec):
    if spec is None:
        return None
    if isinstance(spec, str):
        s = spec.strip().lower()
        if s in _AXES:
            return _AXES[s].copy()
        v = np.array([float(x) for x in spec.split(",")], float)
    else:
        v = np.asarray(spec, float)
    n = np.linalg.norm(v)
    if n < 1e-12:
        raise ValueError(f"thickness axis vector is degenerate: {spec!r}")
    return v / n


def pick_thickness_axis(nodes, explicit=None):
    """Deterministic thickness-axis selection (BUG-004 fix: the old SVD-based
    auto-detection was numerically unstable -- non-deterministic tie-breaking
    for near-cubic hosts, and it fed a downstream fallback in `orthogonal_directions`
    that could degenerate to a zero vector). `explicit` may be 'x'/'y'/'z' or a raw
    "dx,dy,dz" vector, and always wins. Otherwise the bounding-box's shortest
    extent is used, so a clearly-thin plate is unambiguous; a cube or
    near-cubic host (all extents close) has no single "correct" thickness axis,
    so we deterministically default to Z, matching the flat-plate convention
    ("a flat plate in the x-y plane uses z") -- the user should still pass
    --thickness-axis explicitly for a cube meant to be thin along a different axis."""
    axis = _parse_axis(explicit)
    if axis is not None:
        return axis
    pts = np.asarray(list(nodes.values()) if isinstance(nodes, dict) else nodes, float)
    extent = pts.max(0) - pts.min(0)
    order = np.argsort(extent, kind="stable")
    if extent[order[0]] > 1e-12 and extent[order[1]] / max(extent[order[0]], 1e-12) < 1.05:
        return np.array([0., 0., 1.])   # ambiguous (cube-like): deterministic default, not a guess-and-crash
    return np.eye(3)[order[0]]


def _layer_positions(lo, hi, diameter, gap, eps=1e-9):
    """Centerline offsets of every layer that fits fully within [lo, hi], evenly
    spaced at pitch = diameter+gap, first/last layer inset by diameter/2 (BUG-007
    fencepost fix: closed form, no over-permissive arange bound)."""
    pitch = diameter + gap
    span = hi - lo
    if span < diameter - eps:
        return []
    n = int(np.floor((span - diameter) / pitch + eps)) + 1
    return [lo + diameter / 2 + k * pitch for k in range(max(n, 0))]


def _host_bounds(elems, nodes):
    """Pre-compute each host hex's node array and axis-aligned bbox once, reused
    for every fiber row's boundary clip below."""
    out = []
    for e in elems.values():
        hp = np.asarray([nodes[i] for i in e.connectivity[:8]], float)
        out.append((hp, hp.min(0), hp.max(0)))
    return out


def _row_coverage(a, b, host_bounds):
    """Parametric sub-intervals of segment a->b (each a (t_lo, t_hi) in [0, 1])
    that actually lie inside the union of host hexes, merging touching/overlapping
    hosts into contiguous runs. This is what makes a fiber row follow the host
    mesh's real (possibly curved/irregular) in-plane boundary instead of the
    bounding box of the whole node cloud -- a rectangular candidate row over a
    round or notched plate is trimmed down to just the part that actually sits
    over host material (BUG-009: fibers overshooting a non-rectangular plate)."""
    a = np.asarray(a, float); b = np.asarray(b, float)
    lo_bb, hi_bb = np.minimum(a, b), np.maximum(a, b)
    intervals = []
    for hp, hmin, hmax in host_bounds:
        if np.any(hi_bb < hmin - 1e-9) or np.any(lo_bb > hmax + 1e-9):
            continue
        bounds = clip_segment_hex_bounds(a, b, hp)
        if bounds is not None:
            intervals.append(bounds)
    if not intervals:
        return []
    intervals.sort()
    merged = [list(intervals[0])]
    for t_lo, t_hi in intervals[1:]:
        if t_lo <= merged[-1][1] + 1e-7:
            merged[-1][1] = max(merged[-1][1], t_hi)
        else:
            merged.append([t_lo, t_hi])
    return [tuple(m) for m in merged]


def flat_disc_fibers(elems, nodes, diameter, thickness_axis=None, gap=0.0, reference=(1, 0, 0), end_inset=0.0):
    """Straight 0/90 fiber layup for a flat plate, box, or cube (parallel front/back
    faces). `thickness_axis` selects/overrides the through-thickness direction --
    see `pick_thickness_axis`. Each candidate row is clipped to the actual host
    element footprint (`elems`), not just the node cloud's bounding box, so a
    non-rectangular in-plane boundary (round, notched, L-shaped, ...) is respected
    -- see `_row_coverage`."""
    pts = np.asarray(list(nodes.values()), float)
    axis = pick_thickness_axis(nodes, thickness_axis)
    center = pts.mean(0)
    t0, t1 = orthogonal_directions(reference, axis)
    w = pts @ axis
    lo, hi = w.min(), w.max()
    host_bounds = _host_bounds(elems, nodes)
    fibers = []
    label = 1
    for k, z in enumerate(_layer_positions(lo, hi, diameter, gap)):
        j = k % 2
        d, perp = (t0, t1) if j == 0 else (t1, t0)
        for s in _layer_positions((pts @ perp).min(), (pts @ perp).max(), diameter, gap):
            lo2 = (pts @ d).min() - center @ d
            hi2 = (pts @ d).max() - center @ d
            if hi2 <= lo2:
                continue
            base = center + (z - center @ axis) * axis + (s - center @ perp) * perp
            a_full = base + lo2 * d
            b_full = base + hi2 * d
            span = hi2 - lo2
            for t_lo, t_hi in _row_coverage(a_full, b_full, host_bounds):
                # end_inset (default 0) is an optional caller-requested margin,
                # applied on top of the real host-footprint clip above -- e.g. a
                # fully-packed lattice that exactly tiles a rectangular host (as
                # in the flat-plate acceptance test) is expected to run flush to
                # the host boundary with no inset at all.
                lo3 = lo2 + t_lo * span + end_inset
                hi3 = lo2 + t_hi * span - end_inset
                if hi3 <= lo3:
                    continue
                fibers.append(Fiber(label, np.array([base + lo3 * d, base + hi3 * d]), k, "t0" if j == 0 else "t90"))
                label += 1
    return fibers
