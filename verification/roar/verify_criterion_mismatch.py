"""Indirect verification of agy's T-007 criterion-mismatch hypothesis,
without any new SDV field-output request (confirmed impossible for VUELs
-- see abaqus-explicit-quirks.md item 6).

Idea: VU1 and its ghost C3D8R share identical node connectivity, so the
deformation (and hence Green-Lagrange strain) VU1 would see is exactly
recoverable from the standard nodal displacement field U, which IS a
normal, always-available field output. This script re-implements VU1's
own engineering-strain failure criterion (uel/VUEL_failure.for,
ELEM_MAXABS_ENG vs EPS_FAIL) in pure Python against the ghost's shared
nodes, for each "island" ghost element (STATUS=1, surrounded mostly by
dead neighbors). It reports, per island:

  - whether the VU1-equivalent criterion ever would have exceeded
    EPS_FAIL (and at what frame/time), using only U history;
  - the island ghost element's own max SDEG ever reached (native
    ductile-damage criterion), from the already-present SDEG field.

This distinguishes two possible explanations without any new run:
  (a) VU1-equivalent criterion exceeds EPS_FAIL but ghost SDEG never
      approaches 1 -> genuine criterion mismatch (VU1 would have cut
      this element, the ghost's native criterion disagrees) -- this is
      what agy's brainstorm hypothesized.
  (b) neither criterion ever comes close at this specific element,
      despite being surrounded by deleted neighbors -> this element is
      simply an isolated survivor (a one-element bridge/cavity), not a
      software bug -- the "island" is a real but unremarkable outcome
      of how the crater front swept past it.

Run on ROAR: abaqus python verify_criterion_mismatch.py flat_t007.odb
"""
from __future__ import print_function
import json
import sys

from odbAccess import openOdb

GHOST_ELSET = "EMBMESH_GHOST_DIAGNOSTICS"
PLATE_INSTANCE = "PLATE-1"
GHOST_HOST_OFFSET = 24000
EPS_FAIL = 0.113800332690901

