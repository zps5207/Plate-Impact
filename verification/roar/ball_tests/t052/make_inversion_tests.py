"""Generate isolation test matrix decks for impactor hex inversion investigation (T-052).

Builds a small, fast 10-deck test matrix (each solves in ~2-4 minutes on 8 CPUs)
with the 1000 m/s steel ball, differing in EXACTLY ONE ingredient from the
bt2 c2 truss + D4 (+0.002) reference deck to isolate:
  1. Reference Deck (c2 coupon: truss fibers, D4 = +0.002, element deletion=YES, default hourglass/distortion)
  2. Distortion control on (DISTORTION CONTROL=YES, LENGTH RATIO=0.1)
  3. Enhanced hourglass control (HOURGLASS=ENHANCED, EAS / tangent stiffness)
  4. Viscous hourglass control (HOURGLASS=VISCOUS, velocity damping for shock)
  5. Ball element deletion OFF (ELEMENT DELETION=NO, isolates ghost tracking vs intact inversion)
  6. Thin fiber node contact (THICKNESS = 0.050 mm, eliminates 3.7x oversized punch)
  7. No fiber contact (fibers embedded for stiffness, but excluded from contact inclusions)
  8. Uniform hex O-grid ball mesh (ball_mesh.py, 17,248 C3D8R hexes, no pole singularity)
  9. Ball-alone plain elastic plate control (isolates ball constitutive/shock under flat impact)
 10. Combined best-practice fix (Distortion control + Enhanced hourglass + Thin contact + O-grid)

Quarter-symmetry coupon (SI: m, kg, s, Pa):
  - Plate: 6 plies (16x16 hexes per ply, DX = 1.25 mm, T = 1.27 mm per ply, L = 20 mm).
  - Cohesive interfaces between plies (Hazzard numbers: 1.2/1.8 MPa, Gc 0.544/1.088 N/mm).
  - Embedded cross-ply fibers (0/90 alternating, d = 0.632 mm).
  - Ball: Quarter sphere, R = 9.525 mm, 1000 m/s in -z direction.
  - Step time: 1.2e-5 s (12 us, matching bt1/bt2 runs).
"""

from __future__ import print_function, division
import os
import sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[3]
FULL_INP = PROJECT_ROOT / "Meshing" / "vals-plywise-erode" / "native" / "output.inp"
DECKS_DIR = HERE / "decks"

# Plate coupon parameters
NPLY = 6
NX = 16
DX = 1.25e-3
T = 1.27e-3
LX = NX * DX
LY = NX * DX
T_TOTAL = NPLY * T

# Ball parameters
BALL_R = 0.009525
BALL_V0 = -1000.0
SIM_TIME = 1.2e-5  # 12 microseconds: exactly matches bt1 and bt2 test series

# Material properties
FIBER_AREA = 3.1370687601686238e-07  # m^2 (d = 0.632 mm)
FIBER_RADIUS = 0.000316


def chunks(ids, n=12):
    return [", ".join(map(str, ids[s:s + n])) for s in range(0, len(ids), n)]


def get_material_blocks(d4_val="0.002", damage_on=True):
    """Return Abaqus material cards for Steel, Matrix, and Fiber."""
    damage_block = f"""*Damage Initiation, criterion=JOHNSON COOK
 0.1152, 1.0116, -1.7684, {d4_val}, 0.5262, 1800., 293., 0.0001
*Damage Evolution, type=DISPLACEMENT
0.
""" if damage_on else ""

    steel_mat = f"""*Material, name=Steel
{damage_block}*Density
 7850.,
*Elastic
 2.03e+11, 0.33
*Plastic, hardening=JOHNSON COOK
 3.0433e+08, 4.22007e+08, 0.345, 0.87, 1800., 293.
"""

    matrix_mat = """*Material, name=Matrix
*Damage Initiation, criterion=DUCTILE
 0.01, 0.333333, 0.01
*Damage Evolution, type=ENERGY
 1460.,
*Density
 980.,
*Elastic
 7e+08, 0.45
*Plastic, extrapolation=LINEAR
 7e+07
"""

    fiber_mat = """*Material, name=Fiber
*Damage Initiation, criterion=MAXS
 3.5e+09
*Damage Evolution, type=DISPLACEMENT
0.
*Density
 2540.,
*Elastic
 7.2e+10, 0.22
"""

    cohesion_prop = """*Surface Interaction, name=Cohesion
*Cohesive Behavior
 1e+13, 1e+13, 1e+13
*Damage Initiation, criterion=MAXS
 1.2e+06, 1.8e+06, 1.8e+06
*Damage Evolution, type=ENERGY, mixed mode behavior=BK, power=1.4
 544., 1088., 1088.
*Friction
 0.3,
"""

    elastic_plate_mat = """*Material, name=ElasticPlate
*Density
 2700.,
*Elastic
 7.0e+10, 0.33
"""

    return {
        "steel": steel_mat,
        "matrix": matrix_mat,
        "fiber": fiber_mat,
        "cohesion": cohesion_prop,
        "elastic_plate": elastic_plate_mat,
    }


