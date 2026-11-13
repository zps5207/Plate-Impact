from __future__ import annotations
import numpy as np
from .layup import orthogonal_directions
from .fibers import Fiber, _layer_positions
from .director import radial_direction


def _angular_span(angles):
    """Given angles in radians (any range), return (theta_min, theta_max, full_circle).
    Detects the largest circular gap between samples; if it's small, the ring is a
    full 360 degree sweep, otherwise it's the panel spanning the *other* way
    around from the gap (so partial cylinders/panels are handled without the user
    having to state an angular extent)."""
    a = np.sort(np.unique(np.round(np.mod(np.asarray(angles, float), 2 * np.pi), 9)))
    if len(a) < 3:
        return 0.0, 2 * np.pi, True
    gaps = np.diff(np.concatenate([a, [a[0] + 2 * np.pi]]))
    k = int(np.argmax(gaps))
    # a full ring's gaps are all ~uniform; a real panel edge leaves one gap much
    # larger than the rest (comparing to the *median*, not an absolute angle,
    # so this works for both coarse and fine angular sampling).
    if gaps[k] < 3 * np.median(gaps):
        return 0.0, 2 * np.pi, True
    start = a[(k + 1) % len(a)]
    end = a[k] + 2 * np.pi if k == len(a) - 1 else a[k]
    # walk the long way around, away from the gap
    return float(start), float(start + (2 * np.pi - gaps[k])), False


def _arc_points(center, e1, e2, r, th0, th1, seg_len):
    n = max(2, int(np.ceil(abs(th1 - th0) * r / max(seg_len, 1e-9))) + 1)
    th = np.linspace(th0, th1, n)
    return np.array([center + r * (np.cos(t) * e1 + np.sin(t) * e2) for t in th])


def cylindrical_fibers(nodes, diameter, axis_point, axis_dir, gap=0.0, reference=(1, 0, 0)):
    """Embedded fibers for a plate/shell curved about a single axis (a cylinder or
    a panel of one). Two alternating families: axial ("t0", straight, parallel to
    the axis) and hoop ("t90", circular arcs at constant radius). The local
    director (used for beam-element orientation, and equal to the blended
    surface-1/surface-2 normal since both bounding surfaces share this axis) is
    the outward radial direction everywhere -- see embmesh.director."""
    pts = np.asarray(list(nodes.values()), float)
    a = np.asarray(axis_point, float); u = np.asarray(axis_dir, float); u /= np.linalg.norm(u)
    e1, e2 = orthogonal_directions(reference, u)
    rel = pts - a
    z = rel @ u
    rad = rel - np.outer(z, u)
    r = np.linalg.norm(rad, axis=1)
    theta = np.arctan2(rad @ e2, rad @ e1)
    r_lo, r_hi = float(r.min()), float(r.max())
    z_lo, z_hi = float(z.min()), float(z.max())
    th0, th1, full = _angular_span(theta)
    pitch = diameter + gap
    fibers = []; label = 1
    for k, rk in enumerate(_layer_positions(r_lo, r_hi, diameter, gap)):
        circumference = rk * (2 * np.pi if full else (th1 - th0))
        if k % 2 == 0:  # axial family
            n_fib = max(1, int(np.floor(circumference / pitch + 1e-9)) + (0 if full else 1))
            if n_fib < 1: continue
            angles = (th0 + (np.arange(n_fib) + 0.5) * (2 * np.pi / n_fib if full else (th1 - th0) / n_fib)) \
                if full else th0 + (np.arange(n_fib) + 0.5) * (th1 - th0) / n_fib
            for th in angles:
                c = a + rk * (np.cos(th) * e1 + np.sin(th) * e2)
                p0, p1 = c + z_lo * u, c + z_hi * u
                up = radial_direction(c, axis_point=a, axis_dir=u)   # the director field, at this fiber's location
                fibers.append(Fiber(label, np.array([p0, p1]), k, "t0", {"up": up})); label += 1
        else:           # hoop family
            for zj in _layer_positions(z_lo, z_hi, diameter, gap):
                c = a + zj * u
                th_hi = th0 + 2 * np.pi if full else th1
                poly = _arc_points(c, e1, e2, rk, th0, th_hi, pitch)
                mids = (poly[:-1] + poly[1:]) / 2
                up = np.array([radial_direction(m, axis_point=a, axis_dir=u) for m in mids])
                fibers.append(Fiber(label, poly, k, "t90", {"up": up})); label += 1
    return fibers, dict(r_inner=r_lo, r_outer=r_hi, z_min=z_lo, z_max=z_hi, full_circle=full)


