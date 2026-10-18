"""Standalone world-coordinate containment audit for plywise deck with embedded fibers."""
from __future__ import annotations

import json
import sys
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from embmesh.parser import parse_deck
from embmesh.geometry import point_in_hex, hex_volume


def audit_deck(deck_path: str | Path, out_json: str | Path | None = None) -> dict:
    deck_path = Path(deck_path)
    deck = parse_deck(deck_path)

    # Find ply instances and fiber instances
    ply_inst_names = sorted(
        [name for name in deck.instances if name.lower().startswith("ply-")],
        key=lambda s: int(s.split("-")[-1]) if s.split("-")[-1].isdigit() else 0,
    )
    if not ply_inst_names:
        raise ValueError("No Ply-* instances found in deck")

    # The ply Part
    ply_part_name = deck.instances[ply_inst_names[0]].part
    ply_part = deck.parts[ply_part_name]

    per_ply = []
    total_nodes = 0
    total_nodes_outside = 0
    total_midpoints = 0
    total_midpoints_outside = 0
    all_lengths = []

    for k, ply_name in enumerate(ply_inst_names, start=1):
        fiber_inst_name = f"Fibers-{ply_name}"
        if fiber_inst_name not in deck.instances:
            # Try alternate naming Fibers-Ply-k
            fiber_inst_name = f"Fibers-Ply-{k}"
        if fiber_inst_name not in deck.instances:
            raise ValueError(f"Could not find matching fiber instance for {ply_name}")

        fiber_inst = deck.instances[fiber_inst_name]
        fpart = deck.parts[fiber_inst.part]

        # Host elements in world frame
        host_nodes = deck.instance_nodes(ply_name)
        host_hexes = np.array([
            [host_nodes[n] for n in elem.connectivity[:8]]
            for elem in ply_part.elements.values()
        ])
        lo = host_hexes.min(axis=1)
        hi = host_hexes.max(axis=1)
        tree = cKDTree(host_hexes.mean(axis=1))

        # Fibers in world frame
        fib_nodes = deck.instance_nodes(fiber_inst_name)
        points = np.array(list(fib_nodes.values()))
        ends = np.array([(fib_nodes[e.connectivity[0]], fib_nodes[e.connectivity[1]]) for e in fpart.elements.values()])
        midpoints = 0.5 * (ends[:, 0] + ends[:, 1])

        lengths = np.linalg.norm(ends[:, 1] - ends[:, 0], axis=1)
        all_lengths.extend(lengths.tolist())

        bad_nodes = 0
        for p in points:
            _, ids = tree.query(p, k=16)
            if not any(np.all(p >= lo[j] - 1e-9) and np.all(p <= hi[j] + 1e-9) and point_in_hex(p, host_hexes[j]) for j in ids):
                bad_nodes += 1

        bad_midpoints = 0
        for mp in midpoints:
            _, ids = tree.query(mp, k=16)
            if not any(np.all(mp >= lo[j] - 1e-9) and np.all(mp <= hi[j] + 1e-9) and point_in_hex(mp, host_hexes[j]) for j in ids):
                bad_midpoints += 1

        info = {
            "ply_instance": ply_name,
            "fiber_instance": fiber_inst_name,
            "fiber_part": fiber_inst.part,
            "fiber_nodes": len(points),
            "nodes_outside": bad_nodes,
            "fiber_segments": len(ends),
            "midpoints_outside": bad_midpoints,
            "shortest_segment_m": float(lengths.min()),
            "median_segment_m": float(np.median(lengths)),
            "longest_segment_m": float(lengths.max()),
            "total_fiber_length_m": float(lengths.sum()),
        }
        per_ply.append(info)
        total_nodes += len(points)
        total_nodes_outside += bad_nodes
        total_midpoints += len(midpoints)
        total_midpoints_outside += bad_midpoints

    all_segs = np.asarray(all_lengths)
    # Target length from ply Part volume
    ref_hexes = np.array([
        [ply_part.nodes[n] for n in elem.connectivity[:8]]
        for elem in ply_part.elements.values()
    ])
    target_len = float(np.cbrt(np.median([hex_volume(h) for h in ref_hexes])))

    report = {
        "deck": str(deck_path),
        "ply_count": len(ply_inst_names),
        "target_segment_length_m": target_len,
        "total_fiber_nodes": total_nodes,
        "total_fiber_nodes_outside": total_nodes_outside,
        "total_fiber_midpoints": total_midpoints,
        "total_fiber_midpoints_outside": total_midpoints_outside,
        "overall_segments": len(all_segs),
        "overall_shortest_segment_m": float(all_segs.min()),
        "overall_median_segment_m": float(np.median(all_segs)),
        "overall_longest_segment_m": float(all_segs.max()),
        "overall_total_length_m": float(all_segs.sum()),
        "segment_length_over_target_min": float(all_segs.min() / target_len),
        "segment_length_over_target_median": float(np.median(all_segs) / target_len),
        "segment_length_over_target_max": float(all_segs.max() / target_len),
        "per_ply": per_ply,
    }

    if out_json:
        Path(out_json).write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    deck = sys.argv[1] if len(sys.argv) > 1 else "outbox/T-029/curved_plywise/output.inp"
    out = sys.argv[2] if len(sys.argv) > 2 else None
    rep = audit_deck(deck, out)
    print(json.dumps(rep, indent=2))
    if rep["total_fiber_nodes_outside"] > 0 or rep["total_fiber_midpoints_outside"] > 0:
        sys.exit(1)
