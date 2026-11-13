r"""Generator for the fiber-host contact test coupons (T-056).

Generates three variants of a small 2-ply coupon with 3 hex layers per ply,
VUEL matrix + C3D8R ghost hosts (nv3 properties), mid-ply T3D2 fibers,
and axial fiber pull to trigger host failure and element deletion:
  (i)   coupon_fiberhost_nocontact.inp : No fiber-host contact
  (ii)  coupon_fiberhost_native.inp    : Native penalty contact on all fiber-host pairs (shows initial-overlap energy blowup)
  (iii) coupon_fiberhost_baseline.inp  : Baseline VUINTERACTION scheme (overclosure zeroed at t=0, ratcheting)
  Also writes coupon_fiberhost.inp as identical to variant (iii).

Usage:
  python make_coupon_fiberhost.py
"""
from pathlib import Path

# Geometry parameters (SI: m, kg, s, Pa)
NX, NY, NZ = 4, 4, 3
DX = 0.000632   # 0.632 mm in-plane spacing
DY = 0.000632
T_PLY = 0.00127 # 1.27 mm ply thickness
DZ = T_PLY / NZ # 0.42333 mm per hex layer
FIBER_AREA = 3.1370687601686238e-07 # m^2 -> diameter 0.632 mm
EQUIV_D = 0.000632
STEP_TIME = 1.0e-05 # 10 us
PULL_VELOCITY = 50.0 # 50 m/s pull on fiber end to induce shear failure


def make_plate_part():
    lines = ["*Part, name=Plate", "*Node"]
    # Nodes: (NX+1)*(NY+1)*(NZ+1)
    nid = 1
    node_map = {}
    for k in range(NZ + 1):
        for j in range(NY + 1):
            for i in range(NX + 1):
                node_map[(i, j, k)] = nid
                lines.append(f" {nid}, {i*DX:.6e}, {j*DY:.6e}, {k*DZ:.6e}")
                nid += 1

    # Elements: NX*NY*NZ
    vuel_elems = []
    ghost_elems = []
    top_faces = []
    bot_faces = []
    eid = 1
    for k in range(NZ):
        for j in range(NY):
            for i in range(NX):
                c = [
                    node_map[(i, j, k)],
                    node_map[(i + 1, j, k)],
                    node_map[(i + 1, j + 1, k)],
                    node_map[(i, j + 1, k)],
                    node_map[(i, j, k + 1)],
                    node_map[(i + 1, j, k + 1)],
                    node_map[(i + 1, j + 1, k + 1)],
                    node_map[(i, j + 1, k + 1)],
                ]
                conn = ", ".join(str(n) for n in c)
                vuel_elems.append(f" {eid}, {conn}")
                ghost_elems.append(f" {eid + 1000}, {conn}")
                if k == 0:
                    bot_faces.append(f"{eid + 1000}, S1")  # S1 is bottom face (z min)
                if k == NZ - 1:
                    top_faces.append(f"{eid + 1000}, S2")  # S2 is top face (z max)
                eid += 1

    lines += [
        "*User Element, type=VU1, nodes=8, coordinates=3, properties=39, variables=159",
        " 1, 2, 3",
        "*Element, type=VU1, elset=EMBMESH_VUEL_HOST",
        *vuel_elems,
        "*UEL Property, elset=EMBMESH_VUEL_HOST",
        " 700000000, 0.45, 980, 0, 0.06, 1.2, 10, 70000000",
        " 0, 1, 0, 0, 0, 1, 0, 1460",
        " 0, 1, 1, 1, 70000000, 0, 0, 0",
        " 0, 0, 0, 0, 0, 1, 0.1, 0",
        " 0, 0, 0, 0, 0, 0, 0",
        "*Element, type=C3D8R, elset=EMBMESH_GHOST_HOST",
        *ghost_elems,
        "*Solid Section, elset=EMBMESH_GHOST_HOST, material=EMBMESH_GHOST_MATERIAL",
        ",",
        "*Surface, type=ELEMENT, name=PLY_TOP",
        *top_faces,
        "*Surface, type=ELEMENT, name=PLY_BOTTOM",
        *bot_faces,
        "*End Part",
    ]
    return lines, node_map