def extract_nominal_ball(inp_path=FULL_INP):
    """Extract nominal quarter-ball nodes and elements from full deck."""
    p1 = np.array([0., 0., 0.011])
    axis = np.array([-1., 0., 0.])
    theta = np.radians(90.0)

    def transform(v):
        v_rot = v * np.cos(theta) + np.cross(axis, v) * np.sin(theta) + axis * np.dot(axis, v) * (1.0 - np.cos(theta))
        return p1 + v_rot

    nodes, c3d8r, c3d6 = {}, [], []
    in_ball, mode = False, None
    with open(inp_path, "r", encoding="utf-8") as f:
        for line in f:
            line_s = line.strip()
            if line_s.startswith("*Part, name=Ball"):
                in_ball = True
                continue
            if in_ball and line_s.startswith("*End Part"):
                break
            if in_ball:
                if line_s.startswith("*Node"):
                    mode = "node"
                    continue
                elif line_s.startswith("*Element, type=C3D8R"):
                    mode = "c3d8r"
                    continue
                elif line_s.startswith("*Element, type=C3D6"):
                    mode = "c3d6"
                    continue
                elif line_s.startswith("*"):
                    mode = None
                    continue
                if mode == "node":
                    parts = [x.strip() for x in line_s.split(",") if x.strip()]
                    raw_coord = np.array([float(x) for x in parts[1:4]])
                    nodes[int(parts[0])] = transform(raw_coord)
                elif mode == "c3d8r":
                    parts = [int(x.strip()) for x in line_s.split(",") if x.strip()]
                    c3d8r.append((parts[0], parts[1:]))
                elif mode == "c3d6":
                    parts = [int(x.strip()) for x in line_s.split(",") if x.strip()]
                    c3d6.append((parts[0], parts[1:]))

    # Identify symmetry nodes
    sym_x, sym_y = [], []
    for nid, c in nodes.items():
        if abs(c[0]) < 1e-6:
            sym_x.append(nid)
        if abs(c[1]) < 1e-6:
            sym_y.append(nid)

    return {
        "nodes": nodes,
        "c3d8r": c3d8r,
        "c3d6": c3d6,
        "sym_x": sorted(sym_x),
        "sym_y": sorted(sym_y),
    }


def build_ogrid_quarter_ball(n=28, nr=10, hc=0.5):
    """Build uniform O-grid quarter ball (100% C3D8R hexes, no pole singularity)."""
    R = BALL_R
    h = hc * R
    g = np.linspace(-1, 1, n + 1)
    keys = {}
    pts = []

    def node(p):
        k = tuple(np.round(p / 1e-9).astype(np.int64))
        i = keys.get(k)
        if i is None:
            i = keys[k] = len(pts)
            pts.append(p)
        return i

    hexes = []
    # inner cube
    ix = np.empty((n + 1,) * 3, dtype=np.int64)
    for i in range(n + 1):
        for j in range(n + 1):
            for k in range(n + 1):
                ix[i, j, k] = node(h * np.array([g[i], g[j], g[k]]))
    for i in range(n):
        for j in range(n):
            for k in range(n):
                hexes.append([ix[i, j, k], ix[i + 1, j, k], ix[i + 1, j + 1, k], ix[i, j + 1, k],
                              ix[i, j, k + 1], ix[i + 1, j, k + 1], ix[i + 1, j + 1, k + 1], ix[i, j + 1, k + 1]])

    # outer blocks: axis permutations of the +z block
    perms = [(0, 1, 2), (1, 2, 0), (2, 0, 1)]
    for perm in perms:
        for sign in (1.0, -1.0):
            lay = np.empty((n + 1, n + 1, nr + 1), dtype=np.int64)
            for a in range(n + 1):
                for b in range(n + 1):
                    t_ = np.tan(np.pi / 4 * np.array([g[a], g[b]]))
                    d = np.array([t_[0], t_[1], 1.0])
                    d = d / np.linalg.norm(d) * R
                    inner = np.array([h * g[a], h * g[b], h])
                    for r in range(nr + 1):
                        w = r / nr
                        p = (1 - w) * inner + w * d
                        q = np.empty(3)
                        q[perm[0]], q[perm[1]], q[perm[2]] = p[0], p[1], p[2] * sign
                        lay[a, b, r] = node(q)
            for a in range(n):
                for b in range(n):
                    for r in range(nr):
                        hexes.append([lay[a, b, r], lay[a + 1, b, r], lay[a + 1, b + 1, r], lay[a, b + 1, r],
                                     lay[a, b, r + 1], lay[a + 1, b, r + 1], lay[a + 1, b + 1, r + 1], lay[a, b + 1, r + 1]])

    pts = np.array(pts)
    hexes = np.array(hexes)

    # Orient hexes positively
    P = pts[hexes]
    vol = np.einsum("ij,ij->i", np.cross(P[:, 1] - P[:, 0], P[:, 3] - P[:, 0]), P[:, 4] - P[:, 0])
    flip = vol < 0
    hexes[flip] = hexes[flip][:, [0, 3, 2, 1, 4, 7, 6, 5]]

    # Keep the x >= 0, z >= 0 quarter in part frame
    cen = pts[hexes].mean(1)
    keep = (cen[:, 0] > 0) & (cen[:, 2] > 0)
    hexes = hexes[keep]
    used = np.unique(hexes)
    remap = -np.ones(len(pts), dtype=np.int64)
    remap[used] = np.arange(len(used))
    pts, hexes = pts[used], remap[hexes]

    # Transform to assembly frame: (0, 0, 0.011) + 90 deg rotation about [-1,0,0]
    p1 = np.array([0., 0., 0.011])
    axis = np.array([-1., 0., 0.])
    theta = np.radians(90.0)

    def transform(v):
        v_rot = v * np.cos(theta) + np.cross(axis, v) * np.sin(theta) + axis * np.dot(axis, v) * (1.0 - np.cos(theta))
        return p1 + v_rot

    t_nodes = {}
    for i, p in enumerate(pts):
        t_nodes[i + 1] = transform(p)

    c3d8r = []
    for i, h in enumerate(hexes):
        c3d8r.append((i + 1, [int(k + 1) for k in h]))

    sym_x, sym_y = [], []
    for nid, c in t_nodes.items():
        if abs(c[0]) < 1e-6:
            sym_x.append(nid)
        if abs(c[1]) < 1e-6:
            sym_y.append(nid)

    return {
        "nodes": t_nodes,
        "c3d8r": c3d8r,
        "c3d6": [],
        "sym_x": sorted(sym_x),
        "sym_y": sorted(sym_y),
    }


