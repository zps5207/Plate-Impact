#!/usr/bin/env python3
"""
patch_vuel_sdv_output.py: Diagnostic patch for embmesh/vuelghost.py.

Adds a host VU1 element set EMBMESH_VUEL_DIAGNOSTICS and field output
request for SDV49 (failure flag), SDV106 (damage fraction), and SDV107
(fiber volume fraction) so that follow-up ROAR runs can directly query and
cross-reference VU1 host failure states against native ghost STATUS per element.
"""
import sys
import os

VUEL_DIAGNOSTICS_ELSET = "EMBMESH_VUEL_DIAGNOSTICS"

def patch_vuelghost_content(content: str) -> str:
    """Apply the SDV field output request modification to vuelghost.py content."""
    # 1. Add VUEL_DIAGNOSTICS_ELSET constant if not already present
    if "VUEL_DIAGNOSTICS_ELSET" not in content:
        target_const = 'GHOST_DIAGNOSTIC_VARIABLES = ("S", "LE", "PEEQ", "SDEG", "STATUS")'
        replacement_const = (
            'GHOST_DIAGNOSTIC_VARIABLES = ("S", "LE", "PEEQ", "SDEG", "STATUS")\n'
            f'VUEL_DIAGNOSTICS_ELSET = "{VUEL_DIAGNOSTICS_ELSET}"'
        )
        if target_const not in content:
            raise ValueError("Could not find GHOST_DIAGNOSTIC_VARIABLES target line in vuelghost.py")
        content = content.replace(target_const, replacement_const)

    # 2. Add instance elset creation for host elements at *End Assembly
    if 'VUEL_DIAGNOSTICS_ELSET' not in content or '_instance_set_lines(\n                VUEL_DIAGNOSTICS_ELSET' not in content:
        target_assembly = 'final.extend(_instance_set_lines(\n                GHOST_DIAGNOSTIC_ELSET, instance, ghost_by_host.values()))'
        replacement_assembly = (
            'final.extend(_instance_set_lines(\n                GHOST_DIAGNOSTIC_ELSET, instance, ghost_by_host.values()))\n'
            '            final.extend(_instance_set_lines(\n                VUEL_DIAGNOSTICS_ELSET, instance, ghost_by_host.keys()))'
        )
        if target_assembly in content:
            content = content.replace(target_assembly, replacement_assembly)

    # 3. Add field output request for SDV49, SDV106, SDV107 at *End Step
    if 'EMBMESH_VUEL_DIAGNOSTICS' not in content or 'SDV49' not in content:
        target_step = 'if name == "end step":\n            final.extend(_ghost_diagnostic_output_lines())'
        replacement_step = (
            'if name == "end step":\n'
            '            final.extend(_ghost_diagnostic_output_lines())\n'
            '            final.extend([\n'
            '                "** embmesh: host VU1 failure state diagnostics",\n'
            '                "*Output, field, number interval=1000",\n'
            '                f"*Element Output, elset={VUEL_DIAGNOSTICS_ELSET}",\n'
            '                "SDV49, SDV106, SDV107",\n'
            '            ])'
        )
        if target_step in content:
            content = content.replace(target_step, replacement_step)

    return content

def main():
    if len(sys.argv) < 2:
        target_path = "embmesh/vuelghost.py"
    else:
        target_path = sys.argv[1]

    if not os.path.exists(target_path):
        print(f"Error: target file {target_path!r} not found.", file=sys.stderr)
        sys.exit(1)

    with open(target_path, "r", encoding="utf-8") as f:
        original = f.read()

    patched = patch_vuelghost_content(original)

    with open(target_path, "w", encoding="utf-8") as f:
        f.write(patched)

    print(f"Successfully patched {target_path} to request host VU1 SDV output.")

if __name__ == "__main__":
    main()
