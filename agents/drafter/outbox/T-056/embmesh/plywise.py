"""Split a one-hex-thick plate into translated instances of one ply part."""
from __future__ import annotations

from pathlib import Path
import re

import numpy as np

from .errors import MesherInputError
from .geometry import HEX_FACES
from .fibers import pick_thickness_axis
from .model import Part, Element
from .parser import parse_deck
from .cohesive_materials import cohesive_interaction


class EmbmeshError(MesherInputError):
    """Plywise input cannot be represented as translated congruent plies."""


# Same local coordinates as geometry.hex_volume/inverse_hex, in Abaqus order.
_SIGNS = np.array([[-1, -1, 1], [-1, 1, 1], [1, 1, 1], [1, -1, 1],
                   [-1, -1, -1], [-1, 1, -1], [1, 1, -1], [1, -1, -1]])
_FACE_ID = {frozenset(face): f'S{i}' for i, face in enumerate(HEX_FACES, 1)}


def oriented_faces(points, direction):
    """Return (bottom face id, top face id, bottom/top local-node pairs)."""
    p = np.asarray(points, float)
    # the stack direction decides the pairing; hex_thickness_axis (smallest span) misreads a
    # one-hex-thick plate whose in-plane elements are smaller than the plate thickness
    axis = max(range(3), key=lambda a: abs(np.dot(
        p[_SIGNS[:, a] > 0].mean(0) - p[_SIGNS[:, a] < 0].mean(0), direction)))
    low = np.flatnonzero(_SIGNS[:, axis] < 0)
    high = np.flatnonzero(_SIGNS[:, axis] > 0)
    if np.dot(p[high].mean(0) - p[low].mean(0), direction) < 0:
        low, high = high, low
    pairs = []
    for i in low:
        match = [j for j in high if np.all(_SIGNS[j, np.arange(3) != axis] ==
                                              _SIGNS[i, np.arange(3) != axis])]
        pairs.append((int(i), int(match[0])))
    return _FACE_ID[frozenset(low)], _FACE_ID[frozenset(high)], pairs


def _calc_stride(max_val: int) -> int:
    s = 10000
    while s <= max_val:
        s *= 10
    return s


def resolve_ply_count(thickness_mean, plies=None, ply_thickness=None):
    if (plies is None) == (ply_thickness is None):
        raise EmbmeshError('specify exactly one of --plies or --ply-thickness')
    if plies is not None:
        if isinstance(plies, bool) or int(plies) != plies or plies < 1:
            raise EmbmeshError('--plies must be a positive integer')
        return int(plies)
    if not np.isfinite(ply_thickness) or ply_thickness <= 0:
        raise EmbmeshError('--ply-thickness must be positive and finite')
    return max(1, round(thickness_mean / ply_thickness))


