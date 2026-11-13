"""Generate isolation test matrix decks for impactor failure investigation (T-049).

Builds a small, fast 10-deck test matrix (each solves in ~2-4 minutes on 8 CPUs)
with the real steel ball (1000 m/s, JC plasticity, JC damage ON/OFF), differing
in ONE ingredient at a time to isolate:
  1. Plain plate baseline (material/mesh stability, negative JC d4 pathology)
  2. Host matrix interaction (eroding surface alone vs embedded fibers)
  3. Fiber contact thickness (nominal 0.618 mm vs thin 0.05 mm vs removed)
  4. Ball element discretization (nominal 18.5k elements vs coarse 2k elements)
  5. Fiber contact formulation (penalty scaling vs continuous beam element surface)

Quarter-symmetry coupon (SI: m, kg, s, Pa):
  - Plate: 6 plies (16x16 hexes per ply, DX = 1.25 mm, T = 1.27 mm per ply, L = 20 mm).
  - Cohesive interfaces between plies (Hazzard numbers: 1.2/1.8 MPa, Gc 0.544/1.088 N/mm).
  - Embedded cross-ply fibers (0/90 alternating, d = 0.632 mm).
  - Ball: Quarter sphere, R = 9.525 mm, 1000 m/s in -z direction.
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
SIM_TIME = 1.5e-5  # 15 microseconds: captures impact and full coupon perforation

# Material properties
FIBER_AREA = 3.1370687601686238e-07  # m^2 (d = 0.632 mm)
FIBER_RADIUS = 0.000316


def chunks(ids, n=12):
    return [", ".join(map(str, ids[s:s + n])) for s in range(0, len(ids), n)]


def get_material_blocks(damage_on=True):
    """Return Abaqus material cards for Steel, Matrix, and Fiber."""
    damage_block = """*Damage Initiation, criterion=JOHNSON COOK
 0.1152, 1.0116, -1.7684, -0.05279, 0.5262, 1800., 293., 0.0001
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
 7e+07, 0.
"""

    fiber_mat = """*Material, name=Fiber
*Damage Initiation, criterion=DUCTILE
 0.0391, 0.333333, 0.01
 0.0251, 0.333333, 1.
 0.01167, 0.333333, 1000.
*Damage Evolution, type=DISPLACEMENT
0.
*Density
 981.,
*Elastic
 1.35e+11, 0.45
*Plastic
 3.5e+09, 0.
*Plastic, rate=1.
 4.3e+09, 0.
*Plastic, rate=1000.
 4.5e+09, 0.
"""

    cohesive_mat = """*Surface Interaction, name=Cohesion
*Cohesive Behavior
 6e+10, 3.6e+10, 3.6e+10
*Damage Initiation, criterion=MAXS
 1.2e+06, 1.8e+06, 1.8e+06
*Damage Evolution, type=ENERGY, mixed mode behavior=POWER LAW, power=1
 544, 1088, 1088
"""

    elastic_plate_mat = """*Material, name=ElasticSteel
*Density
 7850.,
*Elastic
 2.03e+11, 0.33
