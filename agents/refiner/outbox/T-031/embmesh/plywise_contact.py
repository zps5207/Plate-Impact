"""Plywise node-to-ball contact, isolated from the legacy single-host path."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import numpy as np

from .contact import (BALL_ELSET, BALL_SURFACE, PLATE_NSET, PLATE_SURFACE,
                      FIBER_NSET, FIBER_SURFACE, CONTACT_INTERACTION,
                      _set_lines, _keyword, _augment_step_contact,
                      median_host_edge_length, resolve_contact_thickness)
from .parser import parse_deck


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
                             ply_thickness=None):
    """Add limited ball contact after the plywise writer has produced its deck."""
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
    removed_old, stale = clean_old_impact_references(lines, old_instance, True)
    removed_inclusions = _limit_inclusions(lines)
    end_assembly = next(i for i, s in enumerate(lines) if s.lstrip().lower() == '*end assembly')
    assembly = _set_lines('Elset', BALL_ELSET, ball_instance, ball_part.elements)
    assembly += [f'*Surface, type=ELEMENT, name={BALL_SURFACE}', f'{BALL_ELSET},']
    pairs, thicknesses = [], []
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
    lines[end_assembly:end_assembly] = ['** embmesh generated plywise ball-contact surfaces'] + assembly
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
    Path(path).write_text('\n'.join(lines) + '\n')
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
                replaced_contact_inclusions=removed_inclusions)