def spherical_fibers(nodes, diameter, center, pole_axis, gap=0.0, reference=(1, 0, 0)):
    """Embedded fibers for a spherical(-panel) shell. Two alternating families:
    meridian ("t0", constant longitude, arcs of constant colatitude range) and
    latitude ("t90", constant colatitude, circular arcs). `pole_axis` sets the
    parametrization's pole (the "axis the user suspects is most representative",
    per the mesher's director-field protocol); both bounding surfaces share the
    sphere's center, so the local director is simply the outward radial direction."""
    pts = np.asarray(list(nodes.values()), float)
    c = np.asarray(center, float); u = np.asarray(pole_axis, float); u /= np.linalg.norm(u)
    e1, e2 = orthogonal_directions(reference, u)
    rel = pts - c
    r = np.linalg.norm(rel, axis=1)
    cosphi = np.clip((rel @ u) / np.maximum(r, 1e-12), -1, 1)
    phi = np.arccos(cosphi)                    # colatitude from pole, 0..pi
    tang = rel - np.outer(rel @ u, u)
    theta = np.arctan2(tang @ e2, tang @ e1)    # longitude
    r_lo, r_hi = float(r.min()), float(r.max())
    phi_lo, phi_hi = float(np.clip(phi.min(), 1e-4, np.pi)), float(np.clip(phi.max(), 1e-4, np.pi - 1e-4))
    th0, th1, full = _angular_span(theta)
    pitch = diameter + gap
    fibers = []; label = 1

    def radial_at(theta_v, phi_v, r_v):
        return r_v * (np.sin(phi_v) * (np.cos(theta_v) * e1 + np.sin(theta_v) * e2) + np.cos(phi_v) * u)

    for k, rk in enumerate(_layer_positions(r_lo, r_hi, diameter, gap)):
        meridian_len = rk * (phi_hi - phi_lo)
        if k % 2 == 0:  # meridian family (constant longitude)
            circumference_mid = rk * np.sin((phi_lo + phi_hi) / 2) * (2 * np.pi if full else (th1 - th0))
            n_fib = max(1, int(np.floor(circumference_mid / pitch + 1e-9)) + (0 if full else 1))
            angles = (th0 + (np.arange(n_fib) + 0.5) * (2 * np.pi / n_fib)) if full else \
                     th0 + (np.arange(n_fib) + 0.5) * (th1 - th0) / n_fib
            for th in angles:
                n_pts = max(2, int(np.ceil(meridian_len / pitch)) + 1)
                phis = np.linspace(phi_lo, phi_hi, n_pts)
                poly = np.array([c + radial_at(th, p, rk) for p in phis])
                mids = (poly[:-1] + poly[1:]) / 2
                up = np.array([radial_direction(m, center=c) for m in mids])   # the director field, at each segment
                fibers.append(Fiber(label, poly, k, "t0", {"up": up})); label += 1
        else:           # latitude family (constant colatitude)
            for phij in _layer_positions(phi_lo, phi_hi, diameter, gap):
                ring_r = rk * np.sin(phij)
                if ring_r < diameter / 2: continue
                th_hi = th0 + 2 * np.pi if full else th1
                n_pts = max(2, int(np.ceil(abs(th_hi - th0) * ring_r / pitch)) + 1)
                ths = np.linspace(th0, th_hi, n_pts)
                poly = np.array([c + radial_at(t, phij, rk) for t in ths])
                mids = (poly[:-1] + poly[1:]) / 2
                up = np.array([radial_direction(m, center=c) for m in mids])
                fibers.append(Fiber(label, poly, k, "t90", {"up": up})); label += 1
    return fibers, dict(r_inner=r_lo, r_outer=r_hi, phi_min=phi_lo, phi_max=phi_hi, full_circle=full)


def concentric_shell_fibers(radius_front, radius_back, axial_length, diameter, gap=0., count=32):
    """Kept for backward compatibility with earlier direct-parameter callers; prefer
    `cylindrical_fibers` (host-mesh-driven, with a real alternating 0/90 layup)."""
    axis_point = np.array([0., 0., 0.]); axis_dir = np.array([0., 0., 1.])
    nn = {}
    idx = 1
    for r in (radius_front, radius_back):
        for th in np.linspace(0, 2 * np.pi, count, endpoint=False):
            for z in (0.0, axial_length):
                nn[idx] = np.array([r * np.cos(th), r * np.sin(th), z]); idx += 1
    fibers, meta = cylindrical_fibers(nn, diameter, axis_point, axis_dir, gap=gap)
    radii = np.array(sorted({round(np.linalg.norm(f.points[0][:2]), 9) for f in fibers}))
    return fibers, radii