"""
    return {
        "steel": steel_mat,
        "matrix": matrix_mat,
        "fiber": fiber_mat,
        "cohesion": cohesive_mat,
        "elastic_plate": elastic_plate_mat,
    }


def extract_nominal_ball(inp_path=FULL_INP):
    """Extract nominal quarter-ball nodes and elements from full deck."""
    p1 = np.array([0., 0., 0.011])
    axis = np.array([-1., 0., 0.])
    theta = np.radians(90.0)

    def transform(v):
        v_rot = v * np.cos(theta) + np.cross(axis, v) * np.sin(theta) + axis * np.dot(v, axis) * (1.0 - np.cos(theta))
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


def make_coarse_ball(R=BALL_R, Nu=10, Nv=10, Nw=20, z_center=0.011):
    """Generate coarse quarter-ball mesh (2,000 hex elements, no wedges)."""
    u_vals = np.linspace(0, 1, Nu + 1)
    v_vals = np.linspace(0, 1, Nv + 1)
    w_vals = np.linspace(-1, 1, Nw + 1)

    node_id = 1
    nodes, grid = {}, {}
    sym_x, sym_y = [], []
    for k, w in enumerate(w_vals):
        for j, v in enumerate(v_vals):
            for i, u in enumerate(u_vals):
                x = u * np.sqrt(np.maximum(0, 1.0 - v**2/2.0 - w**2/2.0 + (v**2 * w**2)/3.0)) * R
                y = v * np.sqrt(np.maximum(0, 1.0 - u**2/2.0 - w**2/2.0 + (u**2 * w**2)/3.0)) * R
                z = w * np.sqrt(np.maximum(0, 1.0 - u**2/2.0 - v**2/2.0 + (u**2 * v**2)/3.0)) * R + z_center
                nodes[node_id] = np.array([x, y, z])
                grid[(i, j, k)] = node_id
                if i == 0:
                    sym_x.append(node_id)
                if j == 0:
                    sym_y.append(node_id)
                node_id += 1

    elems = []
    elem_id = 1
    for k in range(Nw):
        for j in range(Nv):
            for i in range(Nu):
                n1 = grid[(i, j, k)]
                n2 = grid[(i+1, j, k)]
                n3 = grid[(i+1, j+1, k)]
                n4 = grid[(i, j+1, k)]
                n5 = grid[(i, j, k+1)]
                n6 = grid[(i+1, j, k+1)]
                n7 = grid[(i+1, j+1, k+1)]
                n8 = grid[(i, j+1, k+1)]
                elems.append((elem_id, [n1, n2, n3, n4, n5, n6, n7, n8]))
                elem_id += 1

    return {
        "nodes": nodes,
        "c3d8r": elems,
        "c3d6": [],
        "sym_x": sorted(set(sym_x)),
        "sym_y": sorted(set(sym_y)),
    }


def make_plate_coupon(nply=NPLY, nx=NX, dx=DX, t=T):
    """Generate 6-ply quarter-symmetry host coupon with cohesive interfaces."""
    nodes, elems = {}, {}
    ply_elems = {p: [] for p in range(nply)}
    nid, eid = 1, 1
    edge_nodes, sym_x, sym_y = set(), set(), set()
    grid = {}

    for p in range(nply):
        z_bot = -(nply - p) * t
        for k in range(2):
            z = z_bot + k * t
            for j in range(nx + 1):
                y = j * dx
                for i in range(nx + 1):
                    x = i * dx
                    grid[(p, i, j, k)] = nid
                    nodes[nid] = (x, y, z)
                    if i == 0:
                        sym_x.add(nid)
                    if j == 0:
                        sym_y.add(nid)
                    if i == nx or j == nx:
                        edge_nodes.add(nid)
                    nid += 1
        for j in range(nx):
            for i in range(nx):
                c = [
                    grid[(p, i, j, 0)], grid[(p, i+1, j, 0)],
                    grid[(p, i+1, j+1, 0)], grid[(p, i, j+1, 0)],
                    grid[(p, i, j, 1)], grid[(p, i+1, j, 1)],
                    grid[(p, i+1, j+1, 1)], grid[(p, i, j+1, 1)]
                ]
                elems[eid] = c
                ply_elems[p].append(eid)
                eid += 1

    return {
        "nodes": nodes,
        "elems": elems,
        "ply_elems": ply_elems,
        "edge_nodes": sorted(edge_nodes),
        "sym_x": sorted(sym_x),
        "sym_y": sorted(sym_y),
    }


def make_plain_elastic_plate(nx=NX, dx=DX, total_t=T_TOTAL):
    """Generate single plain elastic block plate (no plies, no cohesive)."""
    nodes, elems = {}, {}
    nid, eid = 1, 1
    nz = 6
    dz = total_t / nz
    edge_nodes, sym_x, sym_y = set(), set(), set()
    grid = {}

    for k in range(nz + 1):
        z = -total_t + k * dz
        for j in range(nx + 1):
            y = j * dx
            for i in range(nx + 1):
                x = i * dx
                grid[(i, j, k)] = nid
                nodes[nid] = (x, y, z)
                if i == 0:
                    sym_x.add(nid)
                if j == 0:
                    sym_y.add(nid)
                if i == nx or j == nx:
                    edge_nodes.add(nid)
                nid += 1

    top_elems = []
    for k in range(nz):
        for j in range(nx):
            for i in range(nx):
                c = [
                    grid[(i, j, k)], grid[(i+1, j, k)],
                    grid[(i+1, j+1, k)], grid[(i, j+1, k)],
                    grid[(i, j, k+1)], grid[(i+1, j, k+1)],
                    grid[(i+1, j+1, k+1)], grid[(i, j+1, k+1)]
                ]
                elems[eid] = c
                if k == nz - 1:
                    top_elems.append(eid)
                eid += 1

    return {
        "nodes": nodes,
        "elems": elems,
        "top_elems": top_elems,
        "edge_nodes": sorted(edge_nodes),
        "sym_x": sorted(sym_x),
        "sym_y": sorted(sym_y),
    }


def make_fibers(nply=NPLY, nx=NX, dx=DX, t=T, base_nid=100001, base_eid=100001, elem_type="T3D2"):
    """Generate embedded cross-ply fiber elements (0/90 alternating)."""
    fnodes, felems = {}, {}
    fnid, feid = base_nid, base_eid
    sym_x, sym_y, edge_nodes = set(), set(), set()

    for p in range(nply):
        zc = -(nply - p - 0.5) * t
        for r in range(nx):
            yc = (r + 0.5) * dx
            row = []
            for q in range(nx + 1):
                if p % 2 == 0:  # 0 deg: along x
                    x, y = q * dx, yc
                    if q == 0:
                        sym_x.add(fnid)
                    if q == nx:
                        edge_nodes.add(fnid)
                else:  # 90 deg: along y
                    x, y = yc, q * dx
                    if q == 0:
                        sym_y.add(fnid)
                    if q == nx:
                        edge_nodes.add(fnid)
                fnodes[fnid] = (x, y, zc)
                row.append(fnid)
                fnid += 1
            for a, b in zip(row[:-1], row[1:]):
                felems[feid] = (a, b)
                feid += 1

    return {
        "nodes": fnodes,
        "elems": felems,
        "sym_x": sorted(sym_x),
        "sym_y": sorted(sym_y),
        "edge_nodes": sorted(edge_nodes),
        "elem_type": elem_type,
    }


def build_deck(config, nominal_ball, coarse_ball):
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
    scale_penalty = config.get("scale_penalty", None)

    ball = nominal_ball if ball_type == "nominal" else coarse_ball
    mats = get_material_blocks(damage_on=damage_on)

    # Node ID offset for Ball to avoid collisions
    ball_nid_offset = 200000
    ball_eid_offset = 200000

    lines = [
        "*Heading",
        f"** T-049 Isolation Matrix: {name}",
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
    else:  # plain elastic block
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

    # --- SECTIONS & MATERIALS ---
    lines.extend([
        "*Section Controls, name=EMBMESH_DELETE_ALL, element deletion=YES",
        f"*Solid Section, elset=BALL_ELEMS, material=Steel, controls={'EMBMESH_DELETE_ALL' if damage_on else 'EMBMESH_HOST_KEEP'}",
        "*Section Controls, name=EMBMESH_HOST_KEEP, element deletion=NO, max degradation=0.99",
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
            "*Solid Section, elset=PLATE_ELEMS, material=ElasticSteel",
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

        if scale_penalty is not None:
            lines.extend([
                "*Contact Controls Assignment, type=SCALE PENALTY",
                f" , , {scale_penalty:g}",
            ])
    else:  # plain elastic plate
        lines.extend([
            "PLATE_SURF, BALL_SURF",
            "*Contact Property Assignment",
            " , , General",
        ])

    # Output requests
    lines.extend([
        "*Output, field, time interval=5e-07",
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
        "CSDMG, CSTRESS, CDISP, CPRESS",
        "*Output, history, time interval=1e-07",
        "*Energy Output",
        "ALLKE, ALLIE, ALLSE, ALLPD, ALLDMD, ALLFD, ALLVD, ALLAE, ALLWK, ETOTAL",
        "*End Step",
    ])

    return "\n".join(lines) + "\n"


# =====================================================================
# Isolation Matrix Configurations
# =====================================================================
MATRIX = [
    {
        "id": "01",
        "name": "t049_01_baseline_plate_dmg_on",
        "desc": "Baseline Ball (JC damage ON) vs Plain Elastic Plate (no fibers, no cohesive)",
        "ball_mesh": "nominal",
        "damage_on": True,
        "plate_type": "plain_elastic",
        "has_fibers": False,
        "fiber_contact": "none",
        "isolates": "Ball constitutive behavior & JC damage formulation under pure flat impact (tests negative d4 strain-rate term)",
    },
    {
        "id": "02",
        "name": "t049_02_baseline_plate_dmg_off",
        "desc": "Baseline Ball (JC damage OFF) vs Plain Elastic Plate (no fibers, no cohesive)",
        "ball_mesh": "nominal",
        "damage_on": False,
        "plate_type": "plain_elastic",
        "has_fibers": False,
        "fiber_contact": "none",
        "isolates": "Ball mesh stability and plastic mushrooming under pure flat impact without element deletion",
    },
    {
        "id": "03",
        "name": "t049_03_host_only_erode",
        "desc": "Ball (JC damage ON) vs 6-Ply Host Matrix Coupon (eroding surface, no fibers)",
        "ball_mesh": "nominal",
        "damage_on": True,
        "plate_type": "coupon",
        "has_fibers": False,
        "fiber_contact": "none",
        "isolates": "Host matrix interaction alone; confirms whether soft matrix erosion causes any ball damage",
    },
    {
        "id": "04",
        "name": "t049_04_host_embedded_no_contact",
        "desc": "Ball (JC damage ON) vs 6-Ply Coupon with Embedded Fibers, but fibers NOT in contact inclusions",
        "ball_mesh": "nominal",
        "damage_on": True,
        "plate_type": "coupon",
        "has_fibers": True,
        "fiber_elem": "T3D2",
        "fiber_contact": "none",
        "isolates": "Host kinematic embedding feedback without direct fiber-to-ball contact forces",
    },
    {
        "id": "05",
        "name": "t049_05_fiber_node_thick_0618",
        "desc": "Coupon recreation of vp5: Ball (JC dmg ON) vs Host + Fiber Node Contact (THICKNESS = 0.618 mm)",
        "ball_mesh": "nominal",
        "damage_on": True,
        "plate_type": "coupon",
        "has_fibers": True,
        "fiber_elem": "T3D2",
        "fiber_contact": "node",
        "fiber_thick": 0.000617973861320424,
        "isolates": "Direct coupon benchmark of full vp5 formulation (18.5k ball, 0.618 mm fiber node contact, JC deletion)",
    },
    {
        "id": "06",
        "name": "t049_06_fiber_node_thick_dmg_off",
        "desc": "Coupon recreation of vp6: Ball (JC dmg OFF) vs Host + Fiber Node Contact (THICKNESS = 0.618 mm)",
        "ball_mesh": "nominal",
        "damage_on": False,
        "plate_type": "coupon",
        "has_fibers": True,
        "fiber_elem": "T3D2",
        "fiber_contact": "node",
        "fiber_thick": 0.000617973861320424,
        "isolates": "Direct coupon benchmark of full vp6 formulation (reproduces severe PEEQ > 60 and element distortion)",
    },
    {
        "id": "07",
        "name": "t049_07_fiber_node_thin_0050",
        "desc": "Ball (JC dmg ON) vs Host + Thin Fiber Node Contact (THICKNESS = 0.050 mm = 50 um)",
        "ball_mesh": "nominal",
        "damage_on": True,
        "plate_type": "coupon",
        "has_fibers": True,
        "fiber_elem": "T3D2",
        "fiber_contact": "node",
        "fiber_thick": 0.00005,
        "isolates": "Fiber contact sphere thickness; tests whether reducing contact radius by 12x eliminates ball spiking",
    },
    {
        "id": "08",
        "name": "t049_08_ball_coarse_mesh",
        "desc": "Coarse Ball Mesh (2,000 hexes, char size ~0.78 mm) vs Nominal Coupon (0.618 mm fiber contact)",
        "ball_mesh": "coarse",
        "damage_on": True,
        "plate_type": "coupon",
        "has_fibers": True,
        "fiber_elem": "T3D2",
        "fiber_contact": "node",
        "fiber_thick": 0.000617973861320424,
        "isolates": "Ball element discretization; tests if element size larger than fiber contact thickness prevents inversion",
    },
    {
        "id": "09",
        "name": "t049_09_fiber_penalty_scale",
        "desc": "Ball (JC dmg ON) vs Host + Fiber Node Contact with SCALE PENALTY = 0.1",
        "ball_mesh": "nominal",
        "damage_on": True,
        "plate_type": "coupon",
        "has_fibers": True,
        "fiber_elem": "T3D2",
        "fiber_contact": "node",
        "fiber_thick": 0.000617973861320424,
        "scale_penalty": 0.1,
        "isolates": "Contact penalty stiffness; tests if attenuating penalty spikes prevents needle-point crushing",
    },
    {
        "id": "10",
        "name": "t049_10_fiber_beam_elem_surf",
        "desc": "Ball (JC dmg ON) vs Host + Continuous B31 Beam Fibers with Element-Based Surface",
        "ball_mesh": "nominal",
        "damage_on": True,
        "plate_type": "coupon",
        "has_fibers": True,
        "fiber_elem": "B31",
        "fiber_contact": "beam",
        "isolates": "Continuous element-based line contact vs discrete node-point penetration",
    },
]


def main():
    DECKS_DIR.mkdir(parents=True, exist_ok=True)
    print("=== T-049 Ball Isolation Test Matrix Generator ===")
    print(f"Loading nominal ball from {FULL_INP}...")
    nominal_ball = extract_nominal_ball(FULL_INP)
    print(f"Nominal ball loaded: {len(nominal_ball['nodes'])} nodes, "
          f"{len(nominal_ball['c3d8r'])} C3D8R, {len(nominal_ball['c3d6'])} C3D6")

    print("Generating coarse ball mesh (2,000 C3D8R elements)...")
    coarse_ball = make_coarse_ball()
    print(f"Coarse ball generated: {len(coarse_ball['nodes'])} nodes, {len(coarse_ball['c3d8r'])} C3D8R")

    print(f"\nGenerating {len(MATRIX)} test decks in {DECKS_DIR}:")
    for cfg in MATRIX:
        deck_text = build_deck(cfg, nominal_ball, coarse_ball)
        out_file = DECKS_DIR / f"{cfg['name']}.inp"
        out_file.write_text(deck_text, encoding="utf-8")
        file_size_kb = out_file.stat().st_size / 1024.0
        print(f"  [{cfg['id']}] Wrote {out_file.name:<38} ({file_size_kb:6.1f} KB) - {cfg['desc'][:50]}...")

    print("\nAll 10 isolation decks generated successfully!")


if __name__ == "__main__":
    main()
