from __future__ import annotations

import numpy as np

_SYMM_SHORTHAND = {"xsymm": 1, "ysymm": 2, "zsymm": 3}


def _kw_opts(line: str) -> dict:
    fields = [x.strip() for x in line.strip()[1:].split(",")]
    opts = {}
    for f in fields[1:]:
        if "=" in f:
            k, v = f.split("=", 1); opts[k.strip().lower()] = v.strip()
    return opts


def boundary_symmetry_sets(deck, instance: str, tolerance: float = 1e-8):
    """Return ``{node-set: (axis, plane_coordinate)}`` for genuine *Boundary symmetry
    constraints (BUG-005 fix): only a zero-valued, DISPLACEMENT-type single-DOF
    constraint (or the XSYMM/YSYMM/ZSYMM shorthand) on a planar node set counts --
    a nonzero prescribed value, or a VELOCITY/ACCELERATION/... type BC on the same
    kind of set, is not a symmetry plane and must not be propagated to fiber nodes.
    Both the bare part-level set name and the instance-qualified form
    (`<instance>.<name>`) are recognized.
    """
    inst = deck.instances[instance]
    part = deck.parts[inst.part]
    constraints = {}
    lines = deck.original_lines
    prefix = f"{instance}.".lower()
    for i, raw in enumerate(lines):
        if raw.strip().lower().startswith("*boundary"):
            opts = _kw_opts(raw)
            btype = str(opts.get("type", "displacement")).lower()
            if btype not in ("displacement", ""):
                j = i + 1
                while j < len(lines) and not lines[j].lstrip().startswith("*"): j += 1
                continue
            j = i + 1
            while j < len(lines) and not lines[j].lstrip().startswith("*"):
                vals = [x.strip() for x in lines[j].split(",")]
                if len(vals) >= 2:
                    raw_name = vals[0]
                    name = raw_name[len(prefix):] if raw_name.lower().startswith(prefix) else raw_name
                    dof_field = vals[1].lower()
                    axis = None; has_magnitude = False
                    if dof_field in _SYMM_SHORTHAND:
                        axis = _SYMM_SHORTHAND[dof_field] - 1
                    else:
                        try:
                            first = int(float(vals[1])); last = int(float(vals[2])) if len(vals) > 2 and vals[2] else first
                        except ValueError:
                            j += 1; continue
                        if first == last and first in (1, 2, 3):
                            axis = first - 1
                        if len(vals) > 3 and vals[3]:
                            try: has_magnitude = abs(float(vals[3])) > 1e-12
                            except ValueError: has_magnitude = True
                    if axis is not None and not has_magnitude and name in part.nsets:
                        q = np.asarray([inst.transform(part.nodes[n]) for n in part.nsets[name] if n in part.nodes])
                        if len(q):
                            c = float(np.median(q[:, axis]))
                            if float(np.max(np.abs(q[:, axis] - c))) <= tolerance:
                                constraints[name] = (axis, c)
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
