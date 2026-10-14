"""Draft patch for Recipe 2: Node-Based Plate Surface Contact.

This script patches embmesh/vuelghost.py to:
1. Define a node-based contact surface '*Surface, type=NODE, name=Surf-Plate-Nodes'
   from the plate instance nodes ('Plate-1.PLATE') before '*End Assembly'.
2. Append 'Surf-Plate-Nodes, Surf-2' to '*Contact Inclusions'.
3. Assign finite contact thickness (0.0005 m = 0.5 mm) via '*Surface Property Assignment, type=THICKNESS'
   to eliminate zero-thickness inter-nodal punch-through.
"""

from __future__ import annotations
import sys
from pathlib import Path


def apply_patch(vuelghost_path: Path) -> str:
    content = vuelghost_path.read_text(encoding="utf-8")

    # Hook at end assembly
    old_end_assembly = 'if name == "end assembly":\n            final.extend(_initial_solution_lines(instance, fractions))'
    new_end_assembly = '''if name == "end assembly":
            final.extend([
                "** embmesh: node-based contact surface for plate nodes",
                "*Surface, type=NODE, name=Surf-Plate-Nodes",
                f"{instance}.PLATE,",
            ])
            final.extend(_initial_solution_lines(instance, fractions))'''

    if old_end_assembly not in content:
        raise RuntimeError("Could not locate end assembly hook in vuelghost.py")

    content = content.replace(old_end_assembly, new_end_assembly, 1)

    # Hook at *Contact
    old_contact_hook = 'if not inserted_model_data and name == "material":'
    new_contact_hook = '''        if name == "contact":
            final.extend(block)
            final.extend([
                "** embmesh: include plate node surface and assign thickness",
                "*Contact Inclusions",
                "Surf-Plate-Nodes, Surf-2",
                "*Surface Property Assignment, type=THICKNESS",
                "Surf-Plate-Nodes, 0.0005",
            ])
            continue
        if not inserted_model_data and name == "material":'''

    if old_contact_hook not in content:
        raise RuntimeError("Could not locate material hook in vuelghost.py")

    content = content.replace(old_contact_hook, new_contact_hook, 1)
    return content


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("embmesh/vuelghost.py")
    if target.exists():
        patched = apply_patch(target)
        print("Patch validated successfully on", target)
    else:
        print("Target not found on local path (dry-run review mode)")