def make_fibers_x_part():
    # Fibers along X at mid-ply (z = 0.635 mm)
    z_mid = T_PLY / 2.0
    lines = ["*Part, name=Fibers_0", "*Node"]
    nid = 1
    # 2 fiber rows at y = 1*DY and y = 3*DY
    elems = []
    eid = 1
    all_nids = []
    for r, j_idx in enumerate([1, 3]):
        y = j_idx * DY
        row_nids = []
        for i in range(NX + 1):
            lines.append(f" {nid}, {i*DX:.6e}, {y:.6e}, {z_mid:.6e}")
            row_nids.append(nid)
            all_nids.append(nid)
            nid += 1
        for a, b in zip(row_nids[:-1], row_nids[1:]):
            elems.append(f" {eid}, {a}, {b}")
            eid += 1
    lines += [
        "*Element, type=T3D2, elset=FIBERS",
        *elems,
        "*Solid Section, elset=FIBERS, material=Fiber",
        f" {FIBER_AREA:.16e}",
        "*Nset, nset=FIBER_NODES",
        ", ".join(str(n) for n in all_nids),
        "*Nset, nset=PULL_END",
        f" {row_nids[-1]}", # Node at x = NX*DX of the second fiber
        "*End Part",
    ]
    return lines


def make_fibers_y_part():
    # Fibers along Y at mid-ply (z = 0.635 mm)
    z_mid = T_PLY / 2.0
    lines = ["*Part, name=Fibers_90", "*Node"]
    nid = 1
    # 2 fiber rows at x = 1*DX and x = 3*DX
    elems = []
    eid = 1
    all_nids = []
    for r, i_idx in enumerate([1, 3]):
        x = i_idx * DX
        row_nids = []
        for j in range(NY + 1):
            lines.append(f" {nid}, {x:.6e}, {j*DY:.6e}, {z_mid:.6e}")
            row_nids.append(nid)
            all_nids.append(nid)
            nid += 1
        for a, b in zip(row_nids[:-1], row_nids[1:]):
            elems.append(f" {eid}, {a}, {b}")
            eid += 1
    lines += [
        "*Element, type=T3D2, elset=FIBERS",
        *elems,
        "*Solid Section, elset=FIBERS, material=Fiber",
        f" {FIBER_AREA:.16e}",
        "*Nset, nset=FIBER_NODES",
        ", ".join(str(n) for n in all_nids),
        "*End Part",
    ]
    return lines