def make_plate_coupon(nply=NPLY, nx=NX, dx=DX, t=T):
    """Generate 6-ply plate coupon mesh."""
    nodes = {}
    elems = {}
    ply_elems = {p: [] for p in range(nply)}
    sym_x = []
    sym_y = []
    edge_nodes = []

    def nid(i, j, k):
        return k * (nx + 1) * (nx + 1) + j * (nx + 1) + i + 1

    def eid(i, j, k):
        return k * nx * nx + j * nx + i + 1

    for k in range(nply + 1):
        z = -k * t
        for j in range(nx + 1):
            y = j * dx
            for i in range(nx + 1):
                x = i * dx
                n = nid(i, j, k)
                nodes[n] = np.array([x, y, z])
                if i == 0:
                    sym_x.append(n)
                if j == 0:
                    sym_y.append(n)
                if i == nx or j == nx:
                    edge_nodes.append(n)

    for k in range(nply):
        for j in range(nx):
            for i in range(nx):
                e = eid(i, j, k)
                n1 = nid(i, j, k + 1)
                n2 = nid(i + 1, j, k + 1)
                n3 = nid(i + 1, j + 1, k + 1)
                n4 = nid(i, j + 1, k + 1)
                n5 = nid(i, j, k)
                n6 = nid(i + 1, j, k)
                n7 = nid(i + 1, j + 1, k)
                n8 = nid(i, j + 1, k)
                elems[e] = [n1, n2, n3, n4, n5, n6, n7, n8]
                ply_elems[k].append(e)

    return {
        "nodes": nodes,
        "elems": elems,
        "ply_elems": ply_elems,
        "sym_x": sorted(set(sym_x)),
        "sym_y": sorted(set(sym_y)),
        "edge_nodes": sorted(set(edge_nodes)),
    }


def make_plain_elastic_plate(nx=NX, dx=DX, total_t=T_TOTAL):
    """Generate single-block homogeneous elastic plate."""
    nodes = {}
    elems = {}
    sym_x = []
    sym_y = []
    edge_nodes = []
    top_elems = []
    nz = 12

    def nid(i, j, k):
        return k * (nx + 1) * (nx + 1) + j * (nx + 1) + i + 1

    def eid(i, j, k):
        return k * nx * nx + j * nx + i + 1

    dz = total_t / nz
    for k in range(nz + 1):
        z = -k * dz
        for j in range(nx + 1):
            y = j * dx
            for i in range(nx + 1):
                x = i * dx
                n = nid(i, j, k)
                nodes[n] = np.array([x, y, z])
                if i == 0:
                    sym_x.append(n)
                if j == 0:
                    sym_y.append(n)
                if i == nx or j == nx:
                    edge_nodes.append(n)

    for k in range(nz):
        for j in range(nx):
            for i in range(nx):
                e = eid(i, j, k)
                n1 = nid(i, j, k + 1)
                n2 = nid(i + 1, j, k + 1)
                n3 = nid(i + 1, j + 1, k + 1)
                n4 = nid(i, j + 1, k + 1)
                n5 = nid(i, j, k)
                n6 = nid(i + 1, j, k)
                n7 = nid(i + 1, j + 1, k)
                n8 = nid(i, j + 1, k)
                elems[e] = [n1, n2, n3, n4, n5, n6, n7, n8]
                if k == 0:
                    top_elems.append(e)

    return {
        "nodes": nodes,
        "elems": elems,
        "top_elems": top_elems,
        "sym_x": sorted(set(sym_x)),
        "sym_y": sorted(set(sym_y)),
        "edge_nodes": sorted(set(edge_nodes)),
    }