def build_ply_part(part, plies=None, ply_thickness=None, thickness_axis=None, through_thickness=1):
    """Return (one-ply Part, metadata); all coordinates remain in the part frame.
    thickness_axis ('x'/'y'/'z' or 'dx,dy,dz', part frame) defaults to the shortest bbox extent."""
    if isinstance(through_thickness, bool) or int(through_thickness) != through_thickness or through_thickness < 1:
        raise EmbmeshError('--through-thickness must be a positive integer')
    through_thickness = int(through_thickness)
    if through_thickness % 2 == 0:
        raise EmbmeshError(f'--through-thickness must be odd (1, 3, 5, ...); got {through_thickness}')
    if not part.elements or not part.nodes:
        raise EmbmeshError('plate part has no hex mesh')
    for elem in part.elements.values():
        if not elem.type.upper().startswith('C3D8') or len(elem.connectivity) != 8:
            raise EmbmeshError(f'element {elem.label} is not a C3D8 hex')
    direction = pick_thickness_axis(part.nodes, thickness_axis)
    pairs_by_elem = {}
    local_pairs_by_elem = {}
    faces = {}
    bottom_nodes, top_nodes = set(), set()
    spans, edge_lengths, pair_vectors = [], [], []
    for elem in part.elements.values():
        conn = elem.connectivity
        pts = np.array([part.nodes[n] for n in conn])
        bottom_face, top_face, local_pairs = oriented_faces(pts, direction)
        pairs = [(conn[i], conn[j]) for i, j in local_pairs]
        pairs_by_elem[elem.label] = pairs
        local_pairs_by_elem[elem.label] = local_pairs
        faces[elem.label] = (bottom_face, top_face)
        bottom_nodes.update(a for a, _ in pairs)
        top_nodes.update(b for _, b in pairs)
        spans.append(abs(np.dot(pts[local_pairs[0][1]] - pts[local_pairs[0][0]], direction)))
        pair_vectors.extend(part.nodes[b] - part.nodes[a] for a, b in pairs)
        face = next(face for face in HEX_FACES if _FACE_ID[frozenset(face)] == bottom_face)
        edge_lengths.extend(np.linalg.norm(pts[face[(i + 1) % 4]] - pts[face[i]]) for i in range(4))
    if bottom_nodes & top_nodes or bottom_nodes | top_nodes != set(part.nodes):
        raise EmbmeshError('plate must have exactly one conforming hex layer through thickness')
    pair_vectors = np.asarray(pair_vectors)
    step_full = np.median(pair_vectors, axis=0)
    mismatch = np.linalg.norm(pair_vectors - step_full, axis=1)
    tolerance = max(1e-8, 0.11 * float(np.median(edge_lengths)))
    if float(mismatch.max()) > tolerance:
        raise EmbmeshError(f'face translation mismatch {mismatch.max():.6g} exceeds {tolerance:.6g} (max/mean/p95 = {mismatch.max():.6g}/{mismatch.mean():.6g}/{np.percentile(mismatch, 95):.6g})')
    thickness = np.asarray(spans)
    if not np.all(np.isfinite(thickness)) or thickness.min() <= 0:
        raise EmbmeshError('plate thickness is degenerate')
    n = resolve_ply_count(float(thickness.mean()), plies, ply_thickness)
    step_ply = step_full / n

    top_to_bottom = {}
    bottom_to_top = {}
    for pairs in pairs_by_elem.values():
        for bottom, top in pairs:
            if top in top_to_bottom and top_to_bottom[top] != bottom:
                raise EmbmeshError(f'top node {top} has inconsistent bottom pairing')
            top_to_bottom[top] = bottom
            bottom_to_top[bottom] = top

    if through_thickness == 1:
        nodes = {label: np.array(pos, copy=True) for label, pos in part.nodes.items()}
        for top, bottom in top_to_bottom.items():
            nodes[top] = part.nodes[bottom] + step_ply
        elements = {k: Element(e.label, e.connectivity, e.type, e.elset)
                    for k, e in part.elements.items()}
        nsets = {k: set(v) for k, v in part.nsets.items()}
        elsets = {k: set(v) for k, v in part.elsets.items()}
        surfaces = {k: list(v) for k, v in part.surfaces.items()}
        ply = Part(part.name, nodes=nodes, elements=elements, nsets=nsets, elsets=elsets, surfaces=surfaces)
        ply.elsets['PLY'] = set(part.elements)
        ply.surfaces['PLY_BOTTOM'] = [(eid, faces[eid][0]) for eid in part.elements]
        ply.surfaces['PLY_TOP'] = [(eid, faces[eid][1]) for eid in part.elements]
        ply._mid_elements = ply.elements
        ply._N_stride = None
        ply._E_stride = None
        ply._part_elements = set(part.elements)
        ply._column_info = None
    else:
        max_node = max(part.nodes) if part.nodes else 0
        max_elem = max(part.elements) if part.elements else 0
        N_stride = _calc_stride(max_node)
        E_stride = _calc_stride(max_elem)

        nodes = {}
        for b in bottom_nodes:
            nodes[b] = np.array(part.nodes[b], copy=True)
        for t in top_nodes:
            b = top_to_bottom[t]
            nodes[t] = part.nodes[b] + step_ply
        for l in range(1, through_thickness):
            frac = l / through_thickness
            for b in bottom_nodes:
                nodes[b + l * N_stride] = part.nodes[b] + frac * step_ply

        elements = {}
        mid_elements = {}
        m_mid = (through_thickness - 1) // 2

        for eid, elem in part.elements.items():
            conn = elem.connectivity
            b_face, t_face = faces[eid]
            local_pairs = local_pairs_by_elem[eid]
            for m in range(through_thickness):
                new_eid = eid + m * E_stride
                new_conn = list(conn)
                for loc_b, loc_t in local_pairs:
                    b_orig = conn[loc_b]
                    t_orig = conn[loc_t]
                    node_bot = b_orig if m == 0 else b_orig + m * N_stride
                    node_top = t_orig if m + 1 == through_thickness else b_orig + (m + 1) * N_stride
                    new_conn[loc_b] = node_bot
                    new_conn[loc_t] = node_top
                new_el = Element(new_eid, new_conn, elem.type, elem.elset)
                elements[new_eid] = new_el
                if m == m_mid:
                    mid_elements[new_eid] = new_el

        nsets = {}
        for k, v in part.nsets.items():
            s = set(v)
            for b, t in bottom_to_top.items():
                if b in v and t in v:
                    for l in range(1, through_thickness):
                        s.add(b + l * N_stride)
            nsets[k] = s

        elsets = {}
        for k, v in part.elsets.items():
            s = set(v)
            for e in v:
                if e in part.elements:
                    for m in range(1, through_thickness):
                        s.add(e + m * E_stride)
            elsets[k] = s

        surfaces = {k: list(v) for k, v in part.surfaces.items()}
        ply = Part(part.name, nodes=nodes, elements=elements, nsets=nsets, elsets=elsets, surfaces=surfaces)
        ply.elsets['PLY'] = set(elements)
        ply.surfaces['PLY_BOTTOM'] = [(eid, faces[eid][0]) for eid in part.elements]
        ply.surfaces['PLY_TOP'] = [(eid + (through_thickness - 1) * E_stride, faces[eid][1]) for eid in part.elements]
        ply._mid_elements = mid_elements
        ply._N_stride = N_stride
        ply._E_stride = E_stride
        ply._part_elements = set(part.elements)
        ply._column_info = {
            'N_stride': N_stride,
            'E_stride': E_stride,
            'bottom_to_top': bottom_to_top,
            'part_elements': set(part.elements),
            'through_thickness': through_thickness,
        }

    meta = dict(plies=n, thickness_min=float(thickness.min()), thickness_mean=float(thickness.mean()),
                thickness_max=float(thickness.max()), resulting_ply_thickness=float(thickness.mean() / n),
                stack_vector=step_full.tolist(), step=step_ply.tolist(),
                mismatch_max=float(mismatch.max()), mismatch_mean=float(mismatch.mean()),
                mismatch_p95=float(np.percentile(mismatch, 95)), mismatch_tolerance=tolerance,
                expected_interface_gap_max=0.0,
                stacked_top_residual_max=float(mismatch.max()),
                stacked_top_residual_mean=float(mismatch.mean()),
                stacked_top_residual_p95=float(np.percentile(mismatch, 95)),
                through_thickness=through_thickness,
                through_thickness_element_thickness=float(thickness.mean() / (n * through_thickness)),
                N_stride=getattr(ply, '_N_stride', None),
                E_stride=getattr(ply, '_E_stride', None))
    return ply, meta