def generate_deck(variant: str):
    plate_lines, node_map = make_plate_part()
    fibers_0_lines = make_fibers_x_part()
    fibers_90_lines = make_fibers_y_part()

    lines = [
        "*Heading",
        f"** fiber-host coupon test - variant {variant}",
        "** SI units: m, kg, s, Pa, N, J",
        *plate_lines,
        *fibers_0_lines,
        *fibers_90_lines,
        "*Assembly, name=Assembly",
        "*Instance, name=Ply-1, part=Plate",
        " 0., 0., 0.",
        "*End Instance",
        "*Instance, name=Ply-2, part=Plate",
        f" 0., 0., {T_PLY:.6e}",
        "*End Instance",
        "*Instance, name=Fibers-Ply-1, part=Fibers_0",
        " 0., 0., 0.",
        "*End Instance",
        "*Instance, name=Fibers-Ply-2, part=Fibers_90",
        f" 0., 0., {T_PLY:.6e}",
        "*End Instance",
        "** embedded element constraints: fibers embedded in own-ply ghost hosts",
        "*Embedded Element, host elset=Ply-1.EMBMESH_GHOST_HOST",
        "Fibers-Ply-1.FIBERS",
        "*Embedded Element, host elset=Ply-2.EMBMESH_GHOST_HOST",
        "Fibers-Ply-2.FIBERS",
        "** cohesive interface between plies",
        "** eroding element surfaces for ghost hosts",
        "*Surface, type=ELEMENT, name=EMBMESH_HOST_PLY_1",
        "Ply-1.EMBMESH_GHOST_HOST,",
        "Ply-1.EMBMESH_GHOST_HOST, INTERIOR",
        "*Surface, type=ELEMENT, name=EMBMESH_HOST_PLY_2",
        "Ply-2.EMBMESH_GHOST_HOST,",
        "Ply-2.EMBMESH_GHOST_HOST, INTERIOR",
        "** node-based fiber contact surfaces",
        "*Surface, type=NODE, name=EMBMESH_FIBER_NODES_PLY_1",
        "Fibers-Ply-1.FIBER_NODES,",
        "*Surface, type=NODE, name=EMBMESH_FIBER_NODES_PLY_2",
        "Fibers-Ply-2.FIBER_NODES,",
        "** diagnostic sets",
        "*Elset, elset=ALL_GHOSTS",
        "Ply-1.EMBMESH_GHOST_HOST, Ply-2.EMBMESH_GHOST_HOST",
        "*Elset, elset=ALL_VUELS",
        "Ply-1.EMBMESH_VUEL_HOST, Ply-2.EMBMESH_VUEL_HOST",
        "** boundary sets",
        "*Nset, nset=BOTTOM_FIXED, instance=Ply-1",
    ]

    # Bottom nodes of Ply 1 (k=0)
    bot_nids = [node_map[(i, j, 0)] for j in range(NY + 1) for i in range(NX + 1)]
    lines.append(", ".join(str(n) for n in bot_nids))
    lines += [
        "*Nset, nset=PULLED_FIBER_NODE",
        "Fibers-Ply-1.PULL_END",
        "*End Assembly",
        "** initial conditions: SVAR 1..159 with SVAR107 = fiber volume fraction",
        "*Initial Conditions, type=SOLUTION",
    ]

    # Solution-dependent initial conditions for VU1 elements
    svar_row = ", ".join(["0"] * 8)
    for p in [1, 2]:
        for e in range(1, NX * NY * NZ + 1):
            lines.append(f"Ply-{p}.{e}, {svar_row}")
            for r in range(12):  # rows 2-13
                lines.append(svar_row)
            # row 14 has SVAR 105..112 (SVAR107 is index 3 in 0-based row)
            lines.append("0, 0, 0.3804479, 0, 0, 0, 0, 0")
            for r in range(5):   # rows 15-19
                lines.append(svar_row)
            lines.append("0, 0, 0, 0, 0, 0, 0")  # row 20 (7 entries to make 159)

    # Materials
    lines += [
        "*Material, name=EMBMESH_GHOST_MATERIAL",
        "*Damage Initiation, criterion=DUCTILE",
        " 0.1612767, 0.333333, 0.01",
        "*Damage Evolution, type=DISPLACEMENT",
        " 0.",
        "*Density",
        " 0.098",
        "*Elastic",
        " 70000., 0.45",
        "*Plastic",
        " 7000., 0.",
        "*Material, name=Fiber",
        "*Damage Initiation, criterion=DUCTILE",
        " 0.0391, 0.333333, 0.01",
        " 0.0251, 0.333333, 1.",
        " 0.01167, 0.333333, 1000.",
        "*Damage Evolution, type=ENERGY",
        " 1.,",
        "*Density",
        " 981.,",
        "*Elastic",
        " 1.35e+11, 0.45",
        "*Plastic",
        " 1.35e+09, 0.",
        "*Material, name=Matrix",
        "*Damage Initiation, criterion=DUCTILE",
        " 0.1, 0.333333, 0.01",
        "*Damage Evolution, type=ENERGY",
        " 1460.,",
        "*Density",
        " 980.,",
        "*Elastic",
        " 7.0e+08, 0.45",
        "*Plastic",
        " 7.0e+07, 0.",
        "** cohesive interaction between plies",
        "*Surface Interaction, name=Cohesion",
        "*Cohesive Behavior",
        " 6.0e+10, 3.6e+10, 3.6e+10",
        "*Damage Initiation, criterion=MAXS",
        " 1.2e+06, 2.6e+06, 2.6e+06",
        "*Damage Evolution, type=ENERGY, mixed mode behavior=POWER LAW, power=1",
        " 544, 1088, 1088",
        "*Surface Interaction, name=General",
        "*Friction",
        " 0.01,",
    ]

    if variant == "baseline":
        lines += [
            "** user interaction for own-ply fiber-host contact with baseline overclosure",
            "*Surface Interaction, name=FiberHostBaseline, USER=INTERACTION, PROPERTIES=2, DEPVAR=2, TRACKING THICKNESS=0.0005",
            "",
            " 2.0e+11, 0.01",
        ]

    lines += [
        "*Boundary",
        "BOTTOM_FIXED, 1, 3",
        "*Step, name=Step-1",
        "*Dynamic, Explicit",
        f", {STEP_TIME:.6e}",
        "** axial fiber pull velocity to shear embedding matrix host",
        "*Boundary, type=VELOCITY",
        f"PULLED_FIBER_NODE, 1, 1, {PULL_VELOCITY:g}",
        "** general contact setup",
        "*Contact, op=NEW",
    ]

    if variant == "nocontact":
        lines += [
            "*Contact Inclusions",
            "Ply-1.PLY_TOP , Ply-2.PLY_BOTTOM",
            "*Contact Property Assignment",
            "Ply-1.PLY_TOP , Ply-2.PLY_BOTTOM , Cohesion",
            "*Contact Controls Assignment, nodal erosion=YES",
        ]
    elif variant == "native":
        lines += [
            "*Contact Inclusions",
            "Ply-1.PLY_TOP , Ply-2.PLY_BOTTOM",
            "EMBMESH_FIBER_NODES_PLY_1 , EMBMESH_HOST_PLY_1",
            "EMBMESH_FIBER_NODES_PLY_1 , EMBMESH_HOST_PLY_2",
            "EMBMESH_FIBER_NODES_PLY_2 , EMBMESH_HOST_PLY_1",
            "EMBMESH_FIBER_NODES_PLY_2 , EMBMESH_HOST_PLY_2",
            "*Contact Property Assignment",
            " ,  , General",
            "Ply-1.PLY_TOP , Ply-2.PLY_BOTTOM , Cohesion",
            "*Contact Controls Assignment, nodal erosion=YES",
            "*Surface Property Assignment, property=THICKNESS",
            f"EMBMESH_FIBER_NODES_PLY_1, {EQUIV_D:.12g}",
            f"EMBMESH_FIBER_NODES_PLY_2, {EQUIV_D:.12g}",
        ]
    elif variant == "baseline":
        lines += [
            "*Contact Inclusions",
            "Ply-1.PLY_TOP , Ply-2.PLY_BOTTOM",
            "EMBMESH_FIBER_NODES_PLY_1 , EMBMESH_HOST_PLY_1",
            "EMBMESH_FIBER_NODES_PLY_1 , EMBMESH_HOST_PLY_2",
            "EMBMESH_FIBER_NODES_PLY_2 , EMBMESH_HOST_PLY_1",
            "EMBMESH_FIBER_NODES_PLY_2 , EMBMESH_HOST_PLY_2",
            "*Contact Property Assignment",
            " ,  , General",
            "Ply-1.PLY_TOP , Ply-2.PLY_BOTTOM , Cohesion",
            "EMBMESH_FIBER_NODES_PLY_1 , EMBMESH_HOST_PLY_1 , FiberHostBaseline",
            "EMBMESH_FIBER_NODES_PLY_2 , EMBMESH_HOST_PLY_2 , FiberHostBaseline",
            "*Contact Controls Assignment, nodal erosion=YES",
            "*Surface Property Assignment, property=THICKNESS",
            f"EMBMESH_FIBER_NODES_PLY_1, {EQUIV_D:.12g}",
            f"EMBMESH_FIBER_NODES_PLY_2, {EQUIV_D:.12g}",
        ]

    lines += [
        "*Restart, write, number interval=1, time marks=NO",
        "** history output: whole model energy balance and host deletion status",
        "*Output, history, time interval=5e-08",
        "*Energy Output",
        "ALLIE, ALLKE, ETOTAL, ALLPD, ALLFD, ALLVD",
        "*Element Output, elset=ALL_GHOSTS",
        "STATUS",
        "** field output for visualization and diagnostics",
        "*Output, field, number interval=20",
        "*Node Output",
        "U, V",
        "*Element Output, elset=ALL_GHOSTS",
        "STATUS, S, PEEQ, SDEG",
        "*Element Output, elset=ALL_VUELS",
        "SDV49, SDV106, SDV107",
        "*Contact Output",
        "CSDMG, CSMAXSCRT, CSTRESS, CDISP",
        "*End Step",
    ]
    return "\n".join(lines) + "\n"


def main():
    here = Path(__file__).resolve().parent
    variants = {
        "nocontact": here / "coupon_fiberhost_nocontact.inp",
        "native": here / "coupon_fiberhost_native.inp",
        "baseline": here / "coupon_fiberhost_baseline.inp",
    }
    for var, path in variants.items():
        content = generate_deck(var)
        path.write_text(content, encoding="utf-8")
        print(f"Wrote {path.name} ({len(content.splitlines())} lines)")

    # Also write coupon_fiberhost.inp identical to baseline
    base_file = here / "coupon_fiberhost.inp"
    base_file.write_text(variants["baseline"].read_text(encoding="utf-8"), encoding="utf-8")
    print(f"Wrote {base_file.name} (identical to coupon_fiberhost_baseline.inp)")


if __name__ == "__main__":
    main()
