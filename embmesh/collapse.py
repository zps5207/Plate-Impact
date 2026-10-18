"""Collapse multi-layer plate hex mesh into a single conforming hex layer."""
from __future__ import annotations

from pathlib import Path
import re
import numpy as np

from .errors import MesherInputError
from .geometry import HEX_FACES, hex_volume
from .fibers import pick_thickness_axis
from .model import Part, Element, Deck, Instance
from .parser import parse_deck
from .plywise import oriented_faces, EmbmeshError


def _keyword(line: str) -> str:
    return line.strip().split(',', 1)[0].lower()


def _option(line: str, name: str) -> str | None:
    match = re.search(r'(?:^|,)\s*' + re.escape(name) + r'\s*=\s*([^,]+)', line, re.I)
    return match.group(1).strip() if match else None


def _format_set_block(kw: str, name: str, ids: list[int], instance: str | None = None, internal: bool = False) -> list[str]:
    ids = sorted(set(ids))
    if not ids:
        return []
    opt_inst = f', instance={instance}' if instance else ''
    opt_internal = ', internal' if internal else ''
    is_gen = len(ids) >= 3 and ids == list(range(ids[0], ids[-1] + 1))
    
    if kw.lower() == '*nset':
        hdr = f'*Nset, nset={name}{opt_internal}{opt_inst}' + (', generate' if is_gen else '')
    else:
        hdr = f'*Elset, elset={name}{opt_internal}{opt_inst}' + (', generate' if is_gen else '')
    
    if is_gen:
        return [hdr, f'{ids[0]}, {ids[-1]}, 1']
    lines = [hdr]
    for i in range(0, len(ids), 16):
        lines.append(', '.join(map(str, ids[i:i + 16])))
    return lines


def _parse_data_ids(lines: list[str], is_generate: bool = False) -> list[int]:
    all_vals = []
    for l in lines:
        raw = l.strip()
        if not raw or raw.startswith('**'):
            continue
        for x in raw.split(','):
            x = x.strip()
            if x:
                all_vals.append(int(x))
    if is_generate:
        result = []
        for i in range(0, len(all_vals), 3):
            start = all_vals[i]
            end = all_vals[i + 1]
            step = all_vals[i + 2] if i + 2 < len(all_vals) else 1
            result.extend(range(start, end + 1, step))
        return result
    return all_vals


def _blocks(lines: list[str]) -> list[tuple[int, int]]:
    starts = [i for i, s in enumerate(lines) if s.lstrip().startswith('*') and not s.lstrip().startswith('**')]
    return [(i, starts[k + 1] if k + 1 < len(starts) else len(lines)) for k, i in enumerate(starts)]