def interface_pairs(plies):
    return [(f'Ply-{k}_top', f'Ply-{k + 1}_bottom') for k in range(1, plies)]


def _keyword(line):
    return line.strip().split(',', 1)[0].lower()


def _option(line, name):
    match = re.search(r'(?:^|,)\s*' + re.escape(name) + r'\s*=\s*([^,]+)', line, re.I)
    return match.group(1).strip() if match else None


def _surface_lines(ply, instance):
    lines = []
    for side in ('bottom', 'top'):
        name = f'{instance}_{side}'
        by_face = {}
        for eid, face in ply.surfaces[f'PLY_{side.upper()}']:
            by_face.setdefault(face, []).append(eid)
        for face in sorted(by_face):
            elset = f'_{name}_{face}'
            ids = sorted(by_face[face])
            if len(ids) >= 3 and ids == list(range(ids[0], ids[-1] + 1)):
                lines.append(f'*Elset, elset={elset}, internal, instance={instance}, generate')
                lines.append(f'{ids[0]}, {ids[-1]}, 1')
            else:
                lines.append(f'*Elset, elset={elset}, internal, instance={instance}')
                lines.extend(', '.join(map(str, ids[i:i + 16])) for i in range(0, len(ids), 16))
        lines.append(f'*Surface, type=ELEMENT, name={name}')
        lines.extend(f'_{name}_{face}, {face}' for face in sorted(by_face))
    return lines


