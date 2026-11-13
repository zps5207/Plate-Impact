"""Plywise node-to-ball and element-based contact, isolated from the legacy single-host path."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import numpy as np

from .contact import (BALL_ELSET, BALL_SURFACE, PLATE_NSET, PLATE_SURFACE,
                      FIBER_NSET, FIBER_SURFACE, CONTACT_INTERACTION,
                      _set_lines, _keyword, _augment_step_contact,
                      median_host_edge_length, resolve_contact_thickness)
from .geometry import HEX_FACES
from .parser import parse_deck

REV_FACE = {f'S{i}': i - 1 for i in range(1, 7)}


@dataclass(frozen=True)
class FiberInstanceRef:
    instance: str
    node_labels: tuple[int, ...]


def _blocks(lines):
    starts = [i for i, s in enumerate(lines) if s.lstrip().startswith('*') and
              not s.lstrip().startswith('**')]
    return [(i, starts[k + 1] if k + 1 < len(starts) else len(lines))
            for k, i in enumerate(starts)]


def _comment(lines, indices, reason):
    removed = []
    for i in sorted(set(indices)):
        if not lines[i].lstrip().startswith('**'):
            removed.append(lines[i].strip())
            lines[i] = f'** removed by embmesh plywise: {reason}: {lines[i]}'
    return removed


def _parse_ids(lines, is_generate=False):
    vals = []
    for line in lines:
        raw = line.strip()
        if not raw or raw.startswith('**') or raw.startswith('*'):
            continue
        for x in raw.split(','):
            x = x.strip()
            if x:
                vals.append(int(x))
    if is_generate:
        result = []
        for i in range(0, len(vals), 3):
            s = vals[i]
            e = vals[i + 1]
            st = vals[i + 2] if i + 2 < len(vals) else 1
            result.extend(range(s, e + 1, st))
        return result
    return vals


def _find_plate_impact_surface(lines, old_instance):
    """Find assembly element surface referencing old_instance, returning (surf_name, facets_by_face, all_facets)."""
    blocks = _blocks(lines)
    in_assembly = False
    old_elsets = {}
    for start, end in blocks:
        name, opts = _keyword(lines[start])
        if name == 'assembly':
            in_assembly = True
        elif name == 'end assembly':
            in_assembly = False
        if in_assembly and name == 'elset' and str(opts.get('instance', '')).lower() == old_instance.lower():
            ename = str(opts.get('elset', '')).strip()
            is_gen = 'generate' in opts
            old_elsets[ename.lower()] = _parse_ids(lines[start + 1:end], is_gen)

    in_assembly = False
    for start, end in blocks:
        name, opts = _keyword(lines[start])
        if name == 'assembly':
            in_assembly = True
        elif name == 'end assembly':
            in_assembly = False
        if in_assembly and name == 'surface' and str(opts.get('type', '')).upper() == 'ELEMENT':
            surf_name = str(opts.get('name', '')).strip()
            records = []
            for line in lines[start + 1:end]:
                raw = line.strip()
                if raw and not raw.startswith('*') and not raw.startswith('**'):
                    parts = [p.strip() for p in raw.split(',')]
                    if len(parts) >= 2:
                        records.append((parts[0], parts[1].upper()))
            if any(r[0].lower() in old_elsets for r in records) or surf_name.lower() == 'surf-1':
                facets_by_face = {}
                all_facets = set()
                for elset_ref, fid in records:
                    eids = old_elsets.get(elset_ref.lower(), [])
                    if eids:
                        facets_by_face.setdefault(fid, []).extend(eids)
                        for eid in eids:
                            all_facets.add((eid, fid))
                if all_facets:
                    return surf_name, facets_by_face, all_facets
    return None, {}, set()


def clean_old_impact_references(lines, old_instance, enabled):
    """Disable assembly impact surfaces and stale step references if contact is on."""
    old_sets, old_surfaces, affected = set(), set(), set()
    in_assembly = False
    blocks = _blocks(lines)
    for start, end in blocks:
        name, opts = _keyword(lines[start])
        if name == 'assembly':
            in_assembly = True
        if in_assembly and name == 'elset' and str(opts.get('instance', '')).lower() == old_instance.lower():
            old_sets.add(str(opts.get('elset', '')).lower())
            affected.update(range(start, end))
        if name == 'end assembly':
            in_assembly = False
    in_assembly = False
    for start, end in blocks:
        name, opts = _keyword(lines[start])
        if name == 'assembly':
            in_assembly = True
        if in_assembly and name == 'surface':
            data = '\n'.join(lines[start + 1:end]).lower()
            if (old_instance.lower() in (lines[start] + data).lower() or
                    any(re.search(r'(?<![\w-])' + re.escape(s) + r'(?![\w-])', data) for s in old_sets if s)):
                old_surfaces.add(str(opts.get('name', '')).lower())
                affected.update(range(start, end))
        if name == 'end assembly':
            in_assembly = False
    for start, end in blocks:
        name, _ = _keyword(lines[start])
        if name in ('contact inclusions', 'surface property assignment',
                    'contact property assignment', 'contact exclusions'):
            for i in range(start + 1, end):
                fields = [x.strip().lower() for x in lines[i].split(',')]
                if any(x in old_surfaces for x in fields if x):
                    affected.add(i)
    listed = [lines[i].strip() for i in sorted(affected) if lines[i].strip()]
    if enabled:
        return _comment(lines, affected, 'removed plate instance or impact surface'), listed
    return [], listed


def _interactions(lines):
    """Collect interaction names and whether their property block is cohesive."""
    result = []
    current = None
    for line in lines:
        if not line.lstrip().startswith('*') or line.lstrip().startswith('**'):
            continue
        name, opts = _keyword(line)
        if name == 'surface interaction':
            current = [str(opts.get('name', '')).strip(), False]
            result.append(current)
        elif name == 'cohesive behavior' and current is not None:
            current[1] = True
        elif name not in ('friction', 'surface behavior', 'damage initiation',
                          'damage evolution', 'cohesive behavior', 'contact damping',
                          'gap conductance', 'thermal conductance'):
            current = None
    return result


def _limit_inclusions(lines):
    """Remove prior general-contact inclusions so only explicit ball pairs remain."""
    removed = []
    for start, end in _blocks(lines):
        name, opts = _keyword(lines[start])
        if name in ('contact inclusions', 'contact property assignment'):
            removed += _comment(lines, range(start, end), 'replaced by ball-only inclusions')
        elif name == 'contact' and 'all exterior' in opts:
            raise ValueError('plywise ball contact cannot safely extend *Contact, all exterior')
    return removed


def add_plywise_ball_contact(path, old_instance, ball_instance, *, plate=True,
                             fibers=(), fiber=False, thickness='auto', interaction_name=None,
                             ply_thickness=None, ply=None, world_step=None, plies=None,
                             ghost_by_host=None):
    """Add ball contact (element-based and node-based) after plywise writer has produced its deck."""
    if not (plate or fiber):
        return None
    if not ball_instance:
        raise ValueError('--ball-instance is required when node contact is enabled')
    deck = parse_deck(path)
    if ball_instance not in deck.instances:
        raise ValueError(f'ball instance {ball_instance!r} was not found')
    ball_part = deck.parts[deck.instances[ball_instance].part]
    if not ball_part.elements:
        raise ValueError(f'ball instance {ball_instance!r} has no elements')
    hosts = [name for name in deck.instances if re.fullmatch(r'Ply-\d+', name)]
    hosts.sort(key=lambda x: int(x.split('-')[1]))
    if plate and not hosts:
        raise ValueError('no Ply-k instances were found')
    fibers = list(fibers)
    if fiber and not fibers:
        raise ValueError('fiber node contact requested, but no fiber instances were supplied')
    for ref in fibers:
        if ref.instance not in deck.instances:
            raise ValueError(f'fiber instance {ref.instance!r} was not found')
        unknown = set(ref.node_labels) - set(deck.parts[deck.instances[ref.instance].part].nodes)
        if unknown:
            raise ValueError(f'fiber instance {ref.instance!r} has unknown nodes: {sorted(unknown)[:5]}')
    part = deck.parts[deck.instances[hosts[0]].part] if hosts else None
    edge = median_host_edge_length(part.elements, part.nodes) if part else None
    fiber_segment = None
    if fiber:
        lengths = []
        for ref in fibers:
            instance = deck.instances[ref.instance]
            nodes = deck.instance_nodes(ref.instance)
            selected = set(ref.node_labels)
            for elem in deck.parts[instance.part].elements.values():
                conn = elem.connectivity
                if len(conn) >= 2 and conn[0] in selected and conn[1] in selected:
                    lengths.append(float(np.linalg.norm(nodes[conn[1]] - nodes[conn[0]])))
        if lengths:
            fiber_segment = float(np.median(lengths))
        elif isinstance(thickness, str) and thickness.lower() == 'auto':
            raise ValueError('automatic fiber contact thickness needs fiber segment elements')
    plate_t, fiber_t = resolve_contact_thickness(thickness, edge, fiber_segment, plate, fiber)
    lines = Path(path).read_text().splitlines()

    # Detect original element-based impact surface (e.g. Surf-1) before cleaning
    surf_name, facets_by_face, all_facets = _find_plate_impact_surface(lines, old_instance)
    has_surf1 = surf_name is not None and bool(all_facets)
    target_instance = None
    target_side = None
    target_facets = []
    selection_reason = None
    n_plies = plies or len(hosts)

    if has_surf1:
        if ply is not None and 'PLY_BOTTOM' in ply.surfaces and 'PLY_TOP' in ply.surfaces:
            bot_facets = set(ply.surfaces['PLY_BOTTOM'])
            top_facets = set(ply.surfaces['PLY_TOP'])
            ply_nodes_dict = ply.nodes
            ply_elements_dict = ply.elements
        else:
            # Reconstruct bot/top from assembly surfaces Ply-1_bottom and Ply-1_top
            bot_facets = set()
            top_facets = set()
            ply_nodes_dict = deck.instance_nodes(hosts[0])
            ply_elements_dict = part.elements if part else {}
            # Read from lines
            for i, l in enumerate(lines):
                if l.strip().lower() == '*surface, type=element, name=ply-1_bottom':
                    for k in range(i + 1, len(lines)):
                        if lines[k].strip().startswith('*'):
                            break
                        parts = [p.strip() for p in lines[k].split(',')]
                        if len(parts) >= 2:
                            for eid in ply_elements_dict:
                                bot_facets.add((eid, parts[1].upper()))
                elif l.strip().lower() == '*surface, type=element, name=ply-1_top':
                    for k in range(i + 1, len(lines)):
                        if lines[k].strip().startswith('*'):
                            break
                        parts = [p.strip() for p in lines[k].split(',')]
                        if len(parts) >= 2:
                            for eid in ply_elements_dict:
                                top_facets.add((eid, parts[1].upper()))

        matching_bot = all_facets & bot_facets
        matching_top = all_facets & top_facets

        if matching_bot and matching_top:
            step_arr = np.asarray(world_step, float) if world_step is not None else np.array([0., 0., 1.])
            norm_step = np.linalg.norm(step_arr)
            axis = step_arr / (norm_step if norm_step > 0 else 1.0)
            ball_pts = np.array(list(deck.instance_nodes(ball_instance).values()))
            ball_center = np.mean(ball_pts, axis=0)

            bot_pts = [ply_nodes_dict[ply_elements_dict[eid].connectivity[idx]]
                       for eid, fid in bot_facets if eid in ply_elements_dict
                       for idx in HEX_FACES[REV_FACE.get(fid, 0)]]
            bot_center = np.mean(bot_pts, axis=0) if bot_pts else np.zeros(3)
            dist_bot = abs(float(np.dot(ball_center - bot_center, axis)))

            step_full = (n_plies - 1) * step_arr
            top_pts = [ply_nodes_dict[ply_elements_dict[eid].connectivity[idx]] + step_full
                       for eid, fid in top_facets if eid in ply_elements_dict
                       for idx in HEX_FACES[REV_FACE.get(fid, 0)]]
            top_center = np.mean(top_pts, axis=0) if top_pts else np.zeros(3)
            dist_top = abs(float(np.dot(ball_center - top_center, axis)))

            if dist_bot < dist_top:
                target_instance = 'Ply-1'
                target_side = 'bottom'
                target_facets = sorted(bot_facets)
                selection_reason = (
                    f"Surf-1 contains faces on both bottom ({len(matching_bot)}) and top ({len(matching_top)}); "
                    f"stack-bottom is nearest to ball along stack axis (dist {dist_bot:.6g} m vs {dist_top:.6g} m); "
                    f"keeping stack-bottom on Ply-1_bottom"
                )
            else:
                target_instance = f'Ply-{n_plies}'
                target_side = 'top'
                target_facets = sorted(top_facets)
                selection_reason = (
                    f"Surf-1 contains faces on both bottom ({len(matching_bot)}) and top ({len(matching_top)}); "
                    f"stack-top is nearest to ball along stack axis (dist {dist_top:.6g} m vs {dist_bot:.6g} m); "
                    f"keeping stack-top on Ply-{n_plies}_top"
                )
        elif matching_bot:
            target_instance = 'Ply-1'
            target_side = 'bottom'
            target_facets = sorted(bot_facets)
            selection_reason = f"Surf-1 faces sit on stack-bottom face ({len(matching_bot)} faces); assigned to Ply-1_bottom"
        elif matching_top:
            target_instance = f'Ply-{n_plies}'
            target_side = 'top'
            target_facets = sorted(top_facets)
            selection_reason = f"Surf-1 faces sit on stack-top face ({len(matching_top)} faces); assigned to Ply-{n_plies}_top"
        else:
            target_instance = None
            selection_reason = "Surf-1 has no faces matching stack-bottom or stack-top (all side faces dropped)"

    # Clean old impact references and inclusions
    removed_old, stale = clean_old_impact_references(lines, old_instance, True)
    removed_inclusions = _limit_inclusions(lines)

    # Rebuild Surf-1 on target ply
    surf1_assembly_lines = []
    if target_instance and target_facets:
        by_face = {}
        for eid, fid in target_facets:
            by_face.setdefault(fid, []).append(eid)
        for fid in sorted(by_face):
            elset_name = f'_Surf-1_{fid}'
            eids = sorted(by_face[fid])
            if len(eids) >= 3 and eids == list(range(eids[0], eids[-1] + 1)):
                surf1_assembly_lines.append(f'*Elset, elset={elset_name}, internal, instance={target_instance}, generate')
                surf1_assembly_lines.append(f'{eids[0]}, {eids[-1]}, 1')
            else:
                surf1_assembly_lines.append(f'*Elset, elset={elset_name}, internal, instance={target_instance}')
                surf1_assembly_lines.extend(', '.join(map(str, eids[i:i + 16])) for i in range(0, len(eids), 16))
        surf1_assembly_lines.append('*Surface, type=ELEMENT, name=Surf-1')
        surf1_assembly_lines.extend(f'_Surf-1_{fid}, {fid}' for fid in sorted(by_face))

        if ghost_by_host:
            from .plywise_vuel import remap_surface_elsets
            surf1_assembly_lines = remap_surface_elsets(surf1_assembly_lines, ghost_by_host)

    end_assembly = next(i for i, s in enumerate(lines) if s.lstrip().lower() == '*end assembly')
    assembly = _set_lines('Elset', BALL_ELSET, ball_instance, ball_part.elements)
    assembly += [f'*Surface, type=ELEMENT, name={BALL_SURFACE}', f'{BALL_ELSET},']
    pairs, thicknesses = [], []

    # Check if Surf-2 (ball element surface) is present in deck
    has_surf2 = any(l.strip().lower().startswith('*surface') and 'name=surf-2' in l.lower()
                    for l in lines if not l.strip().startswith('**'))

    if target_instance and has_surf2:
        pairs.append(('Surf-1', 'Surf-2'))
        pairs.append(('Surf-2', 'Surf-1'))
        pairs.append(('Surf-1', ''))
        pairs.append(('Surf-2', ''))

    if plate:
        for host in hosts:
            assembly += _set_lines('Nset', PLATE_NSET, host, deck.parts[deck.instances[host].part].nodes)
        assembly += [f'*Surface, type=NODE, name={PLATE_SURFACE}', f'{PLATE_NSET},']
        pairs.append((PLATE_SURFACE, BALL_SURFACE))
        thicknesses.append((PLATE_SURFACE, plate_t))
    if fiber:
        for ref in fibers:
            assembly += _set_lines('Nset', FIBER_NSET, ref.instance, ref.node_labels)
        assembly += [f'*Surface, type=NODE, name={FIBER_SURFACE}', f'{FIBER_NSET},']
        pairs.append((FIBER_SURFACE, BALL_SURFACE))
        thicknesses.append((FIBER_SURFACE, fiber_t))

    lines[end_assembly:end_assembly] = (
        (['** embmesh restored element-based plate impact surface (Surf-1)'] + surf1_assembly_lines
         if surf1_assembly_lines else []) +
        ['** embmesh generated plywise ball-contact surfaces'] + assembly
    )

    available = _interactions(lines)
    if interaction_name:
        matches = [x for x in available if x[0].lower() == interaction_name.lower()]
        if not matches:
            raise ValueError(f'ball interaction {interaction_name!r} was not found')
        if matches[0][1]:
            raise ValueError(f'ball interaction {interaction_name!r} contains *Cohesive Behavior')
        interaction = matches[0][0]
        reused = True
    else:
        safe = next((x for x in available if x[0] and not x[1]), None)
        interaction = safe[0] if safe else CONTACT_INTERACTION
        reused = safe is not None
    if not reused:
        if any(x[0].lower() == interaction.lower() for x in available):
            raise ValueError(f'generated interaction name {interaction!r} already exists')
        step = next(i for i, s in enumerate(lines) if s.lstrip().lower().startswith('*step'))
        lines[step:step] = ['*Surface Interaction, name=' + interaction,
                            '*Friction', '0.0', '*Surface Behavior, pressure-overclosure=HARD']

    lines, extended = _augment_step_contact(lines, pairs, interaction, thicknesses)

    # Format self-contact inclusion lines cleanly without trailing whitespace
    for i in range(len(lines)):
        if lines[i].strip() in ('Surf-1 ,', 'Surf-2 ,'):
            lines[i] = lines[i].strip()

    Path(path).write_text('\n'.join(lines) + '\n')

    element_contact_meta = None
    if target_instance and has_surf2:
        element_contact_meta = dict(
            surface_name='Surf-1',
            target_instance=target_instance,
            target_side=target_side,
            faces=sorted(by_face.keys()),
            element_count=len(target_facets),
            ghost_remapped=bool(ghost_by_host),
            selection_reason=selection_reason,
            four_inclusion_lines_restored=True,
        )

    return dict(ball_instance=ball_instance, plate_instances=hosts if plate else [],
                plate_node_count=sum(len(deck.parts[deck.instances[h].part].nodes) for h in hosts) if plate else 0,
                fiber_instances=[r.instance for r in fibers] if fiber else [],
                fiber_node_count=sum(len(r.node_labels) for r in fibers) if fiber else 0,
                host_median_edge_length=edge, host_edge_source=f'part {part.name}, median of all 12 C3D8 edges' if part else None,
                fiber_median_segment_length=fiber_segment,
                plate_contact_thickness=plate_t, fiber_contact_thickness=fiber_t,
                plate_thickness_ratio=plate_t / ply_thickness if plate_t is not None and ply_thickness else None,
                thickness_note=('auto plate thickness exceeds ply thickness; review with Abaqus' if plate_t is not None and ply_thickness and plate_t > ply_thickness else 'within ply thickness'),
                interaction=interaction, interaction_reused=reused,
                inclusion_pairs=pairs, existing_contact_extended=extended,
                removed_old_references=removed_old, stale_references_found=stale,
                replaced_contact_inclusions=removed_inclusions,
                element_contact=element_contact_meta)
