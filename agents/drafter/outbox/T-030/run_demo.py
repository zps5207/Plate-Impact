"""Demonstration script for T-030: cohesive contact pair emitter on 4-ply decks."""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Load delivered plycohesive directly
import importlib.util
import embmesh

_plycohesive_path = Path(__file__).resolve().parent / "embmesh" / "plycohesive.py"
_spec = importlib.util.spec_from_file_location("embmesh.plycohesive", str(_plycohesive_path))
_mod = importlib.util.module_from_spec(_spec)
sys.modules["embmesh.plycohesive"] = _mod
_spec.loader.exec_module(_mod)

from embmesh.plycohesive import (
    cohesive_contact_lines,
    insert_cohesive_contact,
    insert_cohesive_contact_into_deck,
)
from embmesh.plywise import interface_pairs
from embmesh.parser import parse_deck


def run():
    out_dir = Path(__file__).resolve().parent / "demo_4ply"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Build a 4-ply deck matching Meshing/stack.inp structure
    # Extract the exact Cohesion interaction and step from stack.inp
    stack_lines = (REPO_ROOT / "Meshing" / "stack.inp").read_text(encoding="utf-8").splitlines()

    # Find Cohesion surface interaction in stack.inp
    cohesion_start = next(i for i, l in enumerate(stack_lines) if l.strip().lower() == "*surface interaction, name=cohesion")
    cohesion_end = next(i for i in range(cohesion_start + 1, len(stack_lines)) if stack_lines[i].strip().lower().startswith("*surface interaction, name=general"))
    cohesion_block = stack_lines[cohesion_start:cohesion_end]

    # Find step block
    step_start = next(i for i, l in enumerate(stack_lines) if l.strip().lower().startswith("*step"))

    base_deck_lines = [
        "*Heading",
        "** 4-ply cohesive demonstration deck built from stack.inp structure",
        "*Part, name=Plate",
        "*Node",
        "1, 0., 0., 0.",
        "2, 0.05, 0., 0.",
        "3, 0.05, 0.05, 0.",
        "4, 0., 0.05, 0.",
        "5, 0., 0., 0.0025",
        "6, 0.05, 0., 0.0025",
        "7, 0.05, 0.05, 0.0025",
        "8, 0., 0.05, 0.0025",
        "*Element, type=C3D8R",
        "1, 1, 2, 3, 4, 5, 6, 7, 8",
        "*End Part",
        "*Assembly, name=Assembly",
    ]
    for k in range(1, 5):
        base_deck_lines.append(f"*Instance, name=Ply-{k}, part=Plate")
        base_deck_lines.append(f"0., 0., {(k-1)*0.0025:.6g}")
        base_deck_lines.append("*End Instance")

    # Assembly surfaces in CAE style matching stack.inp / plywise
    for k in range(1, 5):
        base_deck_lines.extend([
            f"*Elset, elset=_Ply-{k}_bottom_S1, internal, instance=Ply-{k}",
            "1",
            f"*Surface, type=ELEMENT, name=Ply-{k}_bottom",
            f"_Ply-{k}_bottom_S1, S1",
            f"*Elset, elset=_Ply-{k}_top_S2, internal, instance=Ply-{k}",
            "1",
            f"*Surface, type=ELEMENT, name=Ply-{k}_top",
            f"_Ply-{k}_top_S2, S2",
        ])
    base_deck_lines.append("*End Assembly")

    # Add interaction property block
    base_deck_lines.extend(["** ", "** INTERACTION PROPERTIES", "** "] + cohesion_block)

    # Add step block from stack.inp
    base_deck_lines.extend(stack_lines[step_start:])

    raw_source = "\n".join(base_deck_lines) + "\n"
    source_path = out_dir / "source_4ply.inp"
    source_path.write_text(raw_source, encoding="utf-8")

    # 2. Insert cohesive contact pairs for 4 plies
    pairs = interface_pairs(4)
    out_deck_path = out_dir / "output_4ply_cohesive.inp"

    print(f"Interface pairs for 4 plies: {pairs}")
    inserted_lines = cohesive_contact_lines(pairs, interaction="Cohesion", slave="lower", unique_cpset=True)
    print("\n--- Generated Contact Pair Lines (slave='lower', unique_cpset=True) ---")
    for l in inserted_lines:
        print(l)

    output_text = insert_cohesive_contact_into_deck(
        source_deck=source_path,
        output_deck=out_deck_path,
        interface_pairs=pairs,
        interaction="Cohesion",
        slave="lower",
        unique_cpset=True,
    )

    # 3. Verify parse_deck succeeds
    parsed = parse_deck(out_deck_path)
    assert len(parsed.instances) >= 4
    print(f"\nWritten deck parsed successfully! Instances: {list(parsed.instances.keys())[:6]}")

    # Inspect interaction lines in output
    print("\n--- Lines around INTERACTIONS in written deck ---")
    out_lines = output_text.splitlines()
    i_start = next(i for i, l in enumerate(out_lines) if l.strip().upper() == "** INTERACTIONS")
    for l in out_lines[i_start : i_start + 25]:
        print(l)


if __name__ == "__main__":
    run()
