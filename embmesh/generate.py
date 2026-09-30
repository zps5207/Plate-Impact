from __future__ import annotations
import numpy as np
import importlib
from pathlib import Path
from .parser import parse_deck
from .selection import select_elements
from .fibers import flat_disc_fibers
from .curved_layup import cylindrical_fibers, spherical_fibers
from .volume import fiber_volume_rows, fiber_volume_rows_precise
from .writers import write_volume_csv, write_precise_volume_csv, write_report, write_vtk, append_fibers_to_deck
from .geometry import point_in_hex
from .symmetry import boundary_symmetry_sets, fiber_nodes_on_symmetry
from .hostvtk import write_host_fiber_vtk


def _validate(diameter, gap):
    if not (diameter > 0):
        raise ValueError(f"--diameter must be positive, got {diameter!r}")
    if gap < 0:
        raise ValueError(f"--gap must be non-negative, got {gap!r}")


def _stable_time_increment(fibers):
    """Shortest fiber SEGMENT length across every polyline (a rough longitudinal
    wave/Courant proxy in the deck's own length units -- not a substitute for
    Abaqus's own stable-increment estimate)."""
    best = None
    for f in fibers:
        pts = np.asarray(f.points, float)
        for a, b in zip(pts[:-1], pts[1:]):
            L = float(np.linalg.norm(b - a))
            if best is None or L < best: best = L
    return best