def _update_part_lines(part_lines, ply, through_thickness=1):
    if through_thickness == 1:
        node_start = next(i for i, s in enumerate(part_lines) if _keyword(s) == '*node')
        node_end = next(i for i in range(node_start + 1, len(part_lines)) if part_lines[i].lstrip().startswith('*'))
        node_lines = [f'{label}, {p[0]:.17g}, {p[1]:.17g}, {p[2]:.17g}' for label, p in ply.nodes.items()]
        extra = ['*Elset, elset=PLY']
        ids = sorted(ply.elements)
        extra.extend(', '.join(map(str, ids[i:i + 16])) for i in range(0, len(ids), 16))
        return part_lines[:node_start + 1] + node_lines + part_lines[node_end:] + extra

    node_start = next(i for i, s in enumerate(part_lines) if _keyword(s) == '*node')
    node_end = next(i for i in range(node_start + 1, len(part_lines)) if part_lines[i].lstrip().startswith('*'))
    node_lines = [f'{label}, {p[0]:.17g}, {p[1]:.17g}, {p[2]:.17g}' for label, p in ply.nodes.items()]

    col_info = getattr(ply, '_column_info', None)
    N_stride = col_info['N_stride']
    E_stride = col_info['E_stride']
    b2t = col_info['bottom_to_top']
    p_elems = col_info['part_elements']

    res = part_lines[:node_start + 1] + node_lines
    i = node_end
    while i < len(part_lines):
        line = part_lines[i]
        kw = _keyword(line)
        if kw == '*element':
            j = i + 1
            while j < len(part_lines) and not part_lines[j].lstrip().startswith('*'):
                j += 1
            elem_type = _option(line, 'type') or 'C3D8R'
            el_header = f'*Element, type={elem_type}'
            elem_lines = [f"{e.label}, " + ", ".join(map(str, e.connectivity)) for e in sorted(ply.elements.values(), key=lambda x: x.label)]
            res.append(el_header)
            res.extend(elem_lines)
            i = j
            continue
        elif kw in ('*nset', '*elset'):
            j = i + 1
            while j < len(part_lines) and not part_lines[j].lstrip().startswith('*'):
                j += 1
            block = part_lines[i:j]
            is_gen = bool(re.search(r'(?i),\s*generate\b', block[0]))
            ids = []
            if is_gen:
                for row in block[1:]:
                    vals = [int(v.strip()) for v in row.split(',') if v.strip() and not v.strip().startswith('**')]
                    if len(vals) >= 2:
                        s, e = vals[0], vals[1]
                        st = vals[2] if len(vals) >= 3 else 1
                        ids.extend(range(s, e + 1, st))
            else:
                for row in block[1:]:
                    ids.extend(int(v.strip()) for v in row.split(',') if v.strip() and not v.strip().startswith('**'))
            if kw == '*nset':
                s_ids = set(ids)
                for b, t in b2t.items():
                    if b in s_ids and t in s_ids:
                        for l in range(1, through_thickness):
                            s_ids.add(b + l * N_stride)
                new_ids = sorted(s_ids)
            else:
                s_ids = set(ids)
                for e in ids:
                    if e in p_elems:
                        for m in range(1, through_thickness):
                            s_ids.add(e + m * E_stride)
                new_ids = sorted(s_ids)
            clean_header = re.sub(r'(?i),\s*generate\b', '', block[0])
            data_lines = [', '.join(map(str, new_ids[k:k + 16])) for k in range(0, len(new_ids), 16)]
            res.append(clean_header)
            res.extend(data_lines)
            i = j
            continue
        res.append(line)
        i += 1

    extra = ['*Elset, elset=PLY']
    ids = sorted(ply.elements)
    extra.extend(', '.join(map(str, ids[k:k + 16])) for k in range(0, len(ids), 16))
    res.extend(extra)
    return res


