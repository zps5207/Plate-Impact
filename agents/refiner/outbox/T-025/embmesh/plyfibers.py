"""Per-ply fiber generation for plywise meshing.

Generates one unidirectional fiber layer per ply centered on the ply's mid-surface,
at a per-ply angle. Emits one fiber Part per distinct angle, instanced once per ply
with identical translations to the host plies, and embeds each ply's fibers strictly
within its own host elements.
"""
from __future__ import annotations

from dataclasses import dataclass
import warnings
import numpy as np
from pathlib import Path
from typing import Sequence

from .fibers import Fiber, _layer_positions, _parse_axis, pick_thickness_axis
from .layup import orthogonal_directions
from .geometry import hex_volume

_SIGNS = np.array([[-1,-1,1],[-1,1,1],[1,1,1],[1,-1,1],[-1,-1,-1],[-1,1,-1],[1,1,-1],[1,-1,-1]], float)
_AXIS_FACES = {
    0: ((4, 0, 1, 5), (7, 3, 2, 6)),  # xi: -1 and +1
    1: ((4, 7, 3, 0), (5, 6, 2, 1)),  # eta: -1 and +1
    2: ((4, 5, 6, 7), (0, 1, 2, 3)),  # zeta: -1 and +1
}


@dataclass
class PlyInstanceInfo:
    """Interface defining a host ply instance for fiber placement and embedding."""
    name: str
    translation: np.ndarray  # shape (3,)
    rotation_axis: np.ndarray | None = None
    rotation_angle: float = 0.0
    rotation_origin: np.ndarray | None = None

    def __post_init__(self):
        self.translation = np.asarray(self.translation, float)
        if self.rotation_axis is not None:
            self.rotation_axis = np.asarray(self.rotation_axis, float)
        if self.rotation_origin is not None:
            self.rotation_origin = np.asarray(self.rotation_origin, float)


def expand_layup(angles: Sequence[float], plies: int, symmetric: bool = False, repeat: int = 1) -> list[float]:
    """Expand layup angle sequence and validate against requested ply count.

    Parameters:
        angles: sequence of ply angles (in degrees), e.g. [0, 90, 45, -45]
        plies: target total number of plies (positive integer)
        symmetric: if True, append reverse sequence (e.g. [0, 90] -> [0, 90, 90, 0])
        repeat: repeat factor (positive integer)

    Returns:
        list of floats of length `plies`
    """
    if repeat < 1 or int(repeat) != repeat:
        raise ValueError(f"repeat must be a positive integer, got {repeat}")
    base = [float(a) for a in angles] * int(repeat)
    if symmetric:
        full = base + base[::-1]
    else:
        full = base
    if len(full) != plies:
        raise ValueError(
            f"expanded layup has {len(full)} plies ({full}), does not match requested ply count {plies}"
        )
    return full


def _oriented_hex_faces(h, axis, conn=None):
    """Return (bottom_pts, top_pts, bottom_ids, top_ids) for one hex along stack axis."""
    best_ax = None
    best_comp = -1.0
    best_lo, best_hi = None, None
    for ax in (0, 1, 2):
        lo_idx, hi_idx = _AXIS_FACES[ax]
        vec = h[list(hi_idx)].mean(0) - h[list(lo_idx)].mean(0)
        comp = abs(float(np.dot(vec, axis)))
        if comp > best_comp:
            best_comp = comp
            best_ax = ax
            best_lo, best_hi = lo_idx, hi_idx

    lo_pts = h[list(best_lo)]
    hi_pts = h[list(best_hi)]
    lo_ids = tuple(conn[i] for i in best_lo) if conn is not None else tuple(best_lo)
    hi_ids = tuple(conn[i] for i in best_hi) if conn is not None else tuple(best_hi)

    if np.dot(hi_pts.mean(0) - lo_pts.mean(0), axis) < 0:
        return hi_pts, lo_pts, hi_ids, lo_ids
    return lo_pts, hi_pts, lo_ids, hi_ids


