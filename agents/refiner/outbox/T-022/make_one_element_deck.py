"""Reduce curved Flatv2 to its real top-face C-mesh and a translated bottom.

Coordinates remain in the Plate PART frame (thickness = Y). The source's
opposite outer layers drift in XZ, so exact translation requires replacing its
bottom coordinates with top coordinates - (0, .01, 0).
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from embmesh.parser import parse_deck
from embmesh.geometry import hex_center_jacobian


def blocks(lines):
    starts = [i for i, x in enumerate(lines) if x.lstrip().startswith('*') and not x.lstrip().startswith('**')]
    for j, a in enumerate(starts):
        yield a, starts[j+1] if j+1 < len(starts) else len(lines), lines[a].strip().split(',')[0].lower()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('source', type=Path)
    ap.add_argument('output', type=Path)
    args = ap.parse_args()
    deck = parse_deck(args.source)
    part = deck.parts['Plate']
    labels = np.array(sorted(part.nodes))
    xyz = np.array([part.nodes[int(n)] for n in labels])
    sag = .25 - np.sqrt(.25**2 - xyz[:, 0]**2 - xyz[:, 2]**2)
    layer_float = (xyz[:, 1] - sag - .01) / .001
    layer = np.rint(layer_float).astype(int)
    if np.max(abs(layer_float-layer)) > 1e-3:
        raise ValueError('cannot identify source thickness levels')
    level = dict(zip(labels.tolist(), layer.tolist()))
    top_old = labels[layer == 10].tolist()
    bot_old = labels[layer == 0].tolist()
    if len(top_old) != 2491 or len(bot_old) != 2491:
        raise ValueError('unexpected outer node counts')
    top_idx = {old: i+1 for i, old in enumerate(top_old)}
    n_top = len(top_old)
    top = np.array([part.nodes[n] for n in top_old])
    bot = top - np.array([0, .01, 0])
    source_bot = np.array([part.nodes[n] for n in bot_old])
    drift, _ = cKDTree(source_bot[:, [0, 2]]).query(top[:, [0, 2]])
    quads = []
    for e in part.elements.values():
        face = [n for n in e.connectivity if level[n] == 10]
        if len(face) != 4:
            continue
        c = np.mean([part.nodes[n][[0, 2]] for n in face], axis=0)
        face.sort(key=lambda n: np.arctan2(*(part.nodes[n][[0, 2]]-c)[::-1]))
        ids = [top_idx[n] for n in face]
        # Internal ordering accepted by embmesh.geometry; choose positive J.
        p = np.vstack((top[np.array(ids)-1], bot[np.array(ids)-1]))
        if hex_center_jacobian(p) < 0:
            ids = [ids[0], ids[3], ids[2], ids[1]]
        quads.append(ids)
    if len(quads) != 2400:
        raise ValueError(f'expected 2400 top quads, got {len(quads)}')
    node_lines = ['*Node']
    for i, q in enumerate(np.vstack((top, bot)), 1):
        node_lines.append(f'{i}, {q[0]:.12g}, {q[1]:.12g}, {q[2]:.12g}')
    elem_lines = ['*Element, type=C3D8R']
    for i, face in enumerate(quads, 1):
        elem_lines.append(f'{i}, '+', '.join(map(str, face+[n+n_top for n in face])))
    plate = ['*Part, name=Plate'] + node_lines + elem_lines + [
        '*Nset, nset=Plate, generate', f'1, {2*n_top}, 1',
        '*Elset, elset=Plate, generate', '1, 2400, 1',
        '*Solid Section, elset=Plate, controls=EC-1, material=Matrix', ',', '*End Part']
    # Remap original assembly node sets by nearest projected top vertex. This
    # preserves the original named boundary conditions on both outer faces.
    tree = cKDTree(top[:, [0, 2]])
    lines = args.source.read_text().splitlines()
    old_plate_nsets = defaultdict(set)
    for a,z,k in blocks(lines):
        if k != '*nset' or 'instance=plate-1' not in lines[a].lower():
            continue
        name = next((part.split('=',1)[1].strip() for part in lines[a].split(',') if 'nset=' in part.lower()), '')
        for row in lines[a+1:z]:
            if row.strip() and not row.lstrip().startswith('**'):
                old_plate_nsets[name].update(int(v) for v in row.split(',') if v.strip())
    plate_nsets = defaultdict(set)
    for name in ('Outside', 'X', 'Y', 'plate'):
        old = old_plate_nsets.get(name, set())
        for n in old:
            idx = int(tree.query(part.nodes[n][[0, 2]])[1])+1
            plate_nsets[name].update((idx, idx+n_top))
    plate_nsets['plate'].update(range(1, 2*n_top+1))
    def set_lines(kind, name, vals):
        out = [f'*{kind}, {kind.lower()}={name}, instance=Plate-1']
        data = sorted(vals)
        out += [', '.join(map(str, data[i:i+16])) for i in range(0, len(data), 16)]
        return out
    assembly_extra = []
    for name, vals in plate_nsets.items():
        assembly_extra += set_lines('Nset', name, vals)
    assembly_extra += set_lines('Elset', 'plate', range(1, 2401))
    # Contact on the top and all outer lateral faces. The Ball surface is kept.
    faces = [(0,1,2,3), (4,7,6,5), (0,4,5,1), (1,5,6,2), (2,6,7,3), (3,7,4,0)]
    occurrences = defaultdict(list)
    for eid, q in enumerate(quads, 1):
        conn = q + [n+n_top for n in q]
        for fid, inds in enumerate(faces, 1):
            occurrences[tuple(sorted(conn[j] for j in inds))].append((eid, fid))
    surf = defaultdict(list)
    for uses in occurrences.values():
        if len(uses) == 1 and uses[0][1] != 2:
            eid, fid = uses[0]
            surf[fid].append(eid)
    for fid, vals in sorted(surf.items()):
        assembly_extra += set_lines('Elset', f'_Surf-1_S{fid}', vals)
    assembly_extra += ['*Surface, type=ELEMENT, name=Surf-1']
    assembly_extra += [f'_Surf-1_S{fid}, S{fid}' for fid in sorted(surf)]
    b = list(blocks(lines))
    plate_start = next(a for a, _, k in b if k == '*part' and 'name=plate' in lines[a].lower())
    plate_end = next(z for a, z, k in b if a >= plate_start and k == '*end part')
    asm_start = next(a for a, _, k in b if k == '*assembly')
    asm_end = next(z for a, z, k in b if a >= asm_start and k == '*end assembly')
    # Retain only original Ball-1 set/surface blocks in the assembly; Plate
    # definitions are rebuilt, and original Surf-1 gets replaced.
    orig_asm = lines[asm_start:asm_end]
    ab = list(blocks(orig_asm))
    kept = []
    for a, z, k in ab:
        head = orig_asm[a].lower()
        if k == '*assembly' or k == '*end assembly' or k == '*instance' or k == '*end instance':
            kept += orig_asm[a:z]
        elif k in ('*nset','*elset') and 'instance=ball-1' in head:
            kept += orig_asm[a:z]
        elif k == '*surface' and 'name=surf-2' in head:
            kept += orig_asm[a:z]
    # Insert before End Assembly.
    end_at = next(i for i,x in enumerate(kept) if x.lower().startswith('*end assembly'))
    kept[end_at:end_at] = assembly_extra
    output = lines[:plate_start] + plate + lines[plate_end:asm_start] + kept + lines[asm_end:]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text('\n'.join(output)+'\n')
    stack_dev=float(np.max(np.linalg.norm((bot-top)-np.array([0,-.01,0]),axis=1)))
    report = dict(source_outer_projection_drift_max_m=float(drift.max()),
                  source_outer_projection_drift_p95_m=float(np.quantile(drift,.95)),
                  source_outer_projection_drift_median_m=float(np.median(drift)),
                  stack_vector_m=[0,-.01,0], stack_deviation_max_m=stack_dev,
                  cells=len(quads), top_nodes=n_top, new_nodes=2*n_top,
                  surface_faces={str(k):len(v) for k,v in surf.items()},
                  note='Bottom face reconstructed by translating real top face; not the source bottom coordinates.')
    args.output.with_suffix('.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