def make_fibers(nply=NPLY, nx=NX, dx=DX, t=T, base_nid=100001, base_eid=100001, elem_type="T3D2"):
    """Generate cross-ply embedded fibers at mid-planes of each ply."""
    nodes = {}
    elems = {}
    sym_x = []
    sym_y = []
    edge_nodes = []
    curr_nid = base_nid
    curr_eid = base_eid

    for p in range(nply):
        z = -(p + 0.5) * t
        is_x_dir = (p % 2 == 0)
        nfibers = nx + 1

        for fib in range(nfibers):
            line_nodes = []
            for seg in range(nx + 1):
                if is_x_dir:
                    x = seg * dx
                    y = fib * dx
                else:
                    x = fib * dx
                    y = seg * dx
                n = curr_nid
                curr_nid += 1
                nodes[n] = np.array([x, y, z])
                line_nodes.append(n)
                if abs(x) < 1e-6:
                    sym_x.append(n)
                if abs(y) < 1e-6:
                    sym_y.append(n)
                if abs(x - nx * dx) < 1e-6 or abs(y - nx * dx) < 1e-6:
                    edge_nodes.append(n)

            for seg in range(nx):
                e = curr_eid
                curr_eid += 1
                elems[e] = (line_nodes[seg], line_nodes[seg + 1])

    return {
        "nodes": nodes,
        "elems": elems,
        "sym_x": sorted(set(sym_x)),
        "sym_y": sorted(set(sym_y)),
        "edge_nodes": sorted(set(edge_nodes)),
    }


