"""Run and verify both approved T-032 decks using the delivered overlay."""
from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter

import numpy as np

from embmesh.geometry import hex_volume
from embmesh.parser import parse_deck
from embmesh.plywise import _SIGNS, oriented_faces, write_plywise_deck


ROOT = Path(__file__).resolve().parents[5]
TASK = Path(__file__).resolve().parents[1]
CASES = [
    ('original', ROOT / 'Meshing/Flat-curved-p0/Flatv2_curved.inp', {'plies': 10}),
    ('clean', ROOT / 'agents/refiner/outbox/T-024/curved_hostonly.inp', {'ply_thickness': .001}),
]


def volume(part):
    return sum(hex_volume(np.array([part.nodes[n] for n in elem.connectivity]))
               for elem in part.elements.values())


def verify(name, source, kwargs):
    output = TASK / f'{name}_plywise.inp'
    start = perf_counter()
    meta = write_plywise_deck(source, output, **kwargs)
    write_seconds = perf_counter() - start
    original, written = parse_deck(source), parse_deck(output)
    old = original.instances['Plate-1']
    original_part = original.parts[old.part]
    ply_part = written.parts[old.part]
    n = meta['plies']
    step = np.array(meta['stack_vector'])
    direction = step / np.linalg.norm(step)
    old_nodes = original.instance_nodes('Plate-1')
    gap_max = residuals = None
    gaps = []
    residuals = []
    for elem in original_part.elements.values():
        conn = elem.connectivity
        pts = np.array([original_part.nodes[label] for label in conn])
        _, _, pairs = oriented_faces(pts, direction)
        for bottom, top in pairs:
            b, t = conn[bottom], conn[top]
            for k in range(1, n):
                below = written.instances[f'Ply-{k}'].transform(ply_part.nodes[t])
                above = written.instances[f'Ply-{k+1}'].transform(ply_part.nodes[b])
                gaps.append(np.linalg.norm(below - above))
            stacked_top = written.instances[f'Ply-{n}'].transform(ply_part.nodes[t])
            residuals.append(np.linalg.norm(stacked_top - old_nodes[t]))
    source_volume = volume(original_part)
    stacked_volume = n * volume(ply_part)
    report = dict(name=name, source=str(source), output=str(output), metadata=meta,
                  source_volume=source_volume, stacked_volume=stacked_volume,
                  volume_difference=stacked_volume-source_volume,
                  volume_relative_difference=(stacked_volume-source_volume)/source_volume,
                  max_interface_gap=max(gaps),
                  stacked_top_residual_max=max(residuals),
                  stacked_top_residual_mean=float(np.mean(residuals)),
                  stacked_top_residual_p95=float(np.percentile(residuals, 95)),
                  write_seconds=write_seconds, total_seconds=perf_counter()-start)
    (TASK / f'{name}_verification.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    for case in CASES:
        verify(*case)