def _resample_by_arclength(path, target_length):
    path = np.asarray(path, float)
    lengths = np.linalg.norm(np.diff(path, axis=0), axis=1)
    keep = np.r_[True, lengths > 1e-12]
    path = path[keep]
    if len(path) < 2:
        return None, 0., 0.
    lengths = np.linalg.norm(np.diff(path, axis=0), axis=1)
    cum = np.r_[0., np.cumsum(lengths)]
    total = float(cum[-1])
    n = max(1, round(total / target_length))
    stations = np.linspace(0., total, n + 1)
    def sample(st):
        indices = np.clip(np.searchsorted(cum, st, side='right') - 1, 0, len(lengths) - 1)
        weights = ((st - cum[indices]) / lengths[indices])[:, None]
        return path[indices] + weights * (path[indices + 1] - path[indices])
    points = sample(stations)
    for _ in range(12):
        chords = np.linalg.norm(np.diff(points, axis=0), axis=1)
        if (chords.max() - chords.min()) / np.median(chords) <= 1e-10:
            break
        intervals = np.diff(stations) + (chords.mean() - chords)
        if np.any(intervals <= 0):
            raise ValueError('ply fibers: equal-chord correction produced a nonpositive interval')
        stations = np.r_[0., np.cumsum(intervals)]
        stations[-1] = total
        points = sample(stations)
    points[0], points[-1] = path[0], path[-1]
    arc_spread = float(np.ptp(np.diff(stations)) / np.mean(np.diff(stations))) if n > 1 else 0.
    return points, total, arc_spread