def build_deck(config, nominal_ball, ogrid_ball):
    """Build a complete self-contained Abaqus/Explicit input deck."""
    name = config["name"]
    desc = config["desc"]
    ball_type = config.get("ball_mesh", "nominal")
    damage_on = config.get("damage_on", True)
    plate_type = config.get("plate_type", "coupon")
    has_fibers = config.get("has_fibers", True)
    fiber_elem = config.get("fiber_elem", "T3D2")
    fiber_contact = config.get("fiber_contact", "node")  # 'node', 'beam', 'none'
    fiber_thick = config.get("fiber_thick", 0.000617973861320424)

    # Ball section controls
    ball_del = config.get("ball_element_deletion", "YES")
    ball_hg = config.get("ball_hourglass", "RELAX STIFFNESS")
    ball_distort = config.get("ball_distortion_control", False)
    ball_len_ratio = config.get("ball_length_ratio", 0.1)

    ball = nominal_ball if ball_type == "nominal" else ogrid_ball
    mats = get_material_blocks(d4_val="0.002", damage_on=damage_on)
    if config.get("ball_material") == "elastic":
        # purely elastic ball (no plasticity, no damage): a limit case to see how the plate deforms
        mats["steel"] = "*Material, name=Steel\n*Density\n 7850.,\n*Elastic\n %.4e, 0.33\n" % config.get("ball_E", 2.03e11)

    # Node ID offset for Ball to avoid collisions
    ball_nid_offset = 200000
    ball_eid_offset = 200000

    lines = [
        "*Heading",
        f"** T-052 Hex Inversion Matrix: {name}",
        f"** {desc}",
        "*Preprint, echo=NO, model=NO, history=NO, contact=NO",
    ]

    # --- NODES ---
    lines.append("*Node")
    # Ball nodes
    for nid, c in ball["nodes"].items():
        lines.append(f"{nid + ball_nid_offset}, {c[0]:.8e}, {c[1]:.8e}, {c[2]:.8e}")

    sym_x_all = [nid + ball_nid_offset for nid in ball["sym_x"]]
    sym_y_all = [nid + ball_nid_offset for nid in ball["sym_y"]]
    edge_all = []

    # Plate nodes & elements
    if plate_type == "coupon":
        plate = make_plate_coupon()
        for nid, c in plate["nodes"].items():
            lines.append(f"{nid}, {c[0]:.8e}, {c[1]:.8e}, {c[2]:.8e}")
        sym_x_all += plate["sym_x"]
        sym_y_all += plate["sym_y"]
        edge_all += plate["edge_nodes"]
    else:  # plain elastic plate
        plate = make_plain_elastic_plate()
        for nid, c in plate["nodes"].items():
            lines.append(f"{nid}, {c[0]:.8e}, {c[1]:.8e}, {c[2]:.8e}")
        sym_x_all += plate["sym_x"]
        sym_y_all += plate["sym_y"]
        edge_all += plate["edge_nodes"]

    # Fiber nodes
    fibers = None
    if has_fibers:
        fibers = make_fibers(elem_type=fiber_elem)
        for nid, c in fibers["nodes"].items():
            lines.append(f"{nid}, {c[0]:.8e}, {c[1]:.8e}, {c[2]:.8e}")
        sym_x_all += fibers["sym_x"]
        sym_y_all += fibers["sym_y"]
        edge_all += fibers["edge_nodes"]

    # --- ELEMENTS ---
    # Ball elements
    ball_c3d8r = [f"{eid + ball_eid_offset}, " + ", ".join(str(n + ball_nid_offset) for n in conn)
                  for eid, conn in ball["c3d8r"]]
    lines.append("*Element, type=C3D8R, elset=BALL_C3D8R")
    lines.extend(ball_c3d8r)

    if ball["c3d6"]:
        ball_c3d6 = [f"{eid + ball_eid_offset}, " + ", ".join(str(n + ball_nid_offset) for n in conn)
                     for eid, conn in ball["c3d6"]]
        lines.append("*Element, type=C3D6, elset=BALL_C3D6")
        lines.extend(ball_c3d6)
        lines.extend(["*Elset, elset=BALL_ELEMS", "BALL_C3D8R, BALL_C3D6"])
    else:
        lines.extend(["*Elset, elset=BALL_ELEMS", "BALL_C3D8R"])

    # Ball surface
    lines.extend([
        "*Surface, type=ELEMENT, name=BALL_SURF",
        "BALL_ELEMS,",
    ])

    # Plate elements
    if plate_type == "coupon":
        lines.append("*Element, type=C3D8R")
        for eid, conn in plate["elems"].items():
            lines.append(f"{eid}, " + ", ".join(map(str, conn)))
        all_host = []
        for p in range(NPLY):
            lines.append(f"*Elset, elset=PLY{p}")
            lines.extend(chunks(plate["ply_elems"][p]))
            all_host.extend(plate["ply_elems"][p])
            lines.extend([
                f"*Surface, type=ELEMENT, name=PLY{p}_TOP", f"PLY{p}, S2",
                f"*Surface, type=ELEMENT, name=PLY{p}_BOT", f"PLY{p}, S1"
            ])
        lines.append("*Elset, elset=HOST")
        lines.extend(chunks(all_host))
        lines.extend([
            "*Surface, type=ELEMENT, name=HOST_SURF",
            "HOST,",
        ])
    else:  # plain elastic plate
        lines.append("*Element, type=C3D8R, elset=PLATE_ELEMS")
        for eid, conn in plate["elems"].items():
            lines.append(f"{eid}, " + ", ".join(map(str, conn)))
        lines.append("*Elset, elset=PLATE_TOP_ELEMS")
        lines.extend(chunks(plate["top_elems"]))
        lines.extend([
            "*Surface, type=ELEMENT, name=PLATE_SURF",
            "PLATE_TOP_ELEMS, S2",
        ])

    # Fiber elements
    if has_fibers:
        lines.append(f"*Element, type={fiber_elem}, elset=FIBERS")
        for eid, conn in fibers["elems"].items():
            lines.append(f"{eid}, {conn[0]}, {conn[1]}")
        lines.append("*Nset, nset=FIBER_NODES")
        lines.extend(chunks(sorted(fibers["nodes"].keys())))
        if fiber_contact == "node":
            lines.extend([
                "*Surface, type=NODE, name=FIBER_NODES",
                "FIBER_NODES",
            ])
        elif fiber_contact == "beam":
            lines.extend([
                "*Surface, type=ELEMENT, name=FIBER_SURF",
                "FIBERS,",
            ])

    # Node sets for BCs and initial conditions
    lines.append("*Nset, nset=BALL_NODES")
    lines.extend(chunks([nid + ball_nid_offset for nid in ball["nodes"].keys()]))
    lines.append("*Nset, nset=SYM_X")
    lines.extend(chunks(sorted(set(sym_x_all))))
    lines.append("*Nset, nset=SYM_Y")
    lines.extend(chunks(sorted(set(sym_y_all))))
    lines.append("*Nset, nset=FIX_EDGE")
    lines.extend(chunks(sorted(set(edge_all))))

    # --- SECTIONS & SECTION CONTROLS ---
    # Construct ball section control card
    ctrl_ball_parts = [f"*Section Controls, name=CTRL_BALL, element deletion={ball_del}"]
    if ball_hg != "RELAX STIFFNESS":
        ctrl_ball_parts.append(f"hourglass={ball_hg}")
    if ball_distort:
        ctrl_ball_parts.append("distortion control=YES")
        ctrl_ball_parts.append(f"length ratio={ball_len_ratio:g}")

    ctrl_ball_header = ", ".join(ctrl_ball_parts)
    lines.append(ctrl_ball_header)

    # Standard controls for host/fibers
    lines.append("*Section Controls, name=EMBMESH_DELETE_ALL, element deletion=YES, max degradation=0.8")

    lines.extend([
        f"*Solid Section, elset=BALL_ELEMS, material=Steel, controls=CTRL_BALL",
    ])
    lines.append(mats["steel"].rstrip())

    if plate_type == "coupon":
        lines.extend([
            "*Solid Section, elset=HOST, material=Matrix, controls=EMBMESH_DELETE_ALL",
            mats["matrix"].rstrip(),
            mats["cohesion"].rstrip(),
        ])
    else:
        lines.extend([
            "*Solid Section, elset=PLATE_ELEMS, material=ElasticPlate",
            mats["elastic_plate"].rstrip(),
        ])

    if has_fibers:
        if fiber_elem == "T3D2":
            lines.extend([
                "*Solid Section, elset=FIBERS, material=Fiber, controls=EMBMESH_DELETE_ALL",
                f"{FIBER_AREA}",
            ])
        else:  # B31 beam
            lines.extend([
                "*Beam Section, elset=FIBERS, material=Fiber, section=CIRC, controls=EMBMESH_DELETE_ALL",
                f"{FIBER_RADIUS}",
                "0., 0., 1.",
            ])
        lines.append(mats["fiber"].rstrip())
        lines.extend([
            "*Embedded Element, host elset=HOST",
            "FIBERS",
        ])

    # Contact interaction properties
    lines.extend([
        "*Surface Interaction, name=General",
        "*Friction",
        " 0.01,",
        "*Surface Behavior, pressure-overclosure=HARD",
    ])

    # Boundary conditions
    lines.extend([
        "*Boundary",
        "SYM_X, XSYMM",
        "SYM_Y, YSYMM",
        "FIX_EDGE, ENCASTRE",
        "*Initial Conditions, type=VELOCITY",
        f"BALL_NODES, 3, {BALL_V0}",
    ])

    # --- STEP ---
    lines.extend([
        "*Step, name=Impact, nlgeom=YES",
        "*Dynamic, Explicit",
        f", {SIM_TIME:g}",
        "*Bulk Viscosity",
        "0.06, 1.2",
        "*Contact",
        "*Contact Inclusions",
    ])

    if plate_type == "coupon":
        lines.append("HOST_SURF, BALL_SURF")
        for p in range(NPLY - 1):
            lines.append(f"PLY{p}_TOP, PLY{p+1}_BOT")
        if has_fibers and fiber_contact == "node":
            lines.append("FIBER_NODES, BALL_SURF")
        elif has_fibers and fiber_contact == "beam":
            lines.append("FIBER_SURF, BALL_SURF")

        lines.extend([
            "*Contact Property Assignment",
            " , , General",
        ])
        for p in range(NPLY - 1):
            lines.append(f"PLY{p}_TOP, PLY{p+1}_BOT, Cohesion")

        if has_fibers and fiber_contact == "node":
            lines.extend([
                "*Surface Property Assignment, property=THICKNESS",
                f"FIBER_NODES, {fiber_thick:.12g}",
            ])
    else:  # plain elastic plate
        lines.extend([
            "PLATE_SURF, BALL_SURF",
            "*Contact Property Assignment",
            " , , General",
        ])

    # Output requests
    lines.extend([
        "*Output, field, time interval=3e-07",
        "*Node Output",
        "U, V",
        "*Element Output, elset=BALL_ELEMS",
        "STATUS, S, PEEQ, EVOL",
    ])

    if plate_type == "coupon":
        lines.extend([
            "*Element Output, elset=HOST",
            "STATUS, S, PEEQ",
        ])
    if has_fibers:
        lines.extend([
            "*Element Output, elset=FIBERS",
            "STATUS, S, LE",
        ])

    lines.extend([
        "*Contact Output",
        "CSDMG, CSTRESS, CDISP",
        "*Output, history, time interval=1e-07",
        "*Energy Output",
        "ALLKE, ALLIE, ALLSE, ALLPD, ALLDMD, ALLFD, ALLVD, ALLAE, ALLWK, ETOTAL",
        "*End Step",
    ])

    return "\n".join(lines) + "\n"


