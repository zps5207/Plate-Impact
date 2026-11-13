r"""Fiber-to-host contact deck builder from the nv3_int deck.

Takes Meshing/newvals-interior-tt3/nv3_int.inp and adds:
  * Per-ply eroding ghost host surfaces (EMBMESH_HOST_PLY_k) with exterior and interior faces
  * Per-ply fiber node surfaces (EMBMESH_FIBER_NODES_PLY_k)
  * Fiber-host contact inclusions (400 pairs: 20 own-ply + 380 other-ply)
  * FiberHostBaseline user interaction (VUINTERACTION) for own-ply pairs with baseline overclosure
  * Native penalty (General) for cross-ply pairs
  * Fiber node thickness assigned to equivalent truss diameter (0.000632 m = 0.632 mm)
  * *Contact Controls Assignment, nodal erosion=YES (no data lines)
  * 2 us step duration, 20 field frames (0.1 us intervals)

Usage:
  python build_newvals_fiberhost_tt3.py
  (writes Meshing/newvals-fiberhost-tt3/nv3_fh.inp)
"""
import argparse
import math
from pathlib import Path
import re
import sys


def find_project_root():
    p = Path(__file__).resolve()
    for parent in p.parents:
        if (parent / "Meshing").exists():
            return parent
    # Fallback to relative navigation
    return Path(__file__).resolve().parents[4]


PLIES = 20
STEP = 2e-6
FRAMES = 20
DEFAULT_FIBER_AREA = 3.1370687601686238e-07  # m^2 -> diameter ~ 0.632 mm
PENALTY_K = 2.0e11  # Pa/m penalty stiffness
FRICTION_MU = 0.01  # Coulomb friction matching General



def _ply_fiber_nset(lines, k):
    """Copy the assembly-level EMBMESH_FIBER_ALL_NODES block of instance
    Fibers-Ply-k as a per-ply nset EMBMESH_FIBER_NODES_PLY_k (hub fix:
    Fibers-Ply-k.EMBMESH_FIBER_ALL_NODES does not exist at part level)."""
    head = f"*nset, nset=embmesh_fiber_all_nodes, instance=fibers-ply-{k}"
    for i, line in enumerate(lines):
        if line.strip().lower() == head:
            out = [f"*Nset, nset=EMBMESH_FIBER_NODES_PLY_{k}, instance=Fibers-Ply-{k}"]
            j = i + 1
            while j < len(lines) and not lines[j].lstrip().startswith("*"):
                out.append(lines[j])
                j += 1
            return out
    raise ValueError(f"No EMBMESH_FIBER_ALL_NODES block for Fibers-Ply-{k}")

