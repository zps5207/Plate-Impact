from __future__ import annotations
import csv,json
from pathlib import Path
import numpy as np

def write_volume_csv(path, rows, instance=None):
    header = ["element_label", "host_volume", "fiber_volume", "volume_fraction", "length_t0", "length_t90"]
    if instance is not None:
        header = ["instance"] + header
        rows = [(instance,) + tuple(r) for r in rows]
    with open(path,"w",newline="") as f:
        w=csv.writer(f); w.writerow(header); w.writerows(rows)

def write_precise_volume_csv(path, rows, instance=None):
    """Rows from volume.fiber_volume_rows_precise: cross-section-weighted
    cylinder/hex intersection volume per host, not the length x area
    approximation `write_volume_csv` records -- see that function's docstring."""
    header = ["element_label", "host_volume", "fiber_volume_precise", "volume_fraction_precise", "volume_t0", "volume_t90"]
    if instance is not None:
        header = ["instance"] + header
        rows = [(instance,) + tuple(r) for r in rows]
    with open(path, "w", newline="") as f:
        w = csv.writer(f); w.writerow(header); w.writerows(rows)

def write_report(path, **data): Path(path).write_text(json.dumps(data,indent=2,sort_keys=True))

def write_vtk(path,fibers, fractions=None):
    points=[]; lines=[]
    for f in fibers:
      i=len(points); pts=np.asarray(f.points,float); points.extend(pts.tolist())
      for k in range(len(pts)-1): lines.append((i+k,i+k+1))
    with open(path,"w") as h:
      h.write("# vtk DataFile Version 3.0\nembmesh fibers\nASCII\nDATASET POLYDATA\n")
      h.write(f"POINTS {len(points)} float\n"+"\n".join("%g %g %g"%tuple(p) for p in points)+"\n")
      h.write(f"LINES {len(lines)} {3*len(lines)}\n"+"\n".join(f"2 {a} {b}" for a,b in lines)+"\n")


def _beam_normal(tangent, up_hint):
    """A unit vector perpendicular to `tangent`, close to `up_hint` when possible
    (falls back to any non-parallel global axis so it is always well-defined)."""
    t = tangent / max(np.linalg.norm(tangent), 1e-15)
    for up in (up_hint, np.array([0., 0., 1.]), np.array([0., 1., 0.]), np.array([1., 0., 0.])):
        n = up - t * (up @ t)
        m = np.linalg.norm(n)
        if m > 1e-6:
            return n / m
    return np.array([1., 0., 0.])


