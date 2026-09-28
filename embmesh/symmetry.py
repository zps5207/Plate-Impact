from __future__ import annotations

import numpy as np


def boundary_symmetry_sets(deck, instance: str, tolerance: float = 1e-8):
    """Return ``{node-set: (axis, plane_coordinate)}`` for *Boundary symmetry sets.

    Abaqus DOF 1/2/3 correspond to X/Y/Z.  The plane is inferred from the
    original set nodes; non-planar sets are ignored conservatively.
    """
    inst = deck.instances[instance]
    part = deck.parts[inst.part]
    constraints = {}
    lines = deck.original_lines
    for i, raw in enumerate(lines):
        if raw.strip().lower().startswith("*boundary"):
            j = i + 1
            while j < len(lines) and not lines[j].lstrip().startswith("*"):
                vals = [x.strip() for x in lines[j].split(",")]
                if len(vals) >= 2:
                    name = vals[0]
                    try:
                        first = int(float(vals[1])); last = int(float(vals[2])) if len(vals) > 2 and vals[2] else first
                    except ValueError:
                        j += 1; continue
                    # Symmetry constraints are single translational DOFs; do not
                    # infer a plane for arbitrary prescribed constraints.
                    if first == last and first in (1, 2, 3) and name in part.nsets:
                        q = np.asarray([inst.transform(part.nodes[n]) for n in part.nsets[name] if n in part.nodes])
                        if len(q):
                            c = float(np.median(q[:, first - 1]))
                            if float(np.max(np.abs(q[:, first - 1] - c))) <= tolerance:
                                constraints[name] = (first - 1, c)
                j += 1
    return constraints


def fiber_nodes_on_symmetry(fibers, node_offset: int, constraints, tolerance=1e-7):
    result = {name: [] for name in constraints}
    node_id = node_offset
    for fiber in fibers:
        for point in np.asarray(fiber.points):
            for name, (axis, coordinate) in constraints.items():
                if abs(float(point[axis]) - coordinate) <= tolerance:
                    result[name].append(node_id)
            node_id += 1
    return {k: sorted(set(v)) for k, v in result.items() if v}