def collapse_layers(deck: Deck, instance: str | Instance = 'Plate-1', thickness_axis=None) -> tuple[Part, dict]:
    """Collapse a multi-layer plate Part into a 1-hex-thick Part.

    Parameters
    ----------
    deck : Deck
        Parsed Abaqus input deck.
    instance : str or Instance, default 'Plate-1'
        Target plate assembly instance.
    thickness_axis : str or array-like, optional
        Through-thickness global direction in the part frame (e.g. 'y' or [0, 1, 0]).
        Defaults to shortest bounding box extent via pick_thickness_axis.

    Returns
    -------
    tuple[Part, dict]
        (new_part, report) where new_part is the 1-hex-thick Part and report contains
        volume ratio, layer counts, residuals, and node/element counts.
    """
    inst_name = instance.name if isinstance(instance, Instance) else instance
    if inst_name not in deck.instances:
        raise EmbmeshError(f"instance {inst_name!r} not found in deck")
    inst = deck.instances[inst_name]
    if inst.part not in deck.parts:
        raise EmbmeshError(f"part {inst.part!r} not found in deck")
    part = deck.parts[inst.part]

    if not part.elements or not part.nodes:
        raise EmbmeshError(f"part {part.name!r} has no hex mesh")

    direction = pick_thickness_axis(part.nodes, thickness_axis)

    elem_info = {}
    for elem in part.elements.values():
        if not elem.type.upper().startswith('C3D8') or len(elem.connectivity) != 8:
            raise EmbmeshError(f"element {elem.label} is not a C3D8 hex")
        pts = np.array([part.nodes[n] for n in elem.connectivity])
        bf, tf, local_pairs = oriented_faces(pts, direction)
        c = elem.connectivity
        bot_fn = frozenset(c[i] for i, j in local_pairs)
        top_fn = frozenset(c[j] for i, j in local_pairs)
        elem_info[elem.label] = {
            'pairs': local_pairs,
            'conn': c,
            'map': {c[i]: c[j] for i, j in local_pairs},
            'bot_nodes': bot_fn,
            'top_nodes': top_fn,
            'bot_face': bf,
            'top_face': tf,
        }

    by_bottom: dict[frozenset[int], int] = {}
    by_top: dict[frozenset[int], int] = {}
    for elabel, data in elem_info.items():
        if data['bot_nodes'] in by_bottom:
            raise EmbmeshError(f"Non-manifold mesh: elements {by_bottom[data['bot_nodes']]} and {elabel} share bottom face")
        by_bottom[data['bot_nodes']] = elabel
        if data['top_nodes'] in by_top:
            raise EmbmeshError(f"Non-manifold mesh: elements {by_top[data['top_nodes']]} and {elabel} share top face")
        by_top[data['top_nodes']] = elabel

    all_tops = set(by_top.keys())
    bottom_labels = [elabel for elabel, data in elem_info.items() if data['bot_nodes'] not in all_tops]
    if not bottom_labels:
        raise EmbmeshError("No bottom face found: mesh may be cyclic or empty")

    columns = []
    col_mappings = []
    visited = set()
    for b in sorted(bottom_labels):
        col = [b]
        visited.add(b)
        cur = b
        curr_map = dict(elem_info[b]['map'])
        while elem_info[cur]['top_nodes'] in by_bottom:
            nxt = by_bottom[elem_info[cur]['top_nodes']]
            if nxt in visited:
                raise EmbmeshError(f"Cycle detected in column starting at {b}: element {nxt} visited twice")
            visited.add(nxt)
            g = elem_info[nxt]['map']
            curr_map = {k: g[v] for k, v in curr_map.items()}
            col.append(nxt)
            cur = nxt
        columns.append(col)
        col_mappings.append(curr_map)

    unvisited = set(part.elements.keys()) - visited
    if unvisited:
        raise EmbmeshError(f"{len(unvisited)} elements in part {part.name!r} could not be chained into columns: {sorted(unvisited)[:10]}")

    layer_counts = [len(col) for col in columns]
    min_layers, max_layers = min(layer_counts), max(layer_counts)
    if min_layers != max_layers:
        diff_cols = [f"column with bottom elem {col[0]} has {len(col)} layers" for col in columns if len(col) != min_layers]
        raise EmbmeshError(f"Non-uniform layer count across columns: min={min_layers}, max={max_layers}. Examples: {diff_cols[:5]}")

    new_elements = {}
    new_nodes = {}
    col_elem_map = {}
    col_details = {}
    pair_vectors = []

    for col, col_map in zip(columns, col_mappings):
        e_bot = part.elements[col[0]]
        c_bot = list(e_bot.connectivity)
        local_pairs = elem_info[col[0]]['pairs']
        new_conn = list(c_bot)
        for i, j in local_pairs:
            new_conn[j] = col_map[c_bot[i]]
        
        collapsed_label = e_bot.label
        new_elements[collapsed_label] = Element(
            label=collapsed_label,
            connectivity=tuple(new_conn),
            type=e_bot.type,
            elset=e_bot.elset,
        )
        for eid in col:
            col_elem_map[eid] = collapsed_label

        for n in new_conn:
            new_nodes[n] = part.nodes[n]

        for i, j in local_pairs:
            pair_vectors.append(part.nodes[new_conn[j]] - part.nodes[c_bot[i]])

        detail = {
            'collapsed_label': collapsed_label,
            'column_elements': col,
            'bot_face_nodes': frozenset(c_bot[i] for i, j in local_pairs),
            'top_face_nodes': frozenset(new_conn[j] for i, j in local_pairs),
            'bot_face_id': elem_info[col[0]]['bot_face'],
            'top_face_id': elem_info[col[0]]['top_face'],
            'collapsed_connectivity': tuple(new_conn),
        }
        for eid in col:
            col_details[eid] = detail

    pair_vectors = np.asarray(pair_vectors)
    step_full = np.median(pair_vectors, axis=0)
    mismatches = np.linalg.norm(pair_vectors - step_full, axis=1)

    vol_before = sum(hex_volume([part.nodes[n] for n in e.connectivity]) for e in part.elements.values())
    vol_after = sum(hex_volume([new_nodes[n] for n in e.connectivity]) for e in new_elements.values())
    vol_ratio = float(vol_after / vol_before) if vol_before > 0 else 1.0

    # Part-level sets
    new_nsets = {}
    for name, nset in part.nsets.items():
        surv = set(nset) & set(new_nodes.keys())
        if surv:
            new_nsets[name] = surv
    new_elsets = {}
    for name, elset in part.elsets.items():
        mapped = {col_elem_map[eid] for eid in elset if eid in col_elem_map}
        if mapped:
            new_elsets[name] = mapped

    new_part = Part(
        name=part.name,
        nodes=new_nodes,
        elements=new_elements,
        nsets=new_nsets,
        elsets=new_elsets,
    )

    report = {
        'instance': inst_name,
        'part': part.name,
        'thickness_axis': direction.tolist(),
        'columns': len(columns),
        'layers_per_column_min': min_layers,
        'layers_per_column_max': max_layers,
        'elements_before': len(part.elements),
        'elements_after': len(new_elements),
        'nodes_before': len(part.nodes),
        'nodes_after': len(new_nodes),
        'volume_before': float(vol_before),
        'volume_after': float(vol_after),
        'volume_ratio': vol_ratio,
        'stack_vector': step_full.tolist(),
        'residual_max': float(mismatches.max()),
        'residual_mean': float(mismatches.mean()),
        'residual_p95': float(np.percentile(mismatches, 95)),
        'dropped_side_faces': {},
        'surviving_faces': {},
        'nsets_rewritten': [],
        'elsets_rewritten': [],
        '_col_elem_map': col_elem_map,
        '_col_details': col_details,
    }

    return new_part, report


