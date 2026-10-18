"""VU1/ghost conversion and per-instance fields for translated ply stacks."""
from __future__ import annotations

import re
import numpy as np

from .parser import parse_deck
from .volume import fiber_volume_rows
from .symmetry import boundary_symmetry_sets, fiber_nodes_on_symmetry
from .vuelghost import (VuelGhostOptions, convert_to_vuel_ghost,
                        _initial_solution_lines, _instance_set_lines,
                        GHOST_DIAGNOSTIC_ELSET, VUEL_DIAGNOSTICS_ELSET,
                        GHOST_ELSET)


def convert_plywise_hosts(lines, ply, angles, fibers_by_angle, diameter, options=None):
    """Convert the common Part once, then emit fields/sets for every instance."""
    options = options or VuelGhostOptions()
    fractions_by_angle = {
        angle: {row[0]: row[3] for row in fiber_volume_rows(
            ply.elements, ply.nodes, fibers_by_angle[angle], diameter)}
        for angle in sorted(set(angles))
    }
    deck = parse_deck('\n'.join(lines))
    first = 'Ply-1'
    converted, ghost_by_host, metadata = convert_to_vuel_ghost(
        lines, deck, first, ply.elements, fractions_by_angle[angles[0]], options)
    # The solid converter handles the first instance. Mirror its surface remap
    # and diagnostics for the remaining instances without touching that path.
    surface_sets = set()
    for i, line in enumerate(converted):
        if line.lower().startswith('*surface,') and 'type=element' in line.lower():
            j = i + 1
            while j < len(converted) and not converted[j].startswith('*'):
                if converted[j].strip() and not converted[j].startswith('**'):
                    surface_sets.add(converted[j].split(',')[0].strip().lower())
                j += 1
    result = []
    i = 0
    while i < len(converted):
        line = converted[i]
        if line.lower().startswith('*elset,') and 'instance=ply-' in line.lower():
            m = re.search(r'instance\s*=\s*(Ply-\d+)', line, re.I)
            name = re.search(r'elset\s*=\s*([^,]+)', line, re.I)
            if m and name and m.group(1).lower() != 'ply-1' and name.group(1).strip().lower() in surface_sets:
                j = i + 1
                while j < len(converted) and not converted[j].startswith('*'):
                    j += 1
                values = [int(x.strip()) for row in converted[i + 1:j] if not row.startswith('**')
                          for x in row.split(',') if x.strip()]
                if re.search(r',\s*generate\b', line, re.I):
                    values = list(range(values[0], values[1] + 1, values[2] if len(values) > 2 else 1))
                result.append(re.sub(r',\s*generate\b', '', line, flags=re.I))
                mapped = [ghost_by_host.get(v, v) for v in values]
                result.extend(', '.join(map(str, mapped[k:k + 16])) for k in range(0, len(mapped), 16))
                i = j
                continue
        if line.lower().startswith('*end assembly'):
            for k in range(2, len(angles) + 1):
                instance = f'Ply-{k}'
                result.extend(_instance_set_lines(GHOST_DIAGNOSTIC_ELSET, instance, ghost_by_host.values()))
                result.extend(_instance_set_lines(VUEL_DIAGNOSTICS_ELSET, instance, ghost_by_host.keys()))
        result.append(line)
        if line.lower().startswith('*end assembly'):
            for k, angle in enumerate(angles[1:], start=2):
                result.extend(_initial_solution_lines(f'Ply-{k}', fractions_by_angle[angle]))
        i += 1
    metadata['vuel_elements_per_ply'] = len(ghost_by_host)
    metadata['ghost_elements_per_ply'] = len(ghost_by_host)
    metadata['total_vuel_elements'] = len(ghost_by_host) * len(angles)
    metadata['total_ghost_elements'] = len(ghost_by_host) * len(angles)
    metadata['per_ply_fractions'] = {
        f'Ply-{k}': {'min': float(min(fractions_by_angle[a].values())),
                     'max': float(max(fractions_by_angle[a].values())),
                     'mean': float(np.mean(list(fractions_by_angle[a].values()))),
                     'at_or_above_one': int(sum(v >= 1 for v in fractions_by_angle[a].values()))}
        for k, a in enumerate(angles, 1)
    }
    return result, ghost_by_host, metadata


def finish_plywise_fibers(lines, source_deck, source_instance, angles, fibers_by_angle,
                          ply_step, ghost_mode):
    """Point embedding at ghosts and propagate planar host symmetry to fibers."""
    deck = parse_deck(source_deck)
    constraints = boundary_symmetry_sets(deck, source_instance)
    # Abaqus commonly declares X/Y sets in the Assembly rather than the Part.
    # The solid helper recognizes Part sets; collect planar assembly sets here.
    raw = deck.original_lines
    for axis, name in enumerate(('X', 'Y')):
        if name in constraints:
            continue
        if not any(row.strip().lower() == f'{name.lower()}, {name.lower()}symm' for row in raw):
            continue
        labels = []
        for i, row in enumerate(raw):
            if row.lower().startswith('*nset,') and re.search(rf'\bnset\s*=\s*{name}\s*(?:,|$)', row, re.I) and re.search(rf'\binstance\s*=\s*{re.escape(source_instance)}\s*(?:,|$)', row, re.I):
                j = i + 1
                vals = []
                while j < len(raw) and not raw[j].startswith('*'):
                    vals.extend(int(v) for v in raw[j].split(',') if v.strip() and not raw[j].startswith('**'))
                    j += 1
                labels.extend(range(vals[0], vals[1] + 1, vals[2] if len(vals) > 2 else 1)
                              if 'generate' in row.lower() else vals)
        points = deck.instance_nodes(source_instance)
        coords = [points[n][axis] for n in labels if n in points]
        if coords and max(coords) - min(coords) <= 1e-8:
            constraints[name] = (axis, float(np.median(coords)))
    result = []
    counts = {}
    for line in lines:
        if ghost_mode and line.lower().startswith('*embedded element, host elset=ply-'):
            line = re.sub(r'(?i)\.PLY\s*$', f'.{GHOST_ELSET}', line)
        if line.lower().startswith('*end assembly'):
            for k, angle in enumerate(angles, 1):
                offset = 100000 + sorted(set(angles)).index(angle) * 100000
                translated = {name: (axis, coordinate - (k - 1) * ply_step[axis])
                              for name, (axis, coordinate) in constraints.items()}
                nodes = fiber_nodes_on_symmetry(fibers_by_angle[angle], offset, translated)
                counts[f'Ply-{k}'] = {name: len(ids) for name, ids in nodes.items()}
                for name, ids in nodes.items():
                    set_name = f'EMBMESH_PLY{k}_{name}_FIBER_SYMM'
                    result.append(f'*Nset, nset={set_name}, instance=Fibers-Ply-{k}')
                    result.extend(', '.join(map(str, ids[j:j + 16])) for j in range(0, len(ids), 16))
        result.append(line)
    # Boundary blocks are step data. Add them immediately before the first
    # *End Step so each named assembly set receives the source set's DOF.
    boundary = []
    for k, names in counts.items():
        ply_number = k.split('-')[1]
        for name, count in names.items():
            if count:
                axis = constraints[name][0] + 1
                boundary.extend(['*Boundary', f'EMBMESH_PLY{ply_number}_{name}_FIBER_SYMM, {axis}, {axis}, 0.'])
    if boundary:
        end = next(i for i, line in enumerate(result) if line.lower().startswith('*end step'))
        result[end:end] = boundary
    return result, counts
