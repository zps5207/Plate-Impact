from __future__ import annotations

from pathlib import Path
import numpy as np

# The VTK writer used to be duplicated here; embmesh.hostvtk is the one real
# implementation (kept importable from here too so nothing that imported it
# from this module breaks).
from .hostvtk import HEX_EDGES, write_host_fiber_vtk  # noqa: F401

# Standard Abaqus C3D8 node order (indices into element.connectivity[:8]),
# one CCW-from-outside quad per face -- matches HEX_EDGES above.
_HEX_FACES = ((0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7))


def _boundary_faces(elements):
    """The host mesh's outer-skin quad faces: a face shared by two neighboring
    host hexes is internal and is dropped (it would otherwise be drawn twice,
    doubling the triangle count for no visual benefit and making a translucent
    render of adjacent faces look artificially darker/more opaque where they
    overlap). Faces are matched by their node-label set, so this only relies on
    the host mesh being conforming (shared nodes on shared faces), which is
    already required for a valid Abaqus mesh."""
    counts: dict[frozenset, int] = {}
    face_nodes: dict[frozenset, tuple] = {}
    for element in elements.values():
        conn = element.connectivity[:8]
        for face in _HEX_FACES:
            ids = tuple(conn[i] for i in face)
            key = frozenset(ids)
            counts[key] = counts.get(key, 0) + 1
            face_nodes[key] = ids
    return [face_nodes[k] for k, c in counts.items() if c == 1]


def plot_host_fibers(path, elements, nodes, fibers, fractions=None):
    """Render an interactive, rotatable HTML preview (plotly; the plotly.js
    runtime is embedded in the file, so it opens standalone in any browser with
    no network access needed) of the host mesh and its embedded fibers.

    Unlike the old static-PNG/matplotlib preview, this: (1) uses an equal
    ('data') 3D aspect ratio so the host mesh is never stretched/distorted by
    independent per-axis autoscaling, (2) lets the viewer freely orbit/zoom
    instead of baking in one fixed camera angle, and (3) renders the host
    mesh's outer surface as translucent (so fibers are visible through it) and
    the fibers themselves in opaque red, so the embedding is easy to read.
    `fractions` is accepted for backward compatibility but not used here (the
    host/fiber VTK export is where per-host volume fraction is written).
    """
    import plotly.graph_objects as go

    faces = _boundary_faces(elements)
    idx: dict[int, int] = {}
    pts: list[np.ndarray] = []
    for face in faces:
        for n in face:
            if n not in idx:
                idx[n] = len(pts)
                pts.append(np.asarray(nodes[n], float))
    host_pts = np.asarray(pts, float) if pts else np.zeros((0, 3))
    i_idx, j_idx, k_idx = [], [], []
    for face in faces:
        a, b, c, d = (idx[n] for n in face)
        # two triangles per quad face
        i_idx += [a, a]; j_idx += [b, c]; k_idx += [c, d]

    host_trace = go.Mesh3d(
        x=host_pts[:, 0], y=host_pts[:, 1], z=host_pts[:, 2],
        i=i_idx, j=j_idx, k=k_idx,
        color="lightsteelblue", opacity=0.18, flatshading=True,
        lighting=dict(diffuse=0.6, ambient=0.55, specular=0.05),
        name="host mesh", hoverinfo="skip", showscale=False,
    )

    fiber_x: list = []; fiber_y: list = []; fiber_z: list = []
    for fiber in fibers:
        p = np.asarray(fiber.points, float)
        fiber_x += p[:, 0].tolist() + [None]
        fiber_y += p[:, 1].tolist() + [None]
        fiber_z += p[:, 2].tolist() + [None]
    fiber_trace = go.Scatter3d(
        x=fiber_x, y=fiber_y, z=fiber_z, mode="lines",
        line=dict(color="rgba(200,0,0,0.97)", width=4),
        name="fibers", hoverinfo="skip",
    )

    fiber_pts = (np.concatenate([np.asarray(f.points, float) for f in fibers])
                 if fibers else np.zeros((0, 3)))
    all_pts = np.vstack([host_pts, fiber_pts]) if len(host_pts) or len(fiber_pts) else np.zeros((1, 3))
    lo, hi = all_pts.min(0), all_pts.max(0)
    span = max(float((hi - lo).max()), 1e-9)
    center = (hi + lo) / 2
    half = span / 2 * 1.02  # small margin so geometry isn't flush with the view edge

    fig = go.Figure(data=[host_trace, fiber_trace])
    fig.update_layout(
        title="embmesh host elements and fibers -- drag to rotate, scroll to zoom",
        showlegend=True,
        scene=dict(
            aspectmode="data",  # equal scaling on all three axes -- no more stretched/distorted host mesh
            xaxis=dict(title="X", range=[center[0] - half, center[0] + half]),
            yaxis=dict(title="Y", range=[center[1] - half, center[1] + half]),
            zaxis=dict(title="Z", range=[center[2] - half, center[2] + half]),
        ),
        margin=dict(l=0, r=0, t=40, b=0),
    )
    fig.write_html(str(Path(path)), include_plotlyjs=True, full_html=True)
