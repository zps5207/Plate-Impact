"""Interactive HTML preview of a plywise deck: each ply's outer surface plus its fibers, coloured by angle."""
from __future__ import annotations

from pathlib import Path
import numpy as np

from .geometry import boundary_faces
from .parser import parse_deck

# categorical, colour-blind-safe-ish; one colour per distinct fiber angle
_ANGLE_COLORS = ["#d62728", "#1f77b4", "#2ca02c", "#9467bd", "#ff7f0e", "#17becf", "#8c564b", "#e377c2"]
_PLY_COLORS = ["#c6dbef", "#fdd0a2", "#c7e9c0", "#dadaeb", "#fcbba1", "#d9d9d9"]


def _ply_number(name):
    tail = name.rsplit("-", 1)[-1]
    return int(tail) if tail.isdigit() else 0


def plot_plywise(deck_path, html_path):
    import plotly.graph_objects as go

    deck = parse_deck(deck_path)
    plies = sorted((n for n in deck.instances if n.startswith("Ply-")), key=_ply_number)
    fiber_insts = {_ply_number(n): n for n in deck.instances if n.startswith("Fibers-Ply-")}
    if not plies:
        raise ValueError("deck has no Ply-k instances; was it written by 'embmesh plywise'?")

    traces, all_pts = [], []
    angle_colors = {}
    for k, name in enumerate(plies, start=1):
        part = deck.parts[deck.instances[name].part]
        world = deck.instance_nodes(name)
        # VU1 hosts sit on the same nodes as their ghost C3D8R elements, which would hide every
        # face (each face would appear twice); draw the native elements when both exist
        native = {k: e for k, e in part.elements.items() if e.type.upper().startswith("C3D8")}
        faces = boundary_faces(native or part.elements)
        idx, pts = {}, []
        for face in faces:
            for n in face:
                if n not in idx:
                    idx[n] = len(pts); pts.append(world[n])
        P = np.asarray(pts, float)
        i, j, kk = [], [], []
        for face in faces:
            a, b, c, d = (idx[n] for n in face)
            i += [a, a]; j += [b, c]; kk += [c, d]
        traces.append(go.Mesh3d(x=P[:, 0], y=P[:, 1], z=P[:, 2], i=i, j=j, k=kk,
                                color=_PLY_COLORS[(k - 1) % len(_PLY_COLORS)], opacity=0.22,
                                flatshading=True, name=name, legendgroup=name, hoverinfo="skip"))
        all_pts.append(P)

        fname = fiber_insts.get(k)
        if fname is None:
            continue
        fpart = deck.parts[deck.instances[fname].part]
        fworld = deck.instance_nodes(fname)
        ang = fpart.name.split("Fibers-", 1)[-1]
        color = angle_colors.setdefault(ang, _ANGLE_COLORS[len(angle_colors) % len(_ANGLE_COLORS)])
        x, y, z = [], [], []
        for e in fpart.elements.values():
            for n in e.connectivity[:2]:
                p = fworld[n]; x.append(p[0]); y.append(p[1]); z.append(p[2])
            x.append(None); y.append(None); z.append(None)
        traces.append(go.Scatter3d(x=x, y=y, z=z, mode="lines", line=dict(color=color, width=3),
                                   name=f"{name} fibers ({ang} deg)", legendgroup=name, hoverinfo="skip"))

    allp = np.vstack(all_pts)
    lo, hi = allp.min(0), allp.max(0)
    c, half = (hi + lo) / 2, float((hi - lo).max()) / 2 * 1.02
    fig = go.Figure(data=traces)
    fig.update_layout(
        title="embmesh plywise: plies and per-ply fibers -- drag to rotate, scroll to zoom, click legend to hide a ply",
        scene=dict(aspectmode="data",
                   xaxis=dict(title="X", range=[c[0] - half, c[0] + half]),
                   yaxis=dict(title="Y", range=[c[1] - half, c[1] + half]),
                   zaxis=dict(title="Z", range=[c[2] - half, c[2] + half])),
        margin=dict(l=0, r=0, t=40, b=0))
    Path(html_path).parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(html_path), include_plotlyjs=True, full_html=True)
    return Path(html_path)
