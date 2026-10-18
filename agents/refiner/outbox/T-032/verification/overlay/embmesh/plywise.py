"""Split a one-hex-thick plate into translated instances of one ply part."""
from __future__ import annotations

from pathlib import Path
import re

import numpy as np

from .errors import MesherInputError
from .geometry import HEX_FACES, hex_thickness_axis
from .model import Part, Element
from .parser import parse_deck


class EmbmeshError(MesherInputError):
    """Plywise input cannot be represented as translated congruent plies."""


# Same local coordinates as geometry.hex_volume/inverse_hex, in Abaqus order.
_SIGNS = np.array([[-1, -1, 1], [-1, 1, 1], [1, 1, 1], [1, -1, 1],
                   [-1, -1, -1], [-1, 1, -1], [1, 1, -1], [1, -1, -1]])
_FACE_ID = {frozenset(face): f'S{i}' for i, face in enumerate(HEX_FACES, 1)}


def oriented_faces(points, direction):
    """Return (bottom face id, top face id, bottom/top local-node pairs)."""
    axis = hex_thickness_axis(points)
    low = np.flatnonzero(_SIGNS[:, axis] < 0)
    high = np.flatnonzero(_SIGNS[:, axis] > 0)
    p = np.asarray(points, float)
    if np.dot(p[high].mean(0) - p[low].mean(0), direction) < 0:
        low, high = high, low
    pairs = []
    for i in low:
        match = [j for j in high if np.all(_SIGNS[j, np.arange(3) != axis] ==
                                              _SIGNS[i, np.arange(3) != axis])]
        pairs.append((int(i), int(match[0])))
    return _FACE_ID[frozenset(low)], _FACE_ID[frozenset(high)], pairs


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


def build_ply_part(part, plies=None, ply_thickness=None):
    """Return (one-ply Part, metadata); all coordinates remain in the part frame."""
    if not part.elements or not part.nodes:
        raise EmbmeshError('plate part has no hex mesh')
    vectors = []
    for elem in part.elements.values():
        if not elem.type.upper().startswith('C3D8') or len(elem.connectivity) != 8:
            raise EmbmeshError(f'element {elem.label} is not a C3D8 hex')
        pts = np.array([part.nodes[n] for n in elem.connectivity])
        axis = hex_thickness_axis(pts)
        vectors.append(pts[_SIGNS[:, axis] > 0].mean(0) - pts[_SIGNS[:, axis] < 0].mean(0))
    vectors = np.asarray(vectors)
    _, _, vh = np.linalg.svd(vectors, full_matrices=False)
    direction = vh[0]
    dominant = int(np.argmax(np.abs(direction)))
    if direction[dominant] < 0:
        direction = -direction
    pairs_by_elem = {}
    faces = {}
    bottom_nodes, top_nodes = set(), set()
    spans, edge_lengths, pair_vectors = [], [], []
    for elem in part.elements.values():
        conn = elem.connectivity
        pts = np.array([part.nodes[n] for n in conn])
        bottom_face, top_face, local_pairs = oriented_faces(pts, direction)
        pairs = [(conn[i], conn[j]) for i, j in local_pairs]
        pairs_by_elem[elem.label] = pairs
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
    nodes = {label: np.array(pos, copy=True) for label, pos in part.nodes.items()}
    top_to_bottom = {}
    for pairs in pairs_by_elem.values():
        for bottom, top in pairs:
            if top in top_to_bottom and top_to_bottom[top] != bottom:
                raise EmbmeshError(f'top node {top} has inconsistent bottom pairing')
            top_to_bottom[top] = bottom
    for top, bottom in top_to_bottom.items():
        nodes[top] = part.nodes[bottom] + step_full / n
    ply = Part(part.name, nodes=nodes, elements={k: Element(e.label, e.connectivity, e.type, e.elset)
                                                 for k, e in part.elements.items()},
               nsets={k: set(v) for k, v in part.nsets.items()},
               elsets={k: set(v) for k, v in part.elsets.items()},
               surfaces={k: list(v) for k, v in part.surfaces.items()})
    ply.elsets['PLY'] = set(part.elements)
    ply.surfaces['PLY_BOTTOM'] = [(eid, face[0]) for eid, face in faces.items()]
    ply.surfaces['PLY_TOP'] = [(eid, face[1]) for eid, face in faces.items()]
    meta = dict(plies=n, thickness_min=float(thickness.min()), thickness_mean=float(thickness.mean()),
                thickness_max=float(thickness.max()), resulting_ply_thickness=float(thickness.mean() / n),
                stack_vector=step_full.tolist(), step=(step_full / n).tolist(),
                mismatch_max=float(mismatch.max()), mismatch_mean=float(mismatch.mean()),
                mismatch_p95=float(np.percentile(mismatch, 95)), mismatch_tolerance=tolerance,
                expected_interface_gap_max=0.0,
                stacked_top_residual_max=float(mismatch.max()),
                stacked_top_residual_mean=float(mismatch.mean()),
                stacked_top_residual_p95=float(np.percentile(mismatch, 95)))
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


def _rewrite_assembly_sets(lines, old_instance, plies):
    rewritten, left = [], []
    result = []
    in_assembly = False
    i = 0
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
                for k in range(1, plies + 1):
                    result.extend([re.sub(r'(?i)(\binstance\s*=\s*)' + re.escape(old_instance) + r'(?=\s*(?:,|$))',
                                          rf'\g<1>Ply-{k}', block[0])] + block[1:])
                rewritten.append(f'{keyword} {set_name}')
            i = j
            continue
        result.append(line)
        i += 1
    return result, sorted(set(rewritten)), sorted(set(left))


def write_plywise_deck(source, output, instance='Plate-1', plies=None, ply_thickness=None):
    """Patch only the selected part and instance; report old assembly references."""
    source = Path(source)
    deck = parse_deck(source)
    if instance not in deck.instances:
        raise EmbmeshError(f'instance {instance!r} not found')
    old = deck.instances[instance]
    part = deck.parts[old.part]
    ply, meta = build_ply_part(part, plies, ply_thickness)
    ply.nodes = {label: old.transform(point) for label, point in ply.nodes.items()}
    world_step = old.transform(np.asarray(meta['step'])) - old.transform(np.zeros(3))
    meta['step_world'] = world_step.tolist()
    lines = source.read_text().splitlines()
    start = next((i for i, s in enumerate(lines) if _keyword(s) == '*part' and
                  (_option(s, 'name') or '').lower() == part.name.lower()), None)
    if start is None:
        raise EmbmeshError(f'part {part.name!r} not found in source text')
    end = next(i for i in range(start + 1, len(lines)) if _keyword(lines[i]) == '*end part')
    part_lines = lines[start:end]
    node_start = next(i for i, s in enumerate(part_lines) if _keyword(s) == '*node')
    node_end = next(i for i in range(node_start + 1, len(part_lines)) if part_lines[i].lstrip().startswith('*'))
    node_lines = [f'{label}, {p[0]:.17g}, {p[1]:.17g}, {p[2]:.17g}' for label, p in ply.nodes.items()]
    extra = ['*Elset, elset=PLY']
    ids = sorted(ply.elements)
    extra.extend(', '.join(map(str, ids[i:i + 16])) for i in range(0, len(ids), 16))
    part_lines = part_lines[:node_start + 1] + node_lines + part_lines[node_end:] + extra
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
    lines, rewritten, left = _rewrite_assembly_sets(lines, instance, meta['plies'])
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
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text('\n'.join(lines) + '\n')
    return meta
