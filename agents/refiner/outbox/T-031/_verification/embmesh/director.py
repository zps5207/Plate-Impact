"""Through-thickness director field for embedded-fiber layup.

The interior orthogonal (through-thickness) direction at any point between a
plate's two bounding surfaces is a distance-weighted blend of the two
surfaces' own local orthogonal (normal) vectors: 100% surface-1's vector at
surface-1, 100% surface-2's vector at surface-2, and a 50/50 blend exactly
at the midpoint between them, varying smoothly for points in between.

For a flat plate (or a box/cube with parallel front and back faces) the two
surface vectors are identical everywhere (the single global "fiber
orienting axis" the user picks or the mesher auto-detects), so the blend is
degenerate and reduces to that constant axis. For a plate with a single-axis
(cylindrical) or spherical curvature, both surfaces share the same
axis/center, so the blend reduces to the analytic radial director -- see
`radial_director`. The blend itself (`blend_director`) is written generally
so it also applies to a plate whose two surfaces are not simple concentric
offsets.
"""
from __future__ import annotations
import numpy as np


def slerp(v1, v2, t):
    """Spherical linear interpolation between two unit vectors at t in [0, 1]."""
    v1 = np.asarray(v1, float); v2 = np.asarray(v2, float)
    v1 = v1 / max(np.linalg.norm(v1), 1e-15)
    v2 = v2 / max(np.linalg.norm(v2), 1e-15)
    dot = float(np.clip(v1 @ v2, -1.0, 1.0))
    theta = np.arccos(dot)
    if theta < 1e-8:
        out = (1 - t) * v1 + t * v2
    else:
        out = (np.sin((1 - t) * theta) * v1 + np.sin(t * theta) * v2) / np.sin(theta)
    n = np.linalg.norm(out)
    return out / n if n > 1e-15 else v1


def blend_director(surface1_normal, surface2_normal, t):
    """The interior director at through-thickness fraction t (0 at surface 1, 1 at
    surface 2): 100% surface1_normal at t=0, 100% surface2_normal at t=1, an
    even (50/50) blend at t=0.5, smoothly varying in between."""
    return slerp(surface1_normal, surface2_normal, float(np.clip(t, 0.0, 1.0)))


def radial_direction(point, axis_point=None, axis_dir=None, center=None):
    """Outward radial direction at `point`, for either a single-axis (cylindrical:
    pass axis_point + axis_dir) or spherical (pass center) curved surface. Both
    of a curved plate's bounding surfaces share this same axis/center, so this
    already *is* `blend_director` for that case (surface-1 and surface-2 normals
    are identical), for any through-thickness fraction t."""
    p = np.asarray(point, float)
    if center is not None:
        d = p - np.asarray(center, float)
    else:
        a = np.asarray(axis_point, float); u = np.asarray(axis_dir, float)
        u = u / np.linalg.norm(u)
        d = (p - a) - ((p - a) @ u) * u
    n = np.linalg.norm(d)
    return d / n if n > 1e-12 else d


def thickness_fraction(layer_index, num_layers):
    """t in [0, 1] for layer `layer_index` of `num_layers` stacked layers (0 =
    innermost/surface-1 side, 1 = outermost/surface-2 side), matching the
    user's rule: even spacing, 50/50 exactly at the middle layer of an odd count."""
    if num_layers <= 1:
        return 0.5
    return layer_index / (num_layers - 1)
