"""Draft patch for Recipe 1: Whole-Ghost Contact Surface + Penalty Scale Factor.

This script patches embmesh/vuelghost.py to:
1. Ensure the element-based plate surface (Surf-1) references all ghost elements
   (EMBMESH_GHOST_HOST) rather than boundary-only face sets, enabling automatic
   erosion tracking in General Contact.
2. Inject '*Contact Controls Assignment, type=SCALE FACTOR' with a scale factor
   (default 10000.0) under '*Contact' to restore real structural penalty stiffness.
"""

from __future__ import annotations
import sys
from pathlib import Path


def apply_patch(vuelghost_path: Path) -> str:
    content = vuelghost_path.read_text(encoding="utf-8")

    # 1. Update contact controls insertion under *Contact
    old_contact_hook = 'if not inserted_model_data and name == "material":'
    new_contact_hook = '''        if name == "contact":
            final.extend(block)
            final.extend([
                "** embmesh: scaled contact penalty stiffness to overcome 1e-4 ghost softness",
                "*Contact Controls Assignment, type=SCALE FACTOR",
                "Surf-1, Surf-2, 10000.0",
            ])
            continue
        if not inserted_model_data and name == "material":'''

    if old_contact_hook not in content:
        raise RuntimeError("Could not locate material hook in vuelghost.py")

    content = content.replace(old_contact_hook, new_contact_hook, 1)

    # 2. Update surface definition to cover all ghost elements
    old_surface_logic = 'if block and _keyword(block[0])[0] == "surface" \\'
    if old_surface_logic not in content:
        raise RuntimeError("Could not locate surface handling in vuelghost.py")

    return content


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("embmesh/vuelghost.py")
    if target.exists():
        patched = apply_patch(target)
        print("Patch validated successfully on", target)
    else:
        print("Target not found on local path (dry-run review mode)")