def ply_fibers(ply_part_hexes, nodes, angle, diameter, gap=0.0, reference=(1, 0, 0),
               end_inset=0.0, thickness_axis=None, ply_index=0, return_meta=False):
    """Generate unidirectional fibers on the mid-surface of a single-hex-thick ply Part.

    Parameters:
        ply_part_hexes: dict of Element or iterable of Element
        nodes: dict of node_id -> coordinates array([x, y, z])
        angle: fiber angle in degrees relative to the 0-degree reference vector
        diameter: fiber cross-section diameter
        gap: spacing between adjacent fiber boundaries (pitch = diameter + gap)
        reference: 0-degree reference vector in assembly frame
        end_inset: deprecated; lateral endpoints always reach the host boundary
        thickness_axis: stack axis override (optional)
        ply_index: 0-based ply index
        return_meta: whether to return metadata dict

    Returns:
        list[Fiber] (and meta dict if return_meta=True)
    """
    if isinstance(ply_part_hexes, dict):
        elems = list(ply_part_hexes.values())
    else:
        elems = list(ply_part_hexes)

    coords = np.asarray(list(nodes.values()), float)
    lookup = {label: i for i, label in enumerate(nodes)}
    conns = np.asarray([e.connectivity[:8] for e in elems], int)
    hexes = coords[np.vectorize(lookup.__getitem__)(conns)]

    target_length = float(np.cbrt(np.median([hex_volume(h) for h in hexes])))

    axis = _parse_axis(thickness_axis)
    if axis is None:
        axis = pick_thickness_axis(nodes)

    t0, t1 = orthogonal_directions(reference, axis)

    # Orient hexes along stack axis
    face0_list = []
    face1_list = []
    face0_ids_list = []
    spans = []
    for h, conn in zip(hexes, conns):
        bot_p, top_p, bot_id, top_id = _oriented_hex_faces(h, axis, conn)
        face0_list.append(bot_p)
        face1_list.append(top_p)
        face0_ids_list.append(bot_id)
        spans.append(abs(float(np.dot(top_p.mean(0) - bot_p.mean(0), axis))))

    face0 = np.asarray(face0_list)
    face1 = np.asarray(face1_list)
    face0_ids = np.asarray(face0_ids_list)

    ply_thickness = float(np.median(spans))
    if ply_thickness < 1e-12:
        raise ValueError("ply fibers: degenerate ply thickness")

    if diameter > ply_thickness + 1e-12:
        raise ValueError(
            f"fiber diameter {diameter:.6g} m exceeds ply thickness {ply_thickness:.6g} m"
        )
    if diameter > 0.8 * ply_thickness:
        warnings.warn(
            f"fiber diameter {diameter:.6g} m exceeds 0.8x ply thickness {ply_thickness:.6g} m",
            UserWarning,
            stacklevel=2,
        )

    # Mid-surface quads
    mid_quads = (face0 + face1) / 2.0

    # In-plane rotation by ply angle
    rad = np.deg2rad(angle)
    e_along = np.cos(rad) * t0 + np.sin(rad) * t1
    e_across = -np.sin(rad) * t0 + np.cos(rad) * t1

    # Project mid-surface quads into (u_along, s_across, z_axis)
    u_along = np.dot(mid_quads, e_along)
    s_across = np.dot(mid_quads, e_across)
    z_axis = np.dot(mid_quads, axis)
    q_proj = np.stack([u_along, s_across, z_axis], axis=2)

    s_min = float(s_across.min())
    s_max = float(s_across.max())
    fibers = []
    label = 1

    for s in _layer_positions(s_min, s_max, diameter, gap):
        a_quad = q_proj
        b_quad = np.roll(q_proj, -1, axis=1)
        cross = ((a_quad[:, :, 1] <= s) & (s < b_quad[:, :, 1])) | (
            (b_quad[:, :, 1] <= s) & (s < a_quad[:, :, 1])
        )
        valid = np.where(cross.sum(axis=1) == 2)[0]
        if len(valid) == 0:
            continue
        frac = np.divide(
            s - a_quad[:, :, 1],
            b_quad[:, :, 1] - a_quad[:, :, 1],
            out=np.zeros_like(a_quad[:, :, 1]),
            where=np.abs(b_quad[:, :, 1] - a_quad[:, :, 1]) > 1e-14,
        )
        uu = a_quad[:, :, 0] + frac * (b_quad[:, :, 0] - a_quad[:, :, 0])
        zz = a_quad[:, :, 2] + frac * (b_quad[:, :, 2] - a_quad[:, :, 2])
        intervals = []
        for ix in valid:
            u_pts = uu[ix, cross[ix]]
            z_pts = zz[ix, cross[ix]]
            order = np.argsort(u_pts)
            if u_pts[order[1]] - u_pts[order[0]] > 1e-12:
                intervals.append(
                    (float(u_pts[order[0]]), float(u_pts[order[1]]),
                     float(z_pts[order[0]]), float(z_pts[order[1]]), int(ix))
                )
        intervals.sort()
        groups = []
        group = []
        right_bound = -np.inf
        for item in intervals:
            if group and item[0] > right_bound + 2e-8:
                groups.append(group)
                group = []
            group.append(item)
            right_bound = max(right_bound, item[1])
        if group:
            groups.append(group)

        for group in groups:
            left, right = group[0][0], max(row[1] for row in group)
            if right <= left:
                continue
            vertices = []
            for u0, u1, z0, z1, eid in group:
                v0 = max(left, u0)
                v1 = min(right, u1)
                if v1 - v0 <= 1e-11:
                    continue
                def point(u_val):
                    h_val = z0 + (z1 - z0) * (u_val - u0) / (u1 - u0)
                    return u_val * e_along + s * e_across + h_val * axis
                p0 = point(v0)
                p1 = point(v1)
                if vertices and np.linalg.norm(p0 - vertices[-1]) > 2e-7:
                    if len(vertices) > 1:
                        pts, total, arc_spread = _resample_by_arclength(vertices, target_length)
                        if pts is not None:
                            fibers.append(
                                Fiber(label, pts, ply_index, f"angle_{angle:.4g}",
                                      {"geometric_path_length_m": total,
                                       "arc_interval_spread_relative": arc_spread,
                                       "angle_deg": float(angle)})
                            )
                            label += 1
                    vertices = []
                if not vertices:
                    vertices.append(p0)
                vertices.append(p1)
            if len(vertices) > 1:
                pts, total, arc_spread = _resample_by_arclength(vertices, target_length)
                if pts is not None:
                    fibers.append(
                        Fiber(label, pts, ply_index, f"angle_{angle:.4g}",
                              {"geometric_path_length_m": total,
                               "arc_interval_spread_relative": arc_spread,
                               "angle_deg": float(angle)})
                    )
                    label += 1

    short_runs = int(sum(f.curvature_data.get("geometric_path_length_m", 0.0) < target_length / 2 for f in fibers))
    all_lengths = [np.linalg.norm(np.diff(f.points, axis=0), axis=1) for f in fibers]
    flat_lengths = np.concatenate(all_lengths) if all_lengths else np.empty(0)
    meta = dict(
        ply_index=ply_index,
        angle_deg=float(angle),
        fiber_count=len(fibers),
        fiber_segments=len(flat_lengths),
        ply_thickness_m=ply_thickness,
        target_segment_length_m=target_length,
        total_fiber_length_m=float(flat_lengths.sum()) if len(flat_lengths) else 0.0,
        shortest_segment_m=float(flat_lengths.min()) if len(flat_lengths) else None,
        median_segment_m=float(np.median(flat_lengths)) if len(flat_lengths) else None,
        longest_segment_m=float(flat_lengths.max()) if len(flat_lengths) else None,
        segment_length_over_target_min=float(flat_lengths.min() / target_length) if len(flat_lengths) else None,
        segment_length_over_target_median=float(np.median(flat_lengths) / target_length) if len(flat_lengths) else None,
        segment_length_over_target_max=float(flat_lengths.max() / target_length) if len(flat_lengths) else None,
        short_fiber_run_count=short_runs,
    )
    return (fibers, meta) if return_meta else fibers


