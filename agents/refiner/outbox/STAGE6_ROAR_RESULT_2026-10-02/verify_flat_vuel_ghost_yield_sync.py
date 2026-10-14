"""Static, scale-aware checks for the Stage-6 Flat VUEL+ghost handoff deck."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path


def keyword(line):
    fields = [x.strip() for x in line[1:].split(",")]
    opts = {}
    for field in fields[1:]:
        if "=" in field:
            key, value = field.split("=", 1)
            opts[key.strip().lower()] = value.strip()
    return fields[0].lower(), opts


def data_after(lines, index):
    result = []
    index += 1
    while index < len(lines) and not lines[index].lstrip().startswith("*"):
        if lines[index].strip():
            result.append(lines[index].strip())
        index += 1
    return result


def element_block(lines, marker):
    index = lines.index(marker)
    result = {}
    for line in data_after(lines, index):
        values = [int(x.strip()) for x in line.split(",") if x.strip()]
        result[values[0]] = tuple(values[1:])
    return result


def material_data(lines, marker):
    index = lines.index(marker) + 1
    result = {}
    active = None
    while index < len(lines):
        line = lines[index].strip()
        if line.lower().startswith("*material") or line.lower().startswith("*step"):
            break
        if line.startswith("*") and not line.startswith("**"):
            active = keyword(line)[0]
            result.setdefault(active, [])
        elif active and line and not line.startswith("**"):
            result[active].append([float(x.strip()) for x in line.split(",") if x.strip()])
        index += 1
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("deck", type=Path)
    parser.add_argument("volume_csv", type=Path)
    parser.add_argument("reference_fibers", type=Path)
    parser.add_argument("generated_fibers", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    lines = args.deck.read_text().splitlines()
    with args.volume_csv.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    fractions = {int(row["element_label"]): float(row["volume_fraction"]) for row in rows}
    host_volumes = {int(row["element_label"]): float(row["host_volume"]) for row in rows}

    vuels = element_block(lines, "*Element, type=VU1, elset=EMBMESH_VUEL_HOST")
    ghosts = element_block(lines, "*Element, type=C3D8R, elset=EMBMESH_GHOST_HOST")
    ghost_offset = min(ghosts) - min(vuels)
    paired = all(ghosts.get(label + ghost_offset) == connectivity for label, connectivity in vuels.items())

    prop_index = lines.index("*UEL Property, elset=EMBMESH_VUEL_HOST")
    prop_lines = data_after(lines, prop_index)
    props = [float(x.strip()) for line in prop_lines for x in line.split(",") if x.strip()]
    ghost_material = material_data(lines, "*Material, name=EMBMESH_GHOST_MATERIAL")

    embed_index = lines.index("*Elset, elset=EMBMESH_HOST, instance=Plate-1")
    embed_labels = {
        int(x.strip())
        for line in data_after(lines, embed_index)
        for x in line.split(",") if x.strip()
    }

    initial_index = lines.index("*Initial Conditions, type=SOLUTION") + 1
    initial_values = {}
    i = initial_index
    while i < len(lines) and not lines[i].lstrip().startswith("*"):
        first = [x.strip() for x in lines[i].split(",") if x.strip()]
        label = int(first[0].rsplit(".", 1)[1])
        values = [float(x) for x in first[1:]]
        i += 1
        while len(values) < 107:
            values.extend(float(x.strip()) for x in lines[i].split(",") if x.strip())
            i += 1
        initial_values[label] = values

    max_fraction_error = max(
        abs(initial_values[label][106] - fraction) for label, fraction in fractions.items()
    )
    nonzero_reserved = sum(
        1 for values in initial_values.values() for value in values[:106] if value != 0.0
    )
    real_mass = sum(host_volumes.values()) * props[2]
    expected_ghost_mass = sum(host_volumes.values()) * props[2] * 1.0e-4

    ref_hash = hashlib.sha256(args.reference_fibers.read_bytes()).hexdigest()
    generated_hash = hashlib.sha256(args.generated_fibers.read_bytes()).hexdigest()
    checks = {
        "vuel_count_24000": len(vuels) == 24000,
        "ghost_count_24000": len(ghosts) == 24000,
        "node_identical_pairs": paired,
        "ghost_labels_24001_48000": min(ghosts) == 24001 and max(ghosts) == 48000,
        "embedded_elset_is_all_ghosts": embed_labels == set(ghosts),
        "properties_13": len(props) == 13,
        "uel_property_max_8_per_line": max(len([x for x in line.split(",") if x.strip()]) for line in prop_lines) <= 8,
        "svar107_count_24000": len(initial_values) == 24000,
        "svar1_to_106_zero": nonzero_reserved == 0,
        "svar107_matches_csv": max_fraction_error <= 5e-15,
        "reference_fibers_identical": ref_hash == generated_hash,
        "vuel_type_starts_vu": any(line.startswith("*User Element, type=VU1") for line in lines),
        "ghost_deletion_enabled": any(
            line.lower().startswith("*section controls, name=embmesh_ghost_controls")
            and "element deletion=yes" in line.lower() for line in lines
        ),
        "ghost_density_scaled_1e-4": abs(ghost_material["density"][0][0] / props[2] - 1e-4) <= 1e-15,
        "ghost_modulus_scaled_1e-4": abs(ghost_material["elastic"][0][0] / props[0] - 1e-4) <= 1e-15,
        "ghost_yield_scaled_1e-4": abs(ghost_material["plastic"][0][0] / props[7] - 1e-4) <= 1e-15,
        "ghost_poisson_preserved": ghost_material["elastic"][0][1] == props[1],
        "ghost_ductile_threshold_zero": ghost_material["damage initiation"][0][0] == 0.0,
        "vuel_eps_matches_stvk_yield_equivalent": abs(
            props[6] - (math.sqrt(1.0 + 2.0 * props[7] / props[0]) - 1.0)
        ) <= 1e-14,
        "ghost_zero_displacement_evolution": ghost_material["damage evolution"][0][0] == 0.0,
    }
    result = {
        "pass": all(checks.values()),
        "checks": checks,
        "counts": {"vuel": len(vuels), "ghost": len(ghosts), "initial_solution": len(initial_values)},
        "vuel_properties": props,
        "max_fraction_error": max_fraction_error,
        "real_host_mass_from_volume_csv": real_mass,
        "expected_ghost_mass": expected_ghost_mass,
        "expected_total_to_real_mass_ratio": (real_mass + expected_ghost_mass) / real_mass,
        "reference_fibers_sha256": ref_hash,
        "generated_fibers_sha256": generated_hash,
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if result["pass"] else 1)


if __name__ == "__main__":
    main()