# =====================================================================
# Isolation Matrix Configurations (10 Decks)
# =====================================================================
MATRIX = [
    {
        "id": "01",
        "name": "t052_01_ref_truss_d4",
        "desc": "Reference Deck: 6-ply coupon, T3D2 fibers (thick 0.618 mm), JC D4=+0.002, element deletion=YES (default hourglass/distortion)",
        "ball_mesh": "nominal",
        "damage_on": True,
        "ball_element_deletion": "YES",
        "ball_hourglass": "RELAX STIFFNESS",
        "ball_distortion_control": False,
        "plate_type": "coupon",
        "has_fibers": True,
        "fiber_elem": "T3D2",
        "fiber_contact": "node",
        "fiber_thick": 0.000617973861320424,
        "isolates": "bt2 c2 truss + D4 reference baseline behavior on fast 6-ply coupon",
    },
    {
        "id": "02",
        "name": "t052_02_distortion_control_on",
        "desc": "Distortion Control ON: DISTORTION CONTROL=YES, LENGTH RATIO=0.1 on ball",
        "ball_mesh": "nominal",
        "damage_on": True,
        "ball_element_deletion": "YES",
        "ball_hourglass": "RELAX STIFFNESS",
        "ball_distortion_control": True,
        "ball_length_ratio": 0.1,
        "plate_type": "coupon",
        "has_fibers": True,
        "fiber_elem": "T3D2",
        "fiber_contact": "node",
        "fiber_thick": 0.000617973861320424,
        "isolates": "Distortion control restoring penalty against corner Jacobian collapse prior to deletion",
    },
    {
        "id": "03",
        "name": "t052_03_hourglass_enhanced",
        "desc": "Enhanced Hourglass Control: HOURGLASS=ENHANCED (assumed strain / tangent stiffness) on ball",
        "ball_mesh": "nominal",
        "damage_on": True,
        "ball_element_deletion": "YES",
        "ball_hourglass": "ENHANCED",
        "ball_distortion_control": False,
        "plate_type": "coupon",
        "has_fibers": True,
        "fiber_elem": "T3D2",
        "fiber_contact": "node",
        "fiber_thick": 0.000617973861320424,
        "isolates": "Physical tangent-stiffness hourglass resistance suppressing zero-energy C3D8R modes under large plastic strain",
    },
    {
        "id": "04",
        "name": "t052_04_hourglass_viscous",
        "desc": "Viscous Hourglass Control: HOURGLASS=VISCOUS (velocity-proportional damping) on ball",
        "ball_mesh": "nominal",
        "damage_on": True,
        "ball_element_deletion": "YES",
        "ball_hourglass": "VISCOUS",
        "ball_distortion_control": False,
        "plate_type": "coupon",
        "has_fibers": True,
        "fiber_elem": "T3D2",
        "fiber_contact": "node",
        "fiber_thick": 0.000617973861320424,
        "isolates": "High-velocity shock wave damping of transient spatial hourglass ringing",
    },
    {
        "id": "05",
        "name": "t052_05_ball_no_deletion",
        "desc": "Ball Element Deletion OFF: ELEMENT DELETION=NO (vp6 behavior on coupon)",
        "ball_mesh": "nominal",
        "damage_on": False,
        "ball_element_deletion": "NO",
        "ball_hourglass": "RELAX STIFFNESS",
        "ball_distortion_control": False,
        "plate_type": "coupon",
        "has_fibers": True,
        "fiber_elem": "T3D2",
        "fiber_contact": "node",
        "fiber_thick": 0.000617973861320424,
        "isolates": "Neighbour element loss of support vs unconstrained orphan node tracking artifact",
    },
    {
        "id": "06",
        "name": "t052_06_fiber_contact_thin_0050",
        "desc": "Thin Fiber Contact: Fiber node contact THICKNESS = 0.050 mm (50 um, 12x reduction)",
        "ball_mesh": "nominal",
        "damage_on": True,
        "ball_element_deletion": "YES",
        "ball_hourglass": "RELAX STIFFNESS",
        "ball_distortion_control": False,
        "plate_type": "coupon",
        "has_fibers": True,
        "fiber_elem": "T3D2",
        "fiber_contact": "node",
        "fiber_thick": 0.000050,
        "isolates": "Fiber node oversized punch effect (eliminates 0.618 mm rigid sphere needle punch)",
    },
    {
        "id": "07",
        "name": "t052_07_fiber_contact_none",
        "desc": "No Fiber Contact: Fibers embedded in matrix for coupon stiffness, but removed from contact inclusions",
        "ball_mesh": "nominal",
        "damage_on": True,
        "ball_element_deletion": "YES",
        "ball_hourglass": "RELAX STIFFNESS",
        "ball_distortion_control": False,
        "plate_type": "coupon",
        "has_fibers": True,
        "fiber_elem": "T3D2",
        "fiber_contact": "none",
        "isolates": "Direct fiber contact force contribution vs pure host matrix interaction",
    },
    {
        "id": "08",
        "name": "t052_08_ball_ogrid_mesh",
        "desc": "Uniform Hex O-Grid Ball Mesh: 17,248 C3D8R hexes (ball_mesh.py, no pole singularity)",
        "ball_mesh": "ogrid",
        "damage_on": True,
        "ball_element_deletion": "YES",
        "ball_hourglass": "RELAX STIFFNESS",
        "ball_distortion_control": False,
        "plate_type": "coupon",
        "has_fibers": True,
        "fiber_elem": "T3D2",
        "fiber_contact": "node",
        "fiber_thick": 0.000617973861320424,
        "isolates": "Pole singularity and wedge-hex transition in nominal ball mesh",
    },
    {
        "id": "09",
        "name": "t052_09_ball_alone_plain_plate",
        "desc": "Ball Alone Control: Ball impacting homogeneous plain elastic plate (no fibers, no cohesive interfaces)",
        "ball_mesh": "nominal",
        "damage_on": True,
        "ball_element_deletion": "YES",
        "ball_hourglass": "RELAX STIFFNESS",
        "ball_distortion_control": False,
        "plate_type": "plain_elastic",
        "has_fibers": False,
        "fiber_contact": "none",
        "isolates": "Ball constitutive / shock response against flat planar boundary (zero laminate complexity)",
    },
    {
        "id": "10",
        "name": "t052_10_combined_best_practice",
        "desc": "Combined Best Practice: Distortion control ON + Enhanced hourglass + Thin contact (0.05 mm) + O-grid mesh",
        "ball_mesh": "ogrid",
        "damage_on": True,
        "ball_element_deletion": "YES",
        "ball_hourglass": "ENHANCED",
        "ball_distortion_control": True,
        "ball_length_ratio": 0.1,
        "plate_type": "coupon",
        "has_fibers": True,
        "fiber_elem": "T3D2",
        "fiber_contact": "node",
        "fiber_thick": 0.000050,
        "isolates": "Synergistic stabilization of numerical controls and contact geometry",
    },
    {
        "id": "11",
        "name": "t052_11_ball_elastic",
        "desc": "Elastic ball (E = 203 GPa, no plasticity, no damage) on the reference 6-ply coupon: shows how the plate deforms without ball failure",
        "ball_mesh": "nominal",
        "ball_material": "elastic",
        "damage_on": False,
        "ball_element_deletion": "NO",
        "ball_hourglass": "RELAX STIFFNESS",
        "ball_distortion_control": False,
        "plate_type": "coupon",
        "has_fibers": True,
        "fiber_elem": "T3D2",
        "fiber_contact": "node",
        "fiber_thick": 0.000617973861320424,
        "isolates": "Plate response to an unbreakable ball (stress in the ball is unphysical, far above yield)",
    },
    {
        "id": "12",
        "name": "t052_12_ball_stiff_elastic",
        "desc": "Near-rigid ball (elastic, E = 2.03 TPa = 10x steel, no plasticity, no damage) on the reference coupon: upper-bound plate loading",
        "ball_mesh": "nominal",
        "ball_material": "elastic",
        "ball_E": 2.03e12,
        "damage_on": False,
        "ball_element_deletion": "NO",
        "ball_hourglass": "RELAX STIFFNESS",
        "ball_distortion_control": False,
        "plate_type": "coupon",
        "has_fibers": True,
        "fiber_elem": "T3D2",
        "fiber_contact": "node",
        "fiber_thick": 0.000617973861320424,
        "isolates": "Plate response to a nearly rigid impactor (a rigid ball spreads load less than real steel, so this overstates local plate loading)",
    },
]


def main():
    DECKS_DIR.mkdir(parents=True, exist_ok=True)
    print("=== Generating T-052 Hex Inversion Test Matrix ===")

    print("Extracting nominal ball from full deck...")
    nominal_ball = extract_nominal_ball()
    print(f"  Nominal ball: {len(nominal_ball['nodes'])} nodes, {len(nominal_ball['c3d8r'])} C3D8R, {len(nominal_ball['c3d6'])} C3D6")

    print("Building uniform hex O-grid ball...")
    ogrid_ball = build_ogrid_quarter_ball(n=28, nr=10, hc=0.5)
    print(f"  O-grid ball: {len(ogrid_ball['nodes'])} nodes, {len(ogrid_ball['c3d8r'])} C3D8R, {len(ogrid_ball['c3d6'])} C3D6")

    for cfg in MATRIX:
        name = cfg["name"]
        deck_content = build_deck(cfg, nominal_ball, ogrid_ball)
        out_path = DECKS_DIR / f"{name}.inp"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(deck_content)
        nlines = deck_content.count("\n")
        print(f"  [{cfg['id']}] Generated {name}.inp ({nlines:,} lines)")

    print(f"\nAll decks successfully generated in: {DECKS_DIR}")


if __name__ == "__main__":
    main()