def format_angle_name(angle: float) -> str:
    """Return clean identifier for angle part name, e.g. '0', '90', '45', '-45'."""
    val = float(angle)
    if val.is_integer():
        return str(int(val))
    return f"{val:.4g}".replace('.', '_')


def emit_plyfibers_deck(
    ply_instances: Sequence[PlyInstanceInfo | tuple[str, Sequence[float]]],
    fibers_by_angle: dict[float, list[Fiber]],
    ply_angles: Sequence[float],
    diameter: float,
    fiber_material: str = "Fiber",
    fiber_type: str = "truss",
    base_node_offset: int = 100000,
    base_element_offset: int = 100000,
    offset_step: int = 100000,
) -> tuple[list[str], list[str], list[str]]:
    """Emit fiber Parts, Instances, and Embedded Element constraints.

    Parameters:
        ply_instances: sequence of PlyInstanceInfo or (name, translation) tuples
        fibers_by_angle: mapping of angle -> list[Fiber] generated in ply frame
        ply_angles: per-ply angle sequence
        diameter: fiber diameter
        fiber_material: name of material defined in deck
        fiber_type: 'truss' (T3D2) or 'beam' (B31)
        base_node_offset: starting node ID for first fiber Part
        base_element_offset: starting element ID for first fiber Part
        offset_step: ID offset step between distinct angle Parts

    Returns:
        (parts_lines, instances_lines, embedding_lines)
    """
    normalized_instances: list[PlyInstanceInfo] = []
    for item in ply_instances:
        if isinstance(item, PlyInstanceInfo):
            normalized_instances.append(item)
        else:
            name, trans = item
            normalized_instances.append(PlyInstanceInfo(name, np.asarray(trans, float)))

    if len(normalized_instances) != len(ply_angles):
        raise ValueError(
            f"number of ply instances ({len(normalized_instances)}) does not match ply angles ({len(ply_angles)})"
        )

    typ = "T3D2" if fiber_type == "truss" else "B31"
    area = float(np.pi * diameter ** 2 / 4.0)

    distinct_angles = sorted(set(ply_angles))
    parts_lines: list[str] = []

    # One Part per distinct angle
    for i, ang in enumerate(distinct_angles):
        fibers = fibers_by_angle[ang]
        ang_str = format_angle_name(ang)
        part_name = f"Fibers-{ang_str}"
        node_off = base_node_offset + i * offset_step
        elem_off = base_element_offset + i * offset_step

        node_lines = [f"*Node, nset=FIBERS_{ang_str}_NODES"]
        elem_lines = [f"*Element, type={typ}, elset=FIBERS"]
        nid = node_off
        eid = elem_off

        for f in fibers:
            pts = np.asarray(f.points, float)
            ids = []
            for p in pts:
                node_lines.append(f"{nid}, {p[0]:.17g}, {p[1]:.17g}, {p[2]:.17g}")
                ids.append(nid)
                nid += 1
            for a, b in zip(ids[:-1], ids[1:]):
                elem_lines.append(f"{eid}, {a}, {b}")
                eid += 1

        sec_lines = [
            f"*Solid Section, elset=FIBERS, material={fiber_material}",
            f"{area:.17g}",
        ]
        parts_lines.extend([f"*Part, name={part_name}"] + node_lines + elem_lines + sec_lines + ["*End Part"])

    instances_lines: list[str] = []
    embedding_lines: list[str] = []

    for k, (ply_inst, ang) in enumerate(zip(normalized_instances, ply_angles), start=1):
        ang_str = format_angle_name(ang)
        part_name = f"Fibers-{ang_str}"
        fiber_inst_name = f"Fibers-Ply-{k}"

        trans_str = ", ".join(f"{v:.17g}" for v in ply_inst.translation)
        inst_block = [
            f"*Instance, name={fiber_inst_name}, part={part_name}",
            trans_str,
        ]
        if ply_inst.rotation_angle:
            axis_end = ply_inst.rotation_origin + ply_inst.rotation_axis
            inst_block.append(
                ", ".join(f"{v:.17g}" for v in [*ply_inst.rotation_origin, *axis_end, ply_inst.rotation_angle])
            )
        inst_block.append("*End Instance")
        instances_lines.extend(inst_block)

        # One *Embedded Element block per ply instance pairing
        emb_block = [
            f"*Embedded Element, host elset={ply_inst.name}.PLY",
            f"{fiber_inst_name}.FIBERS",
        ]
        embedding_lines.extend(emb_block)

    return parts_lines, instances_lines, embedding_lines


def append_plyfibers_to_deck(
    source_deck: str | Path,
    output_deck: str | Path,
    ply_instances: Sequence[PlyInstanceInfo | tuple[str, Sequence[float]]],
    fibers_by_angle: dict[float, list[Fiber]],
    ply_angles: Sequence[float],
    diameter: float,
    fiber_material: str = "Fiber",
    fiber_type: str = "truss",
):
    """Write deck containing ply-wise fibers, instances and embedding constraints."""
    parts_lines, instances_lines, embedding_lines = emit_plyfibers_deck(
        ply_instances, fibers_by_angle, ply_angles, diameter, fiber_material, fiber_type
    )

    source_path = Path(source_deck)
    lines = source_path.read_text().splitlines()

    # Insert Parts before *Assembly
    try:
        ip = min(i for i, l in enumerate(lines) if l.strip().lower().startswith("*assembly"))
        ia = max(i for i, l in enumerate(lines) if l.strip().lower().startswith("*end assembly"))
    except ValueError:
        raise ValueError("source deck has no *Assembly ... *End Assembly block")

    new_lines = lines[:ip] + parts_lines + lines[ip:ia] + instances_lines + embedding_lines + lines[ia:]
    out_path = Path(output_deck)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(new_lines) + "\n")