def _rewrite_assembly_sets(lines, old_instance, plies, column_info=None):
    rewritten, left = [], []
    result = []
    in_assembly = False
    i = 0
    through_thickness = column_info['through_thickness'] if column_info else 1
    while i < len(lines):
        line = lines[i]
        keyword = _keyword(line)
        if keyword == '*assembly':
            in_assembly = True
        elif keyword == '*end assembly':
            in_assembly = False
        if (in_assembly and keyword in ('*nset', '*elset') and
                (_option(line, 'instance') or '').lower() == old_instance.lower()):
            j = i + 1
            while j < len(lines) and not lines[j].lstrip().startswith('*'):
                j += 1
            block = lines[i:j]
            set_name = _option(line, 'nset') or _option(line, 'elset') or ''
            if set_name.lower().startswith('_surf-'):
                result.extend(block)
                left.append(f'{keyword} {set_name}')
            else:
                if column_info and through_thickness > 1:
                    is_gen = bool(re.search(r'(?i),\s*generate\b', block[0]))
                    ids = []
                    if is_gen:
                        for row in block[1:]:
                            vals = [int(v.strip()) for v in row.split(',') if v.strip() and not v.strip().startswith('**')]
                            if len(vals) >= 2:
                                s, e = vals[0], vals[1]
                                st = vals[2] if len(vals) >= 3 else 1
                                ids.extend(range(s, e + 1, st))
                    else:
                        for row in block[1:]:
                            ids.extend(int(v.strip()) for v in row.split(',') if v.strip() and not v.strip().startswith('**'))
                    if keyword == '*nset':
                        N_stride = column_info['N_stride']
                        b2t = column_info['bottom_to_top']
                        s_ids = set(ids)
                        for b, t in b2t.items():
                            if b in s_ids and t in s_ids:
                                for l in range(1, through_thickness):
                                    s_ids.add(b + l * N_stride)
                        new_ids = sorted(s_ids)
                    else:
                        E_stride = column_info['E_stride']
                        p_elems = column_info['part_elements']
                        s_ids = set(ids)
                        for e in ids:
                            if e in p_elems:
                                for m in range(1, through_thickness):
                                    s_ids.add(e + m * E_stride)
                        new_ids = sorted(s_ids)
                    clean_header = re.sub(r'(?i),\s*generate\b', '', block[0])
                    data_lines = [', '.join(map(str, new_ids[k:k + 16])) for k in range(0, len(new_ids), 16)]
                    block = [clean_header] + data_lines

                for k in range(1, plies + 1):
                    result.extend([re.sub(r'(?i)(\binstance\s*=\s*)' + re.escape(old_instance) + r'(?=\s*(?:,|$))',
                                          rf'\g<1>Ply-{k}', block[0])] + block[1:])
                rewritten.append(f'{keyword} {set_name}')
            i = j
            continue
        result.append(line)
        i += 1
    return result, sorted(set(rewritten)), sorted(set(left))


def _find_surface_interaction_blocks(lines: list[str]) -> list[tuple[int, int, str]]:
    """Return list of (start_idx, end_idx, interaction_name) for each *Surface Interaction."""
    blocks = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i].strip()
        if line.startswith('*') and not line.startswith('**'):
            kw = _keyword(line)
            if kw == '*surface interaction':
                name = _option(line, 'name')
                name = name.strip('\'"') if name else ''
                start = i
                last_idx = i
                for j in range(i + 1, n):
                    lj = lines[j].strip()
                    if lj.startswith('*') and not lj.startswith('**'):
                        kj = _keyword(lj)
                        if kj in (
                            '*cohesive behavior',
                            '*damage initiation',
                            '*damage evolution',
                            '*friction',
                            '*surface behavior',
                            '*contact damping',
                            '*gap conductance',
                            '*thermal conductance',
                        ):
                            last_idx = j
                        else:
                            break
                    elif not lj.startswith('**') and lj:
                        last_idx = j
                blocks.append((start, last_idx + 1, name))
                i = last_idx + 1
                continue
        i += 1
    return blocks


def _insert_or_replace_surface_interaction(
    lines: list[str],
    interaction_lines: list[str],
    name: str,
    overwrite: bool = False,
) -> list[str]:
    """Insert or replace *Surface Interaction block in deck lines."""
    blocks = _find_surface_interaction_blocks(lines)
    existing = [b for b in blocks if b[2].lower() == name.lower()]

    if existing:
        if not overwrite:
            raise EmbmeshError(
                f"*Surface Interaction {name!r} already exists in deck; "
                f"use --cohesive-overwrite to replace it"
            )
        start, end, _ = existing[0]
        # Include any immediately preceding preset/hazzard comment header
        if start > 0 and (
            lines[start - 1].strip().lower().startswith('** hazzard')
            or lines[start - 1].strip().lower() == '** cohesive interface preset'
        ):
            start -= 1
        return lines[:start] + interaction_lines + lines[end:]

    # Not existing: insert before the first *Step
    step_idx = next((i for i, l in enumerate(lines) if _keyword(l) == '*step'), None)
    if step_idx is None:
        step_idx = len(lines)

    # Find the last *Material block before *Step
    mats = [i for i in range(step_idx) if _keyword(lines[i]) == '*material']
    if mats:
        last_m = mats[-1]
        last_idx = last_m
        for k in range(last_m + 1, step_idx):
            l = lines[k].strip()
            if l.startswith('*') and not l.startswith('**'):
                if _keyword(l) in (
                    '*surface interaction',
                    '*boundary',
                    '*initial conditions',
                    '*amplitude',
                    '*step',
                ):
                    break
                last_idx = k
            elif not l.startswith('**') and l:
                last_idx = k
        insert_pos = last_idx + 1
    else:
        insert_pos = step_idx

    return lines[:insert_pos] + interaction_lines + lines[insert_pos:]


