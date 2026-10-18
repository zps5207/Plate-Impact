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


def build_ply_part(part, plies=None, ply_thickness=None, thickness_axis=None):
    """Return (one-ply Part, metadata); all coordinates remain in the part frame.
    thickness_axis ('x'/'y'/'z' or 'dx,dy,dz', part frame) defaults to the shortest bbox extent."""
    if not part.elements or not part.nodes:
        raise EmbmeshError('plate part has no hex mesh')
    for elem in part.elements.values():
        if not elem.type.upper().startswith('C3D8') or len(elem.connectivity) != 8:
            raise EmbmeshError(f'element {elem.label} is not a C3D8 hex')
    direction = pick_thickness_axis(part.nodes, thickness_axis)
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


def write_plywise_deck(source, output, instance='Plate-1', plies=None, ply_thickness=None,
                       thickness_axis=None, plate_node_contact=False, fiber_node_contact=False,
                       ball_instance=None, contact_thickness='auto', ball_interaction=None,
                       fiber_instances=(), layup=None, layup_symmetric=False, layup_repeat=1,
                       fiber_diameter=None, fiber_gap=0.0, fiber_type='truss', fiber_material='Fiber',
                       cohesion=None, cohesion_slave='lower',
                       cohesive_material=None, cohesive_rate='quasi-static', cohesive_name=None,
                       length_units='m', cohesive_overwrite=False,
                       collapse_layers=False, host_mode='native', vuel_ghost_options=None):
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
    ply, meta = build_ply_part(part, plies, ply_thickness, thickness_axis)
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

    if layup:
        if not fiber_diameter:
            raise EmbmeshError('--layup needs --fiber-diameter')
        from .plyfibers import PlyInstanceInfo, append_plyfibers_to_deck, expand_layup, ply_fibers
        angles = expand_layup(layup, meta['plies'], layup_symmetric, layup_repeat)
        axis = np.asarray(meta['step_world'], float)
        axis = axis / np.linalg.norm(axis)
        fibers_by_angle = {a: ply_fibers(ply.elements, ply.nodes, a, fiber_diameter, fiber_gap,
                                         thickness_axis=','.join(f'{v:.17g}' for v in axis))
                           for a in sorted(set(angles))}
        infos = [PlyInstanceInfo(f'Ply-{k + 1}', k * world_step) for k in range(meta['plies'])]
        if host_mode == 'vuel-ghost':
            from .plywise_vuel import convert_plywise_hosts
            converted, _, host_meta = convert_plywise_hosts(
                output.read_text().splitlines(), ply, angles, fibers_by_angle,
                fiber_diameter, vuel_ghost_options)
            output.write_text('\n'.join(converted) + '\n')
            meta['vuel_ghost'] = host_meta
            if any(p['at_or_above_one'] for p in host_meta['per_ply_fractions'].values()):
                meta['warnings'].append('fiber volume fraction reaches or exceeds 1 in some hosts; VUEL floors remaining matrix fraction at 1e-6')
        append_plyfibers_to_deck(output, output, infos, fibers_by_angle, angles, fiber_diameter,
                                 fiber_material, fiber_type)
        from .plywise_vuel import finish_plywise_fibers
        finished, symmetry_counts = finish_plywise_fibers(
            output.read_text().splitlines(), source, instance, angles,
            fibers_by_angle, world_step, host_mode == 'vuel-ghost')
        output.write_text('\n'.join(finished) + '\n')
        meta['fiber_symmetry_nodes_per_ply'] = symmetry_counts
        offsets = {a: 100000 + i * 100000 for i, a in enumerate(sorted(set(angles)))}
        fiber_instances = [FiberInstanceRef(f'Fibers-Ply-{k + 1}', tuple(range(
            offsets[a], offsets[a] + sum(len(f.points) for f in fibers_by_angle[a]))))
            for k, a in enumerate(angles)]
        meta['layup'] = [float(a) for a in angles]
        meta['fibers_per_angle'] = {str(a): len(f) for a, f in fibers_by_angle.items()}
        if not re.search(r'^\*material\s*,\s*name\s*=\s*"?' + re.escape(fiber_material) + r'"?\s*$',
                         output.read_text(), re.I | re.M):
            meta['warnings'].append(f'no *Material named {fiber_material!r} in the deck; fibers need one')
    if cohesion_interaction:
        from .plycohesive import insert_cohesive_contact_into_deck
        insert_cohesive_contact_into_deck(output, output, interface_pairs(meta['plies']),
                                          interaction=cohesion_interaction, slave=cohesion_slave)
        meta['cohesion'] = {'interaction': cohesion_interaction, 'pairs': meta['plies'] - 1}
    if plate_node_contact or (fiber_node_contact and fiber_instances):
        meta['ball_contact'] = add_plywise_ball_contact(
            output, instance, ball_instance, plate=plate_node_contact,
            fiber=fiber_node_contact, fibers=fiber_instances,
            thickness=contact_thickness, interaction_name=ball_interaction,
            ply_thickness=meta['resulting_ply_thickness'])
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
    return meta