def build_fiberhost_deck(src_path: Path, out_path: Path, plies: int = PLIES):
    lines = src_path.read_text(encoding="utf-8").splitlines()

    # 1. Compute equivalent diameter from fiber section area in deck
    area = None
    for i, line in enumerate(lines):
        if line.lstrip().lower().startswith("*solid section") and "material=fiber" in line.lower():
            next_line = lines[i + 1].strip()
            try:
                area = float(next_line.split(",")[0])
                break
            except (ValueError, IndexError):
                pass
    if area is None:
        area = DEFAULT_FIBER_AREA
    fiber_diameter = 2.0 * math.sqrt(area / math.pi)

    # 2. Add per-ply assembly surfaces before *End Assembly
    end_assembly_idx = None
    for i, line in enumerate(lines):
        if line.strip().lower() == "*end assembly":
            end_assembly_idx = i
            break
    if end_assembly_idx is None:
        raise ValueError("Could not find *End Assembly in source deck")

    surf_lines = ["** embmesh: per-ply eroding host and fiber contact surfaces"]
    for k in range(1, plies + 1):
        surf_lines += [
            f"*Surface, type=ELEMENT, name=EMBMESH_HOST_PLY_{k}",
            f"Ply-{k}.EMBMESH_GHOST_HOST,",
            f"Ply-{k}.EMBMESH_GHOST_HOST, INTERIOR",
        ]
        surf_lines += _ply_fiber_nset(lines, k)
        surf_lines += [
            f"*Surface, type=NODE, name=EMBMESH_FIBER_NODES_PLY_{k}",
            f"EMBMESH_FIBER_NODES_PLY_{k},",
        ]
    lines[end_assembly_idx:end_assembly_idx] = surf_lines

    # 3. Add *Surface Interaction, name=FiberHostBaseline before first *Step
    step_idx = None
    for i, line in enumerate(lines):
        if line.lstrip().lower().startswith("*step"):
            step_idx = i
            break
    if step_idx is None:
        raise ValueError("Could not find *Step in source deck")

    inter_lines = [
        "** embmesh: user interaction for own-ply fiber-host contact with baseline overclosure",
        "*Surface Interaction, name=FiberHostBaseline, USER=INTERACTION, PROPERTIES=2, DEPVAR=2, TRACKING THICKNESS=0.0005",
        "",
        f" {PENALTY_K:g}, {FRICTION_MU:g}",
    ]
    lines[step_idx:step_idx] = inter_lines

    # 4. Inclusions and Property Assignments in *Contact
    contact_idx = None
    for i, line in enumerate(lines):
        if line.strip().lower().startswith("*contact,"):
            contact_idx = i
            break
    if contact_idx is None:
        raise ValueError("Could not find *Contact block in source deck")

    # Build 400 inclusion lines and 20 baseline property lines
    inclusions_list = []
    baseline_prop_list = []
    for k in range(1, plies + 1):
        # Own-ply pair
        inclusions_list.append(f"EMBMESH_FIBER_NODES_PLY_{k} , EMBMESH_HOST_PLY_{k}")
        baseline_prop_list.append(f"EMBMESH_FIBER_NODES_PLY_{k} , EMBMESH_HOST_PLY_{k} , FiberHostBaseline")
        # Other plies
        for j in range(1, plies + 1):
            if j != k:
                inclusions_list.append(f"EMBMESH_FIBER_NODES_PLY_{k} , EMBMESH_HOST_PLY_{j}")

    # Insert inclusions under *Contact Inclusions
    incl_hdr_idx = None
    for i in range(contact_idx, len(lines)):
        if lines[i].strip().lower().startswith("*contact inclusions"):
            incl_hdr_idx = i
            break
    if incl_hdr_idx is None:
        raise ValueError("Could not find *Contact Inclusions in source deck")

    # Find end of inclusion data lines (next keyword)
    incl_end_idx = incl_hdr_idx + 1
    while incl_end_idx < len(lines) and not lines[incl_end_idx].lstrip().startswith("*"):
        incl_end_idx += 1
    lines[incl_end_idx:incl_end_idx] = inclusions_list

    # Insert baseline property assignments under *Contact Property Assignment
    prop_hdr_idx = None
    for i in range(incl_end_idx, len(lines)):
        if lines[i].strip().lower().startswith("*contact property assignment"):
            prop_hdr_idx = i
            break
    if prop_hdr_idx is None:
        raise ValueError("Could not find *Contact Property Assignment in source deck")

    prop_end_idx = prop_hdr_idx + 1
    while prop_end_idx < len(lines) and not lines[prop_end_idx].lstrip().startswith("*"):
        prop_end_idx += 1
    lines[prop_end_idx:prop_end_idx] = baseline_prop_list

    # 5. Thickness assignments
    thickness_hdr_idx = None
    for i in range(prop_end_idx, len(lines)):
        if lines[i].strip().lower().startswith("*surface property assignment, property=thickness"):
            thickness_hdr_idx = i
            break

    thick_lines = []
    for k in range(1, plies + 1):
        thick_lines.append(f"EMBMESH_FIBER_NODES_PLY_{k}, {fiber_diameter:.15g}")

    if thickness_hdr_idx is not None:
        # Append to existing thickness section
        thick_end_idx = thickness_hdr_idx + 1
        while thick_end_idx < len(lines) and not lines[thick_end_idx].lstrip().startswith("*"):
            thick_end_idx += 1
        lines[thick_end_idx:thick_end_idx] = thick_lines
    else:
        # Insert new thickness keyword before *Contact Controls Assignment or *End Step
        controls_idx = None
        for i in range(prop_end_idx, len(lines)):
            if lines[i].strip().lower().startswith("*contact controls assignment"):
                controls_idx = i
                break
        insert_thick_idx = controls_idx if controls_idx else prop_end_idx
        lines[insert_thick_idx:insert_thick_idx] = [
            "*Surface Property Assignment, property=THICKNESS"
        ] + thick_lines

    # 6. Ensure *Contact Controls Assignment, nodal erosion=YES exists with NO data lines
    has_nodal_erosion = False
    for i in range(contact_idx, len(lines)):
        if lines[i].strip().lower() == "*contact controls assignment, nodal erosion=yes":
            has_nodal_erosion = True
            # Verify no data line follows
            if i + 1 < len(lines) and not lines[i + 1].lstrip().startswith("*"):
                raise ValueError(f"Unexpected data line under nodal erosion: {lines[i + 1]}")
            break
    if not has_nodal_erosion:
        # Insert after property assignment
        lines[prop_end_idx:prop_end_idx] = ["*Contact Controls Assignment, nodal erosion=YES"]

    # 7. Step duration and field frames
    dyn_idx = None
    for i, line in enumerate(lines):
        if line.strip().lower().startswith("*dynamic, explicit"):
            dyn_idx = i
            break
    if dyn_idx is not None:
        lines[dyn_idx + 1] = f", {STEP:g}"

    for j, s in enumerate(lines):
        if s.startswith("*Output, field") and "number interval=" in s:
            # Replace existing intervals with FRAMES
            lines[j] = re.sub(r"number interval=\d+", f"number interval={FRAMES}", s)

    # 8. Write output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Successfully generated: {out_path}")
    print(f"  Plies: {plies}")
    print(f"  Inclusion pairs added: {len(inclusions_list)}")
    print(f"  Baseline property pairs: {len(baseline_prop_list)}")
    print(f"  Assigned fiber thickness: {fiber_diameter:.6e} m")


def main():
    root = find_project_root()
    default_src = root / "Meshing" / "newvals-interior-tt3" / "nv3_int.inp"
    default_out = root / "Meshing" / "newvals-fiberhost-tt3" / "nv3_fh.inp"

    parser = argparse.ArgumentParser(description="Build nv3_fh.inp deck with fiber-host contact")
    parser.add_argument("--src", type=Path, default=default_src, help="Path to input nv3_int.inp")
    parser.add_argument("--out", type=Path, default=default_out, help="Path to output nv3_fh.inp")
    parser.add_argument("--plies", type=int, default=PLIES, help="Number of plies (default: 20)")
    args = parser.parse_args()

    build_fiberhost_deck(args.src, args.out, plies=args.plies)


if __name__ == "__main__":
    main()