def _expand_instance_boundaries(lines, instance, plies):
    """Repeat *Boundary rows that name `instance.<set>` for every Ply-k instance.

    The ply Part keeps the source part's node sets, so e.g. `Plate-1.fix, ENCASTRE`
    becomes `Ply-1.fix` ... `Ply-N.fix`.
    """
    pattern = re.compile(r'^\s*' + re.escape(instance) + r'\.([^,\s]+)\s*(,.*)$', re.I)
    result, expanded, active = [], [], False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('*') and not stripped.startswith('**'):
            active = _keyword(line) == '*boundary'
        elif active and not stripped.startswith('**'):
            match = pattern.match(line)
            if match:
                result.extend(f'Ply-{k}.{match.group(1)}{match.group(2)}' for k in range(1, plies + 1))
                expanded.append(stripped)
                continue
        result.append(line)
    return result, expanded


def write_plywise_deck(source, output, instance='Plate-1', plies=None, ply_thickness=None,
                       thickness_axis=None, plate_node_contact=False, fiber_node_contact=False,
                       ball_instance=None, contact_thickness='auto', ball_interaction=None,
                       fiber_instances=(), layup=None, layup_symmetric=False, layup_repeat=1,
                       fiber_diameter=None, fiber_gap=0.0, fiber_type='truss', fiber_material='Fiber',
                       cohesion=None,
                       cohesive_material=None, cohesive_rate='quasi-static', cohesive_name=None,
                       length_units='m', cohesive_overwrite=False,
                       through_thickness=1,
                       collapse_layers=False, host_mode='native', vuel_ghost_options=None,
                       vuel_smear_through_thickness=False, plate_surface='nodes',
                        fiber_host_contact='none'):
    """Patch only the selected part and instance; report old assembly references."""
    source = Path(source)
    if collapse_layers:
        from .collapse import collapse_deck_text
        deck_raw = parse_deck(source)
        lines_raw = source.read_text().splitlines()
        lines, collapse_report = collapse_deck_text(
            lines_raw, deck_raw, instance=instance, thickness_axis=thickness_axis
        )
        deck = parse_deck('\n'.join(lines))
    else:
        deck = parse_deck(source)
        lines = source.read_text().splitlines()
        collapse_report = None

    if instance not in deck.instances:
        raise EmbmeshError(f'instance {instance!r} not found')
    old = deck.instances[instance]
    part = deck.parts[old.part]
    ply, meta = build_ply_part(part, plies, ply_thickness, thickness_axis, through_thickness=through_thickness)
    if collapse_report is not None:
        meta['collapse'] = {k: v for k, v in collapse_report.items() if not k.startswith('_')}
    ply.nodes = {label: old.transform(point) for label, point in ply.nodes.items()}
    world_step = old.transform(np.asarray(meta['step'])) - old.transform(np.zeros(3))
    meta['step_world'] = world_step.tolist()

    start = next((i for i, s in enumerate(lines) if _keyword(s) == '*part' and
                  (_option(s, 'name') or '').lower() == part.name.lower()), None)
    if start is None:
        raise EmbmeshError(f'part {part.name!r} not found in source text')
    end = next(i for i in range(start + 1, len(lines)) if _keyword(lines[i]) == '*end part')
    part_lines = lines[start:end]
    part_lines = _update_part_lines(part_lines, ply, through_thickness=through_thickness)
    lines = lines[:start] + part_lines + lines[end:]
    inst_start = next((i for i, s in enumerate(lines) if _keyword(s) == '*instance' and
                       (_option(s, 'name') or '').lower() == instance.lower()), None)
    if inst_start is None:
        raise EmbmeshError(f'instance {instance!r} not found in source text')
    inst_end = next(i for i in range(inst_start + 1, len(lines)) if _keyword(lines[i]) == '*end instance')
    replacement = []
    for k in range(meta['plies']):
        replacement.append(f'*Instance, name=Ply-{k + 1}, part={part.name}')
        translation = k * world_step
        replacement.append(', '.join(f'{v:.17g}' for v in translation))
        replacement.append('*End Instance')
    lines = lines[:inst_start] + replacement + lines[inst_end + 1:]
    col_info = getattr(ply, '_column_info', None)
    lines, rewritten, left = _rewrite_assembly_sets(lines, instance, meta['plies'], column_info=col_info)
    lines, expanded = _expand_instance_boundaries(lines, instance, meta['plies'])
    meta['boundaries_expanded'] = expanded
    assembly_end = next(i for i, s in enumerate(lines) if _keyword(s) == '*end assembly')
    surfaces = []
    for k in range(1, meta['plies'] + 1):
        surfaces.extend(_surface_lines(ply, f'Ply-{k}'))
    lines[assembly_end:assembly_end] = surfaces
    references = [s.strip() for s in lines if re.search(r'\b' + re.escape(instance) + r'\b', s, re.I)
                  and not s.lstrip().startswith('**')]
    meta['old_instance_references'] = sorted(set(references))
    meta['assembly_sets_rewritten'] = rewritten
    meta['impact_surface_elsets_left'] = left
    meta.setdefault('warnings', [])

    # Cohesive interaction preset generation / insertion
    cohesion_interaction = cohesion
    if cohesive_material:
        if cohesive_name is None and cohesion is not None:
            cohesive_name = cohesion
        t_ply = float(meta['resulting_ply_thickness'])
        if length_units == 'm' and t_ply > 0.5:
            meta['warnings'].append(
                f"resulting ply thickness {t_ply:.4g} is > 0.5 in 'm' units mode; "
                f"check --length-units (likely mm geometry in m mode)"
            )
        elif length_units == 'mm' and t_ply < 1e-3:
            meta['warnings'].append(
                f"resulting ply thickness {t_ply:.4g} is < 1e-3 in 'mm' units mode; "
                f"check --length-units (likely m geometry in mm mode)"
            )
        c_inter = cohesive_interaction(
            material=cohesive_material,
            ply_thickness=t_ply,
            units=length_units,
            rate=cohesive_rate,
            name=cohesive_name,
        )
        for w in c_inter.warnings:
            if w not in meta['warnings']:
                meta['warnings'].append(w)
        meta['cohesive_interaction'] = {
            'name': c_inter.name,
            'material': cohesive_material,
            'rate': cohesive_rate,
            'thickness_used': t_ply,
            'units': length_units,
            'k': list(c_inter.k),
            'strength': list(c_inter.strength),
            'fracture_energy': list(c_inter.fracture_energy),
            'warnings': list(c_inter.warnings),
        }
        lines = _insert_or_replace_surface_interaction(
            lines, c_inter.inp_lines(), c_inter.name, overwrite=cohesive_overwrite
        )
        cohesion_interaction = c_inter.name

    if host_mode not in ('native', 'vuel-ghost'):
        raise EmbmeshError(f'unknown host mode {host_mode!r}')
    if host_mode == 'vuel-ghost' and not layup:
        raise EmbmeshError('--host-mode vuel-ghost requires --layup and --fiber-diameter')
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text('\n'.join(lines) + '\n')
    from .plywise_contact import FiberInstanceRef, add_plywise_ball_contact, clean_old_impact_references

    ghost_by_host = None
    if layup:
        if not fiber_diameter:
            raise EmbmeshError('--layup needs --fiber-diameter')
        from .plyfibers import PlyInstanceInfo, append_plyfibers_to_deck, expand_layup, ply_fibers
        angles = expand_layup(layup, meta['plies'], layup_symmetric, layup_repeat)
        axis = np.asarray(meta['step_world'], float)
        axis = axis / np.linalg.norm(axis)
        fiber_host_elements = getattr(ply, '_mid_elements', ply.elements)
        fibers_by_angle = {a: ply_fibers(fiber_host_elements, ply.nodes, a, fiber_diameter, fiber_gap,
                                         thickness_axis=','.join(f'{v:.17g}' for v in axis),
                                         ply_thickness=meta['resulting_ply_thickness'],
                                         center_grid=through_thickness > 1)
                           for a in sorted(set(angles))}
        infos = [PlyInstanceInfo(f'Ply-{k + 1}', k * world_step) for k in range(meta['plies'])]
        if host_mode == 'vuel-ghost':
            from .plywise_vuel import convert_plywise_hosts
            converted, ghost_by_host, host_meta = convert_plywise_hosts(
                output.read_text().splitlines(), ply, angles, fibers_by_angle,
                fiber_diameter, vuel_ghost_options, precise=through_thickness > 1,
                smear=vuel_smear_through_thickness)
            output.write_text('\n'.join(converted) + '\n')
            meta['vuel_ghost'] = host_meta
            if any(p['at_or_above_one'] for p in host_meta['per_ply_fractions'].values()):
                meta['warnings'].append('fiber volume fraction reaches or exceeds 1 in some hosts; VUEL floors remaining matrix fraction at 1e-6')
        append_plyfibers_to_deck(output, output, infos, fibers_by_angle, angles, fiber_diameter,
                                 fiber_material, fiber_type)
        from .plywise_vuel import finish_plywise_fibers
        finished, symmetry_counts = finish_plywise_fibers(
            output.read_text().splitlines(), source, instance, angles,
            fibers_by_angle, world_step, host_mode == 'vuel-ghost', ply)
        output.write_text('\n'.join(finished) + '\n')
        meta['fiber_boundary_nodes_per_ply'] = symmetry_counts
        offsets = {a: 100000 + i * 100000 for i, a in enumerate(sorted(set(angles)))}
        fiber_instances = [FiberInstanceRef(f'Fibers-Ply-{k + 1}', tuple(range(
            offsets[a], offsets[a] + sum(len(f.points) for f in fibers_by_angle[a]))))
            for k, a in enumerate(angles)]
        meta['layup'] = [float(a) for a in angles]
        meta['fibers_per_angle'] = {str(a): len(f) for a, f in fibers_by_angle.items()}
        if not re.search(r'^\*material\s*,\s*name\s*=\s*"?' + re.escape(fiber_material) + r'"?\s*$',
                         output.read_text(), re.I | re.M):
            meta['warnings'].append(f'no *Material named {fiber_material!r} in the deck; fibers need one')
    if plate_node_contact or (fiber_node_contact and fiber_instances):
        meta['ball_contact'] = add_plywise_ball_contact(
            output, instance, ball_instance, plate=plate_node_contact,
            fiber=fiber_node_contact, fibers=fiber_instances,
            thickness=contact_thickness, interaction_name=ball_interaction,
            ply_thickness=meta['resulting_ply_thickness'],
            ply=ply, world_step=world_step, plies=meta['plies'],
            ghost_by_host=ghost_by_host, plate_surface=plate_surface)
        meta['old_instance_references'] = [s for s in meta['old_instance_references']
                                           if s not in meta['ball_contact']['removed_old_references']]
    else:
        _, stale = clean_old_impact_references(lines, instance, False)
        meta['ball_contact'] = None
        if stale:
            meta['warnings'].append('UNRESOLVABLE DECK: dangling old-instance impact surface references; enable --plate-node-contact')
            meta['dangling_impact_references'] = stale
        if fiber_node_contact:
            meta['warnings'].append('fiber node contact requested but no fiber instances exist; no fiber contact was added')
    if fiber_host_contact == 'baseline' and fiber_instances:
        from .plywise_contact import add_plywise_fiber_host_contact
        meta['fiber_host_contact'] = add_plywise_fiber_host_contact(
            output,
            hosts=[f"Ply-{k + 1}" for k in range(meta["plies"])],
            fibers=fiber_instances,
            ghost_by_host=bool(ghost_by_host),
            ply_thickness=meta.get('resulting_ply_thickness'),
            through_thickness=through_thickness,
            fiber_diameter=fiber_diameter,
        )
    if cohesion_interaction:
        # after the ball contact so the shared *Contact block already exists; Abaqus/Explicit needs
        # general contact for surface-based cohesive behavior (contact pairs reject it)
        from .plycohesive import insert_cohesive_general_contact
        output.write_text(insert_cohesive_general_contact(
            output.read_text(), interface_pairs(meta['plies']), interaction=cohesion_interaction))
        meta['cohesion'] = {'interaction': cohesion_interaction, 'pairs': meta['plies'] - 1,
                            'mechanism': 'general contact (*Contact Property Assignment per interface)'}
    return meta