# Standard Abaqus C3D8 corner natural coordinates and full 2x2x2 Gauss
# quadrature points (+-1/sqrt(3)), weight 1.0 each -- same rule VU1 uses.
CORNERS = [
    (-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
    (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1),
]
G = 1.0 / (3.0 ** 0.5)
GAUSS_PTS = [(gx * G, gy * G, gz * G)
             for gx in (-1, 1) for gy in (-1, 1) for gz in (-1, 1)]


def shape_derivs_natural(xi, eta, zeta):
    """dN_i/d(xi,eta,zeta) for the 8 corner nodes, Abaqus C3D8 ordering."""
    out = []
    for (xi_i, eta_i, zeta_i) in CORNERS:
        dN_dxi = 0.125 * xi_i * (1 + eta * eta_i) * (1 + zeta * zeta_i)
        dN_deta = 0.125 * (1 + xi * xi_i) * eta_i * (1 + zeta * zeta_i)
        dN_dzeta = 0.125 * (1 + xi * xi_i) * (1 + eta * eta_i) * zeta_i
        out.append((dN_dxi, dN_deta, dN_dzeta))
    return out


def mat3_inv(m):
    a, b, c = m[0]
    d, e, f = m[1]
    g, h, i = m[2]
    det = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
    if abs(det) < 1e-30:
        return None, 0.0
    inv = [
        [(e * i - f * h) / det, (c * h - b * i) / det, (b * f - c * e) / det],
        [(f * g - d * i) / det, (a * i - c * g) / det, (c * d - a * f) / det],
        [(d * h - e * g) / det, (b * g - a * h) / det, (a * e - b * d) / det],
    ]
    return inv, det


def elem_maxabs_eng(ref_coords, disp):
    """ref_coords, disp: lists of 8 (x,y,z) tuples, corner order.
    Returns the element's worst |engineering normal strain| over all
    8 Gauss points, exactly mirroring VU1's ELEM_MAXABS_ENG."""
    cur = [(ref_coords[n][0] + disp[n][0],
            ref_coords[n][1] + disp[n][1],
            ref_coords[n][2] + disp[n][2]) for n in range(8)]
    worst = 0.0
    for (xi, eta, zeta) in GAUSS_PTS:
        dN_nat = shape_derivs_natural(xi, eta, zeta)
        jac = [[0.0, 0.0, 0.0] for _ in range(3)]
        for n in range(8):
            dNdxi, dNdeta, dNdzeta = dN_nat[n]
            x, y, z = ref_coords[n]
            jac[0][0] += dNdxi * x
            jac[0][1] += dNdeta * x
            jac[0][2] += dNdzeta * x
            jac[1][0] += dNdxi * y
            jac[1][1] += dNdeta * y
            jac[1][2] += dNdzeta * y
            jac[2][0] += dNdxi * z
            jac[2][1] += dNdeta * z
            jac[2][2] += dNdzeta * z
        jinv, det = mat3_inv(jac)
        if jinv is None:
            continue
        # dN/dX = Jinv * dN/dnatural (both as column vectors per node)
        dN_global = []
        for n in range(8):
            dNdxi, dNdeta, dNdzeta = dN_nat[n]
            dNdX = jinv[0][0] * dNdxi + jinv[0][1] * dNdeta + jinv[0][2] * dNdzeta
            dNdY = jinv[1][0] * dNdxi + jinv[1][1] * dNdeta + jinv[1][2] * dNdzeta
            dNdZ = jinv[2][0] * dNdxi + jinv[2][1] * dNdeta + jinv[2][2] * dNdzeta
            dN_global.append((dNdX, dNdY, dNdZ))
        # F_iJ = delta_iJ + sum_n u_i(n) * dN_n/dX_J
        F = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
        for n in range(8):
            ux, uy, uz = disp[n]
            dNdX, dNdY, dNdZ = dN_global[n]
            F[0][0] += ux * dNdX
            F[0][1] += ux * dNdY
            F[0][2] += ux * dNdZ
            F[1][0] += uy * dNdX
            F[1][1] += uy * dNdY
            F[1][2] += uy * dNdZ
            F[2][0] += uz * dNdX
            F[2][1] += uz * dNdY
            F[2][2] += uz * dNdZ
        # Green-Lagrange E = 0.5*(F^T F - I); only need normal components.
        for J in range(3):
            c = sum(F[i][J] * F[i][J] for i in range(3))
            e_jj = 0.5 * (c - 1.0)
            stretch = max(2.0 * e_jj + 1.0, 0.0) ** 0.5
            eng = stretch - 1.0
            worst = max(worst, abs(eng))
    return worst


def main(odb_path):
    odb = openOdb(odb_path, readOnly=True)
    instance = odb.rootAssembly.instances[PLATE_INSTANCE]
    ghost_set = odb.rootAssembly.elementSets[GHOST_ELSET]
    ghost_labels = set(e.label for e in ghost_set.elements[0])

    node_coords = {n.label: n.coordinates for n in instance.nodes}
    elem_conn = {}
    centroid = {}
    for e in instance.elements:
        if e.label not in ghost_labels:
            continue
        elem_conn[e.label] = list(e.connectivity)
        pts = [node_coords[n] for n in e.connectivity]
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        cz = sum(p[2] for p in pts) / len(pts)
        centroid[e.label] = (cx, cy, cz, (cx * cx + cy * cy) ** 0.5)

    step = list(odb.steps.values())[0]
    frames = step.frames
    last_frame = frames[-1]
    status_last = {v.elementLabel: v.data
                    for v in last_frame.fieldOutputs["STATUS"]
                    .getSubset(region=ghost_set).values}

    near_labels = [lbl for lbl, c in centroid.items() if c[3] <= 0.010]
    pitch_estimate = 0.05 / 24.0
    islands = []
    for lbl in near_labels:
        if status_last.get(lbl, 1.0) <= 0.5:
            continue
        cx, cy, cz, _ = centroid[lbl]
        neighbor_dead = 0
        neighbor_total = 0
        for other in near_labels:
            if other == lbl:
                continue
            ox, oy, oz, _ = centroid[other]
            d = ((cx - ox) ** 2 + (cy - oy) ** 2 + (cz - oz) ** 2) ** 0.5
            if d <= pitch_estimate * 1.6:
                neighbor_total += 1
                if status_last.get(other, 1.0) <= 0.5:
                    neighbor_dead += 1
        if neighbor_total >= 3 and neighbor_dead / float(neighbor_total) >= 0.6:
            islands.append(lbl)

    print("islands found: %d" % len(islands), file=sys.stderr)

    needed_nodes = set()
    for lbl in islands:
        needed_nodes.update(elem_conn[lbl])

    max_sdeg_by_elem = dict((lbl, (0.0, None)) for lbl in islands)
    crit_max_by_elem = dict((lbl, 0.0) for lbl in islands)
    crit_fail_frame_by_elem = dict((lbl, None) for lbl in islands)

    for fi, frame in enumerate(frames):
        sdeg_field = frame.fieldOutputs.get("SDEG")
        if sdeg_field is not None:
            for v in sdeg_field.getSubset(region=ghost_set).values:
                if v.elementLabel in max_sdeg_by_elem and v.data > max_sdeg_by_elem[v.elementLabel][0]:
                    max_sdeg_by_elem[v.elementLabel] = (v.data, fi)

        u_field = frame.fieldOutputs.get("U")
        if u_field is None:
            continue
        disp_by_node = {}
        for v in u_field.values:
            if v.instance.name == PLATE_INSTANCE and v.nodeLabel in needed_nodes:
                disp_by_node[v.nodeLabel] = v.data

        for lbl in islands:
            if crit_fail_frame_by_elem[lbl] is not None:
                continue
            conn = elem_conn[lbl]
            if any(n not in disp_by_node for n in conn):
                continue
            ref_coords = [node_coords[n] for n in conn]
            disp = [disp_by_node[n] for n in conn]
            crit = elem_maxabs_eng(ref_coords, disp)
            if crit > crit_max_by_elem[lbl]:
                crit_max_by_elem[lbl] = crit
            if crit >= EPS_FAIL:
                crit_fail_frame_by_elem[lbl] = fi

    results = []
    for ghost_lbl in islands:
        max_sdeg, sdeg_frame_idx = max_sdeg_by_elem[ghost_lbl]
        crit_max = crit_max_by_elem[ghost_lbl]
        crit_exceeded_frame_idx = crit_fail_frame_by_elem[ghost_lbl]
        results.append({
            "ghost_label": ghost_lbl,
            "host_label": ghost_lbl - GHOST_HOST_OFFSET,
            "max_vu1_equiv_eng_strain": crit_max,
            "eps_fail_threshold": EPS_FAIL,
            "vu1_equiv_would_have_failed": crit_exceeded_frame_idx is not None,
            "vu1_equiv_failed_at_frame": crit_exceeded_frame_idx,
            "ghost_max_sdeg": max_sdeg,
            "ghost_max_sdeg_at_frame": sdeg_frame_idx,
        })

    criterion_mismatch = sum(1 for r in results if r["vu1_equiv_would_have_failed"])
    isolated_survivor = sum(
        1 for r in results
        if not r["vu1_equiv_would_have_failed"] and r["ghost_max_sdeg"] < 0.5)

    report = {
        "island_count": len(islands),
        "results": results,
        "summary": {
            "criterion_mismatch_count": criterion_mismatch,
            "isolated_survivor_count": isolated_survivor,
            "total": len(results),
        },
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    odb.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: abaqus python verify_criterion_mismatch.py ODB_PATH")
    main(sys.argv[1])