def mesh(deck_path, instance, diameter, output_dir, elset=None, gap=0., fiber_type="truss", reference=(1, 0, 0),
         preview=False, symmetry_tolerance=1e-7, thickness_axis=None, node_offset=100000, element_offset=100000,
         curved=None, curve_axis_point=(0., 0., 0.), curve_axis_dir=(0., 0., 1.), curve_center=(0., 0., 0.),
         curve_pole_axis=(0., 0., 1.), fiber_material="Fiber", precise_volume=False,
         progress=None):
    """Mesh a host region with embedded fibers. `curved` selects the layup family:
    None/'flat' (default) for a flat plate/box/cube, 'cylindrical' for a plate
    curved about a single axis, or 'spherical' for a spherically curved plate."""
    def report(percent, message):
        if progress:
            progress(percent, message)

    report(5, "Reading Abaqus input deck")
    _validate(diameter, gap)
    d = parse_deck(deck_path)
    report(15, "Selecting host elements")
    elems, nodes = select_elements(d, instance, elset)
    curved = (curved or "flat").lower()
    curve_meta = {}
    report(25, "Generating fiber layout")
    if curved in ("flat", "none", ""):
        fibers = flat_disc_fibers(elems, nodes, diameter, thickness_axis=thickness_axis, gap=gap, reference=reference)
    elif curved in ("cylindrical", "cylinder", "single-axis", "single_axis"):
        fibers, curve_meta = cylindrical_fibers(nodes, diameter, curve_axis_point, curve_axis_dir, gap=gap, reference=reference)
    elif curved in ("spherical", "sphere"):
        fibers, curve_meta = spherical_fibers(nodes, diameter, curve_center, curve_pole_axis, gap=gap, reference=reference)
    else:
        raise ValueError(f"unknown --curved mode {curved!r}; expected flat, cylindrical, or spherical")

    out = Path(output_dir); out.mkdir(parents=True, exist_ok=True)
    report(35, "Calculating fiber volume in host elements")
    rows = fiber_volume_rows(
        elems, nodes, fibers, diameter,
        progress=lambda done, total: report(35 + 25 * done / total,
                                            f"Calculating fiber volume ({done}/{total} host elements)"))
    write_volume_csv(out / 'fiber_volume.csv', rows, instance=instance)
    report(60, "Writing volume results")
    precise_rows = None
    if precise_volume:
        report(65, "Calculating precise fiber volumes")
        precise_rows = fiber_volume_rows_precise(
            elems, nodes, fibers, diameter,
            progress=lambda done, total: report(65 + 10 * done / total,
                                                f"Calculating precise fiber volumes ({done}/{total} host elements)"))
        write_precise_volume_csv(out / 'fiber_volume_precise.csv', precise_rows, instance=instance)
    # "embedded endpoints inside a host" is a cheap sanity check on the fiber
    # *endpoints* only (bbox-pruned per host, since checking every point of every
    # curved polyline against every host with no pruning is O(points*hosts) and
    # was the dominant cost for curved layups -- fiber_volume_rows above already
    # does the real, fully-pruned per-segment embedding measurement).
    report(75, "Checking fiber embedding and symmetry")
    host_boxes = [(np.asarray(hp := [nodes[i] for i in e.connectivity[:8]]).min(0),
                   np.asarray(hp).max(0), hp) for e in elems.values()]
    def _in_any_host(p):
        for lo, hi, hp in host_boxes:
            if np.all(p >= lo - 1e-9) and np.all(p <= hi + 1e-9) and point_in_hex(p, hp):
                return True
        return False
    endpoints = [f.points[0] for f in fibers] + [f.points[-1] for f in fibers]
    inside = sum(1 for p in endpoints if _in_any_host(p))
    total_pts = len(endpoints)
    stable_dt = _stable_time_increment(fibers)
    constraints = boundary_symmetry_sets(d, instance, symmetry_tolerance)
    propagated = fiber_nodes_on_symmetry(fibers, node_offset, constraints, symmetry_tolerance)

    report(85, "Writing visualization files")
    write_vtk(out / 'fibers.vtk', fibers)
    fractions = {row[0]: row[3] for row in rows}
    write_host_fiber_vtk(out / 'host_fibers.vtk', elems, nodes, fibers, fractions)
    if preview:
        plot_host_fibers = importlib.import_module('embmesh.visualize').plot_host_fibers
        plot_host_fibers(out / 'preview.html', elems, nodes, fibers, fractions)

    report(92, "Writing embedded Abaqus deck")
    append_fibers_to_deck('\n'.join(d.original_lines), out / 'output.inp', fibers, fiber_type, diameter,
                           node_offset=node_offset, element_offset=element_offset,
                           host_elset=elset or 'HOST', host_instance=instance, symmetry_nodes=propagated,
                           fiber_material=fiber_material, host_labels=list(elems.keys()))
    report_kw = dict(fiber_count=len(fibers), host_count=len(elems), curved=curved,
                 curve_meta={k: (list(v) if isinstance(v, np.ndarray) else v) for k, v in curve_meta.items()},
                 symmetry_constraints={k: [int(v[0]), float(v[1])] for k, v in constraints.items()},
                 propagated_symmetry_nodes=propagated,
                 total_fiber_volume=sum(r[2] for r in rows),
                 volume_fraction_min=min((r[3] for r in rows), default=0),
                 volume_fraction_max=max((r[3] for r in rows), default=0),
                 embedded_endpoints_inside=inside, embedded_endpoint_total=total_pts,
                 estimated_stable_time_increment=stable_dt)
    if precise_rows is not None:
        by_label = {r[0]: r for r in rows}
        diffs = [abs(pr[2] - by_label[pr[0]][2]) / by_label[pr[0]][2] for pr in precise_rows if by_label[pr[0]][2] > 0]
        report_kw.update(
            total_fiber_volume_precise=sum(r[2] for r in precise_rows),
            volume_fraction_precise_min=min((r[3] for r in precise_rows), default=0),
            volume_fraction_precise_max=max((r[3] for r in precise_rows), default=0),
            precise_vs_length_max_rel_diff=max(diffs, default=0.0))
    write_report(out / 'report.json', **report_kw)
    report(100, "Meshing complete")
    return fibers, rows


def mesh_flat(deck_path, instance, diameter, output_dir, elset=None, gap=0., fiber_type="truss",
              reference=(1, 0, 0), preview=False, symmetry_tolerance=1e-7, **kw):
    """Backward-compatible flat-plate entry point; see `mesh`."""
    return mesh(deck_path, instance, diameter, output_dir, elset=elset, gap=gap, fiber_type=fiber_type,
                reference=reference, preview=preview, symmetry_tolerance=symmetry_tolerance, curved="flat", **kw)