def collapse_deck_text(lines: list[str] | str, deck: Deck, instance: str | Instance = 'Plate-1', thickness_axis=None) -> tuple[list[str], dict]:
    """Replace plate part and rewrite sets and surfaces referencing collapsed elements."""
    if isinstance(lines, str):
        lines = lines.splitlines()
    else:
        lines = list(lines)

    inst_name = instance.name if isinstance(instance, Instance) else instance
    if inst_name not in deck.instances:
        raise EmbmeshError(f"instance {inst_name!r} not found in deck")
    inst = deck.instances[inst_name]
    part = deck.parts[inst.part]

    new_part, report = collapse_layers(deck, instance, thickness_axis)
    col_elem_map = report['_col_elem_map']
    col_details = report['_col_details']
    surviving_nodes = set(new_part.nodes.keys())

    # Pre-parse assembly-level elsets on instance and surfaces on instance
    blocks = _blocks(lines)
    assembly_elsets_on_inst: dict[str, list[int]] = {}
    surface_blocks_to_rewrite: dict[str, dict] = {}
    elsets_belonging_to_surfaces = set()

    in_assembly = False
    for start, end in blocks:
        hdr = lines[start]
        kw = _keyword(hdr)
        if kw == '*assembly':
            in_assembly = True
            continue
        elif kw == '*end assembly':
            in_assembly = False
            continue
        if not in_assembly:
            continue

        if kw == '*elset':
            inst_opt = _option(hdr, 'instance')
            if (inst_opt or '').lower() == inst_name.lower():
                set_name = (_option(hdr, 'elset') or '').strip()
                is_gen = 'generate' in hdr.lower()
                eids = _parse_data_ids(lines[start + 1:end], is_generate=is_gen)
                assembly_elsets_on_inst[set_name.lower()] = eids

    # Find element-based surfaces referencing instance or its elsets
    in_assembly = False
    for start, end in blocks:
        hdr = lines[start]
        kw = _keyword(hdr)
        if kw == '*assembly':
            in_assembly = True
            continue
        elif kw == '*end assembly':
            in_assembly = False
            continue
        if not in_assembly:
            continue

        if kw == '*surface':
            stype = _option(hdr, 'type')
            if stype and stype.upper() == 'ELEMENT':
                surf_name = (_option(hdr, 'name') or '').strip()
                entries = []
                is_plate_surf = False
                for line in lines[start + 1:end]:
                    raw = line.strip()
                    if not raw or raw.startswith('**'):
                        continue
                    parts = [p.strip() for p in raw.split(',')]
                    if len(parts) >= 2:
                        ref = parts[0]
                        fid = parts[1].upper()
                        entries.append((ref, fid))
                        if ref.lower() in assembly_elsets_on_inst:
                            is_plate_surf = True
                        elif ref.isdigit() and int(ref) in col_elem_map:
                            is_plate_surf = True

                if is_plate_surf:
                    surface_blocks_to_rewrite[surf_name.lower()] = {
                        'name': surf_name,
                        'entries': entries,
                        'start': start,
                        'end': end,
                    }
                    for ref, _ in entries:
                        if ref.lower() in assembly_elsets_on_inst:
                            elsets_belonging_to_surfaces.add(ref.lower())

    # Map surfaces
    for s_low, s_info in surface_blocks_to_rewrite.items():
        surf_name = s_info['name']
        surviving_by_face: dict[str, set[int]] = {}
        dropped_side = 0
        for ref, face_id in s_info['entries']:
            if ref.lower() in assembly_elsets_on_inst:
                eids = assembly_elsets_on_inst[ref.lower()]
            elif ref.isdigit() and int(ref) in col_elem_map:
                eids = [int(ref)]
            else:
                continue

            face_idx = int(face_id[1:]) - 1 if (face_id.startswith('S') and face_id[1:].isdigit()) else None
            if face_idx is None or face_idx >= len(HEX_FACES):
                continue
            local_face = HEX_FACES[face_idx]

            for eid in eids:
                if eid not in part.elements:
                    continue
                orig_elem = part.elements[eid]
                fn = frozenset(orig_elem.connectivity[idx] for idx in local_face)
                cd = col_details.get(eid)
                if not cd:
                    continue
                if fn == cd['bot_face_nodes']:
                    surviving_by_face.setdefault(cd['bot_face_id'], set()).add(cd['collapsed_label'])
                elif fn == cd['top_face_nodes']:
                    surviving_by_face.setdefault(cd['top_face_id'], set()).add(cd['collapsed_label'])
                else:
                    dropped_side += 1

        s_info['surviving_by_face'] = {fid: sorted(elems) for fid, elems in surviving_by_face.items()}
        s_info['dropped_side'] = dropped_side
        report['surviving_faces'][surf_name] = {fid: len(elems) for fid, elems in s_info['surviving_by_face'].items()}
        report['dropped_side_faces'][surf_name] = dropped_side

    # Now assemble rewritten lines block by block
    result_lines = []
    in_part = False
    target_part = False
    in_assembly = False

    # Preamble lines before first block
    first_block_start = blocks[0][0] if blocks else len(lines)
    result_lines.extend(lines[:first_block_start])

    for start, end in blocks:
        hdr = lines[start]
        kw = _keyword(hdr)
        data = lines[start + 1:end]

        if kw == '*part':
            in_part = True
            pname = _option(hdr, 'name') or ''
            target_part = pname.lower() == part.name.lower()
            result_lines.append(hdr)
            continue
        elif kw == '*end part':
            in_part = False
            target_part = False
            result_lines.append(hdr)
            continue

        if in_part and target_part:
            if kw == '*node':
                result_lines.append('*Node')
                for nid, p in sorted(new_part.nodes.items()):
                    result_lines.append(f'{nid}, {p[0]:.17g}, {p[1]:.17g}, {p[2]:.17g}')
                continue
            elif kw == '*element':
                result_lines.append(hdr)
                for eid, elem in sorted(new_part.elements.items()):
                    result_lines.append(f'{eid}, ' + ', '.join(map(str, elem.connectivity)))
                continue
            elif kw == '*nset':
                nname = _option(hdr, 'nset') or ''
                internal = 'internal' in hdr.lower()
                is_gen = 'generate' in hdr.lower()
                raw_ids = _parse_data_ids(data, is_generate=is_gen)
                surv = [nid for nid in raw_ids if nid in surviving_nodes]
                if surv:
                    result_lines.extend(_format_set_block('*Nset', nname, surv, internal=internal))
                    report['nsets_rewritten'].append(nname)
                continue
            elif kw == '*elset':
                ename = _option(hdr, 'elset') or ''
                internal = 'internal' in hdr.lower()
                is_gen = 'generate' in hdr.lower()
                raw_ids = _parse_data_ids(data, is_generate=is_gen)
                mapped = sorted({col_elem_map[eid] for eid in raw_ids if eid in col_elem_map})
                if mapped:
                    result_lines.extend(_format_set_block('*Elset', ename, mapped, internal=internal))
                    report['elsets_rewritten'].append(ename)
                continue
            else:
                result_lines.append(hdr)
                result_lines.extend(data)
                continue

        if kw == '*assembly':
            in_assembly = True
            result_lines.append(hdr)
            continue
        elif kw == '*end assembly':
            in_assembly = False
            result_lines.append(hdr)
            continue

        if in_assembly:
            if kw == '*nset':
                inst_opt = _option(hdr, 'instance')
                if (inst_opt or '').lower() == inst_name.lower():
                    nname = _option(hdr, 'nset') or ''
                    internal = 'internal' in hdr.lower()
                    is_gen = 'generate' in hdr.lower()
                    raw_ids = _parse_data_ids(data, is_generate=is_gen)
                    surv = [nid for nid in raw_ids if nid in surviving_nodes]
                    if surv:
                        result_lines.extend(_format_set_block('*Nset', nname, surv, instance=inst_name, internal=internal))
                        report['nsets_rewritten'].append(f"{nname} (instance={inst_name})")
                    continue
            elif kw == '*elset':
                inst_opt = _option(hdr, 'instance')
                if (inst_opt or '').lower() == inst_name.lower():
                    ename = _option(hdr, 'elset') or ''
                    if ename.lower() in elsets_belonging_to_surfaces:
                        # Omit here; emitted together with *Surface
                        continue
                    internal = 'internal' in hdr.lower()
                    is_gen = 'generate' in hdr.lower()
                    raw_ids = _parse_data_ids(data, is_generate=is_gen)
                    mapped = sorted({col_elem_map[eid] for eid in raw_ids if eid in col_elem_map})
                    if mapped:
                        result_lines.extend(_format_set_block('*Elset', ename, mapped, instance=inst_name, internal=internal))
                        report['elsets_rewritten'].append(f"{ename} (instance={inst_name})")
                    continue
            elif kw == '*surface':
                sname = (_option(hdr, 'name') or '').strip()
                if sname.lower() in surface_blocks_to_rewrite:
                    s_info = surface_blocks_to_rewrite[sname.lower()]
                    surf_name = s_info['name']
                    # Emit elsets for surviving faces
                    for fid, elems in sorted(s_info['surviving_by_face'].items()):
                        result_lines.extend(_format_set_block(
                            '*Elset', f"_{surf_name}_{fid}", elems, instance=inst_name, internal=True
                        ))
                    result_lines.append(f'*Surface, type=ELEMENT, name={surf_name}')
                    for fid in sorted(s_info['surviving_by_face'].keys()):
                        result_lines.append(f'_{surf_name}_{fid}, {fid}')
                    continue

        # Untouched block (e.g. Ball, Step, Material, Boundary, etc.)
        result_lines.append(hdr)
        result_lines.extend(data)

    return result_lines, report


def collapse_deck(source: str | Path, output: str | Path, instance: str | Instance = 'Plate-1', thickness_axis=None) -> dict:
    """Read a multi-layer deck from source, collapse its plate part to 1 hex, and write to output."""
    src = Path(source)
    lines = src.read_text().splitlines()
    deck = parse_deck(src)
    new_lines, report = collapse_deck_text(lines, deck, instance=instance, thickness_axis=thickness_axis)
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text('\n'.join(new_lines) + '\n')
    return {k: v for k, v in report.items() if not k.startswith('_')}