def append_fibers_to_deck(original, path, fibers, fiber_type="truss", diameter=1.0, node_offset=100000,
                           element_offset=100000, host_elset="HOST", host_instance=None, symmetry_nodes=None,
                           fiber_instance_name="EMBFIB-1", fiber_part_name="EMBFIB", fiber_material="Fiber"):
    """Append the generated fibers as a real, Abaqus-loadable addition to `original`.

    Abaqus rejects `*Node`/`*Element`/`*Solid Section`/`*Beam Section` unless they
    sit inside a `*Part` (or `*Instance`) -- appending them after the whole deck, or
    bare inside `*Assembly`, are both invalid (confirmed against Abaqus 2024; see
    docs/BUGS.md BUG-006). So the fiber mesh is written as its own small `*Part`,
    instanced inside the existing `*Assembly ... *End Assembly` (inserted just
    before `*End Assembly`, whatever else that block already contains), with
    `*Embedded Element` referencing the host by its instance-qualified elset.
    """
    typ = "T3D2" if fiber_type == "truss" else "B31"
    out = list(original.splitlines())
    max_node = max_elem = 0; sec = ''
    for line in out:
        s = line.strip()
        if s.startswith('*'): sec = s.lower()
        elif s and not s.startswith('**'):
            try:
                n = int(s.split(',')[0])
                if sec.startswith('*node'): max_node = max(max_node, n)
                if sec.startswith('*element'): max_elem = max(max_elem, n)
            except ValueError: pass
    if node_offset <= max_node: raise ValueError(f"fiber node offset {node_offset} collides with existing maximum {max_node}")
    if element_offset <= max_elem: raise ValueError(f"fiber element offset {element_offset} collides with existing maximum {max_elem}")

    node_lines = ["*Node, nset=EMBMESH_NODES"]
    elem_lines_by_dir: dict[str, list[str]] = {}
    normals: list[tuple[int, int, np.ndarray]] = []   # (element_label, node_label, n1)
    nid = node_offset; eid = element_offset
    for f in fibers:
        pts = np.asarray(f.points, float)
        ids = []
        for p in pts:
            node_lines.append(f"{nid}, {p[0]:.12g}, {p[1]:.12g}, {p[2]:.12g}")
            ids.append(nid); nid += 1
        up_raw = np.asarray(f.curvature_data.get("up", (0., 0., 1.)), float) if f.curvature_data else np.array([0., 0., 1.])
        n_seg = len(ids) - 1
        up_per_seg = np.tile(up_raw, (n_seg, 1)) if up_raw.ndim == 1 else up_raw
        group = elem_lines_by_dir.setdefault(f.direction, [])
        for k, (a, b) in enumerate(zip(ids[:-1], ids[1:])):
            group.append(f"{eid}, {a},{b}")
            if fiber_type == "beam":
                n1 = _beam_normal(pts[k + 1] - pts[k], up_per_seg[min(k, len(up_per_seg) - 1)])
                normals.append((eid, a, n1)); normals.append((eid, b, n1))
            eid += 1

    directions = sorted(elem_lines_by_dir)
    section_lines: list[str] = []
    all_elset_names = []
    for d in directions:
        ename = f"EMBMESH_FIBERS_{d.upper()}"
        all_elset_names.append(ename)
        section_lines.append(f"*Element, type={typ}, elset={ename}")
        section_lines += elem_lines_by_dir[d]
    for i, d in enumerate(directions):
        ename = all_elset_names[i]
        if fiber_type == "truss":
            section_lines += [f"*Solid Section, elset={ename}, material={fiber_material}",
                               f"{np.pi * diameter ** 2 / 4:.15g}"]
        else:
            # give the section a harmless default n1; every element's true local
            # orientation is overridden explicitly via *Normal below (BUG-002 fix:
            # a single shared n1 is not valid once fibers are not all parallel).
            default_n1 = _beam_normal(np.array([1., 0., 0.]), np.array([0., 0., 1.]))
            section_lines += [f"*Beam Section, elset={ename}, material={fiber_material}, section=CIRC",
                               f"{diameter / 2:.15g}, {default_n1[0]:.15g}, {default_n1[1]:.15g}, {default_n1[2]:.15g}"]
    if fiber_type == "beam" and normals:
        section_lines += ["*Normal"] + [f"{e}, {n}, {v[0]:.12g}, {v[1]:.12g}, {v[2]:.12g}" for e, n, v in normals]

    fib_part = [f"*Part, name={fiber_part_name}"] + node_lines + section_lines + ["*End Part"]
    fib_instance = [f"*Instance, name={fiber_instance_name}, part={fiber_part_name}", "*End Instance"]

    host_ref = f"{host_instance}.{host_elset}" if host_instance else host_elset
    emb = [f"*Embedded Element, host elset={host_ref}"] + [f"{fiber_instance_name}.{n}" for n in all_elset_names]

    nset_lines = []
    for set_name, labels in (symmetry_nodes or {}).items():
        if labels:
            nset_lines += [f"** embmesh propagated fiber nodes to symmetry set {set_name}", f"*Nset, nset={set_name}"]
            nset_lines += [", ".join(str(x) for x in labels)]

    try:
        ip = min(i for i, l in enumerate(out) if l.strip().lower().startswith("*assembly"))
        ia = max(i for i, l in enumerate(out) if l.strip().lower().startswith("*end assembly"))
    except ValueError:
        raise ValueError("source deck has no *Assembly ... *End Assembly block; cannot embed fibers")

    # Fiber is assumed to be defined in the source deck.  Do not append a
    # material block after the analysis steps: Abaqus reads material definitions
    # in the model-data region, before the first *Step.
    new = out[:ip] + fib_part + out[ip:ia] + fib_instance + emb + nset_lines + out[ia:]
    Path(path).write_text("\n".join(new) + "\n")
