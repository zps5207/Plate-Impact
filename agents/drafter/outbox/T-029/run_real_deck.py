"""Generate and audit 4-ply curved deck [0/90/45/-45] for T-029."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import numpy as np
from scipy.spatial import cKDTree

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Load delivered plyfibers directly
import importlib.util
import embmesh

_plyfibers_path = Path(__file__).resolve().parent / "embmesh" / "plyfibers.py"
_spec = importlib.util.spec_from_file_location("embmesh.plyfibers", str(_plyfibers_path))
_mod = importlib.util.module_from_spec(_spec)
sys.modules["embmesh.plyfibers"] = _mod
_spec.loader.exec_module(_mod)

from embmesh.plyfibers import (
    PlyInstanceInfo,
    expand_layup,
    ply_fibers,
    emit_plyfibers_deck,
    append_plyfibers_to_deck,
    format_angle_name,
)
from embmesh.plywise import build_ply_part
from embmesh.parser import parse_deck
from embmesh.geometry import point_in_hex, hex_volume, HEX_FACES


def run_curved_plywise():
    source_inp = REPO_ROOT / "agents" / "refiner" / "outbox" / "T-024" / "curved_hostonly.inp"
    clean_1el_inp = REPO_ROOT / "agents" / "refiner" / "outbox" / "T-023" / "Flatv2_curved_1el.inp"
    out_dir = Path(__file__).resolve().parent / "curved_plywise"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_inp = out_dir / "output.inp"

    # Load 1-element clean curved base plate (2,400 hexes, 10 mm thickness)
    deck1 = parse_deck(clean_1el_inp)
    inst = deck1.instances["Plate-1"]
    part = deck1.parts["Plate"]

    # Partition plate into 4 plies of 2.5 mm each
    n_plies = 4
    ply, meta = build_ply_part(part, plies=n_plies)

    # Bake Plate-1 instance transform into part nodes
    ply_world_nodes = {label: inst.transform(p) for label, p in ply.nodes.items()}
    world_step = inst.transform(np.asarray(meta["step"])) - inst.transform(np.zeros(3))

    angles = expand_layup([0, 90, 45, -45], n_plies)
    diameter = 0.0005  # 0.5 mm <= 2.5 mm ply thickness

    # Create 4 ply instances info
    ply_instances = [
        PlyInstanceInfo(f"Ply-{k}", (k - 1) * world_step)
        for k in range(1, n_plies + 1)
    ]

    # Generate fibers for each distinct angle
    distinct_angles = sorted(set(angles))
    fibers_by_angle = {}
    angle_metas = {}
    for ang in distinct_angles:
        fibs, fmeta = ply_fibers(
            ply.elements,
            ply_world_nodes,
            angle=ang,
            diameter=diameter,
            gap=0.0,
            reference=(1, 0, 0),
            return_meta=True,
        )
        fibers_by_angle[ang] = fibs
        angle_metas[ang] = fmeta

    # Build plywise host deck base lines from curved_hostonly.inp
    raw_lines = source_inp.read_text().splitlines()

    # Replace Plate Part with 1-ply Part (in baked world coordinates)
    def _kw(l): return l.strip().split(",")[0].lower()
    ip_start = next(i for i, l in enumerate(raw_lines) if _kw(l) == "*part" and "name=plate" in l.lower())
    ip_end = next(i for i in range(ip_start + 1, len(raw_lines)) if _kw(raw_lines[i]) == "*end part")

    plate_lines = [
        "*Part, name=Plate",
        "*Node",
    ]
    for nid in sorted(ply_world_nodes):
        p = ply_world_nodes[nid]
        plate_lines.append(f"{nid}, {p[0]:.17g}, {p[1]:.17g}, {p[2]:.17g}")
    plate_lines.append("*Element, type=C3D8R")
    for eid in sorted(ply.elements):
        conn = ply.elements[eid].connectivity
        plate_lines.append(f"{eid}, " + ", ".join(map(str, conn)))
    plate_lines.append("*Elset, elset=PLY")
    eids = sorted(ply.elements)
    for i in range(0, len(eids), 16):
        plate_lines.append(", ".join(map(str, eids[i:i + 16])))
    plate_lines.append("*Solid Section, elset=PLY, controls=EC-1, material=Matrix")
    plate_lines.append(",")
    plate_lines.append("*End Part")

    raw_lines = raw_lines[:ip_start] + plate_lines + raw_lines[ip_end + 1:]

    # Replace Plate-1 instance with Ply-1 .. Ply-4 instances
    ii_start = next(i for i, l in enumerate(raw_lines) if _kw(l) == "*instance" and "name=plate-1" in l.lower())
    ii_end = next(i for i in range(ii_start + 1, len(raw_lines)) if _kw(raw_lines[i]) == "*end instance")

    ply_inst_lines = []
    for pinst in ply_instances:
        ply_inst_lines.append(f"*Instance, name={pinst.name}, part=Plate")
        ply_inst_lines.append(", ".join(f"{v:.17g}" for v in pinst.translation))
        ply_inst_lines.append("*End Instance")

    raw_lines = raw_lines[:ii_start] + ply_inst_lines + raw_lines[ii_end + 1:]

    # Write temporary host-only plywise deck
    temp_deck = out_dir / "temp_host_plywise.inp"
    temp_deck.write_text("\n".join(raw_lines) + "\n")

    # Append fiber parts, instances and embedding constraints
    append_plyfibers_to_deck(
        source_deck=temp_deck,
        output_deck=out_inp,
        ply_instances=ply_instances,
        fibers_by_angle=fibers_by_angle,
        ply_angles=angles,
        diameter=diameter,
    )
    temp_deck.unlink()

    print(f"Written deck: {out_inp}")

    # --- Audit the written deck ---
    written_deck = parse_deck(out_inp)

    # Check instances
    for pinst in ply_instances:
        assert pinst.name in written_deck.instances, f"Missing instance {pinst.name}"

    for k in range(1, n_plies + 1):
        finst_name = f"Fibers-Ply-{k}"
        assert finst_name in written_deck.instances, f"Missing instance {finst_name}"

    # World coordinate containment audit per ply
    target_len = float(np.cbrt(np.median([hex_volume(np.array([ply_world_nodes[n] for n in e.connectivity[:8]])) for e in ply.elements.values()])))

    per_ply_audit = []
    total_nodes = 0
    total_nodes_outside = 0
    total_midpoints = 0
    total_midpoints_outside = 0
    all_segment_lengths = []

    for k, (pinst, ang) in enumerate(zip(ply_instances, angles), start=1):
        # Host hexes in world frame for Ply-k
        host_nodes = written_deck.instance_nodes(pinst.name)
        host_hexes = np.array([
            [host_nodes[n] for n in elem.connectivity[:8]]
            for elem in ply.elements.values()
        ])
        lo = host_hexes.min(axis=1)
        hi = host_hexes.max(axis=1)
        tree = cKDTree(host_hexes.mean(axis=1))

        # Fibers for this ply
        finst_name = f"Fibers-Ply-{k}"
        fib_nodes = written_deck.instance_nodes(finst_name)
        fpart = written_deck.parts[written_deck.instances[finst_name].part]

        points = np.array(list(fib_nodes.values()))
        ends = np.array([(fib_nodes[e.connectivity[0]], fib_nodes[e.connectivity[1]]) for e in fpart.elements.values()])
        midpoints = 0.5 * (ends[:, 0] + ends[:, 1])

        lengths = np.linalg.norm(ends[:, 1] - ends[:, 0], axis=1)
        all_segment_lengths.extend(lengths.tolist())

        bad_points = 0
        for p in points:
            _, ids = tree.query(p, k=16)
            if not any(np.all(p >= lo[j] - 1e-9) and np.all(p <= hi[j] + 1e-9) and point_in_hex(p, host_hexes[j]) for j in ids):
                bad_points += 1

        bad_midpoints = 0
        for mp in midpoints:
            _, ids = tree.query(mp, k=16)
            if not any(np.all(mp >= lo[j] - 1e-9) and np.all(mp <= hi[j] + 1e-9) and point_in_hex(mp, host_hexes[j]) for j in ids):
                bad_midpoints += 1

        ply_info = {
            "ply": pinst.name,
            "angle_deg": float(ang),
            "fiber_part": written_deck.instances[finst_name].part,
            "fiber_instance": finst_name,
            "fiber_nodes": len(points),
            "nodes_outside": bad_points,
            "fiber_segments": len(ends),
            "midpoints_outside": bad_midpoints,
            "shortest_segment_m": float(lengths.min()),
            "median_segment_m": float(np.median(lengths)),
            "longest_segment_m": float(lengths.max()),
            "total_fiber_length_m": float(lengths.sum()),
        }
        per_ply_audit.append(ply_info)
        total_nodes += len(points)
        total_nodes_outside += bad_points
        total_midpoints += len(midpoints)
        total_midpoints_outside += bad_midpoints

    all_segs = np.array(all_segment_lengths)
    overall_report = {
        "source_deck": str(source_inp),
        "written_deck": str(out_inp),
        "plies": n_plies,
        "layup": angles,
        "diameter_m": diameter,
        "ply_thickness_m": float(meta["resulting_ply_thickness"]),
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
        "per_ply": per_ply_audit,
    }

    audit_json = out_dir / "audit.json"
    audit_json.write_text(json.dumps(overall_report, indent=2) + "\n")
    print(json.dumps(overall_report, indent=2))
    return overall_report


if __name__ == "__main__":
    run_curved_plywise()
