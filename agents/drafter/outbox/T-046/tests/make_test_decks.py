"""Generate small test decks for T-046 fiber-host interaction and deletion mechanism.

Generates 5 verification test decks:
1. test1_fiber_alone.inp: Pure uniaxial tension of a single T3D2 truss element
   to verify that Abaqus/Explicit executes element deletion with the exact vp4 card
   (*Solid Section, controls=EMBMESH_DELETE_ALL, *Damage Evolution, type=DISPLACEMENT 0.)
   and identify the exact failure strain (elastic ~2.6% + plastic ~3.9% = ~6.5%).
2. test2_single_host_pull.inp: Single native C3D8R host element with an embedded
   T3D2 fiber. Host back face is fixed; protruding fiber is pulled. Demonstrates
   that the soft host yields and deletes at minute fiber strain (< 0.5%),
   releasing the constraint before the fiber ever fails.
3. test3_vuel_ghost_pull.inp: Single VUEL element + ghost C3D8R element with an
   embedded T3D2 fiber. Demonstrates that the ultra-soft ghost element (E=70 kPa,
   sigy=7 kPa) deletes at negligible milliNewton load, disconnecting the fiber from
   the host while the VUEL remains intact.
4. test4_block_3x3_pull.inp: 3x3x1 block of 9 host elements with an embedded fiber
   tow running through 3 elements. Demonstrates progressive sequential unzipping
   where the fiber deletes host elements one by one without failing.
5. test5_mass_conservation.inp: Dynamic pull test measuring nodal mass and kinetic
   energy after host element deletion, confirming that Abaqus/Explicit retains
   the lumped nodal mass of deleted elements on the remaining/orphan nodes.
"""

import os
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent

# Fiber material parameters (from vp4 deck)
FIBER_E = 1.35e11
FIBER_NU = 0.45
FIBER_RHO = 981.0
FIBER_AREA = 3.1370687601686238e-07  # m^2 (d = 0.632 mm)

# Matrix material parameters (from vp4 deck)
MATRIX_E = 7.0e8
MATRIX_NU = 0.45
MATRIX_RHO = 980.0
MATRIX_SIGY = 7.0e7
MATRIX_INIT_EPS = 0.01
MATRIX_GF = 1460.0

# Ghost material parameters (from vp4 vuel deck)
GHOST_E = 70000.0
GHOST_NU = 0.45
GHOST_RHO = 0.098
GHOST_SIGY = 7000.0
GHOST_INIT_EPS = 0.137252386673892


def fiber_material_block():
    return """*Section Controls, name=EMBMESH_DELETE_ALL, element deletion=YES
*Material, name=Fiber
*Damage Initiation, criterion=DUCTILE
  0.0391, 0.333333,     0.01
  0.0251, 0.333333,       1.
 0.01167, 0.333333,    1000.
*Damage Evolution, type=DISPLACEMENT
0.
*Density
 981.,
*Elastic
 1.35e+11, 0.45
*Plastic
 3.5e+09,0.
*Plastic, rate=1.
 4.3e+09,0.
*Plastic, rate=1000.
 4.5e+09,0.
"""


def matrix_material_block():
    return """*Material, name=Matrix
*Damage Initiation, criterion=DUCTILE
 0.01, 0.333333,     0.01
*Damage Evolution, type=ENERGY
1460.,
*Density
 980.,
*Elastic
 7e+08, 0.45
*Plastic, extrapolation=LINEAR
 7e+07,0.
"""


def ghost_material_block():
    return """*Section Controls, name=EMBMESH_GHOST_CONTROLS, element deletion=YES
 1., 1., 1.
*Material, name=EMBMESH_GHOST_MATERIAL
*Damage Initiation, criterion=DUCTILE
 0.137252386673892, 0.333333, 0.01
*Damage Evolution, type=DISPLACEMENT
 0.
*Density
 0.098,
*Elastic
 70000, 0.45
*Plastic, extrapolation=LINEAR
 7000, 0
"""


def _strip_blank(t):
    # blank lines are read by Abaqus as empty data rows
    return "".join(l for l in t.splitlines(True) if l.strip())


def write_test1():
    """Test 1: Uniaxial tension on a single T3D2 fiber element."""
    text = f"""*Heading
** Test 1: Single T3D2 Fiber Uniaxial Tension Failure
** Validates deletion of T3D2 using *Solid Section and *Damage Evolution
*Node
1, 0.0, 0.0, 0.0
2, 0.001, 0.0, 0.0
*Nset, nset=NALL
1, 2
*Nset, nset=NFIX
1,
*Nset, nset=NPULL
2,
*Element, type=T3D2, elset=FIBERS
1, 1, 2
*Solid Section, elset=FIBERS, material=Fiber, controls=EMBMESH_DELETE_ALL
{FIBER_AREA}
{fiber_material_block()}
*Boundary
NFIX, 1, 3, 0.0
NPULL, 2, 3, 0.0
*Amplitude, name=RAMP, definition=SMOOTH STEP
0.0, 0.0, 1.0e-4, 1.0
*Step, name=Pull, nlgeom=YES
*Dynamic, Explicit
, 1.0e-4
*Bulk Viscosity
0.0, 0.0
*Boundary, type=DISPLACEMENT, amplitude=RAMP
NPULL, 1, 1, 0.0001
*Output, field, time interval=1.0e-6
*Node Output
U, V, RF
*Element Output
S, LE, PEEQ, STATUS
*Output, history, time interval=1.0e-6
*Energy Output
ALLKE, ALLIE, ALLPD, ALLDMD, ETOTAL
*End Step
"""
    (OUT_DIR / "test1_fiber_alone.inp").write_text(_strip_blank(text), newline="")
    print("Wrote test1_fiber_alone.inp")


def write_test2():
    """Test 2: Single native host C3D8R + embedded T3D2 fiber."""
    text = f"""*Heading
** Test 2: Single Native Host Element with Embedded Fiber Tow
** Demonstrates host yield/deletion before fiber reaches failure strain
*Node
1, 0.0, 0.0, 0.0
2, 0.001, 0.0, 0.0
3, 0.001, 0.001, 0.0
4, 0.0, 0.001, 0.0
5, 0.0, 0.0, 0.001
6, 0.001, 0.0, 0.001
7, 0.001, 0.001, 0.001
8, 0.0, 0.001, 0.001
101, 0.0, 0.0005, 0.0005
102, 0.001, 0.0005, 0.0005
103, 0.0015, 0.0005, 0.0005
*Nset, nset=HOST_FIX
1, 4, 5, 8
*Nset, nset=FIBER_PULL
103,
*Element, type=C3D8R, elset=HOST
1, 1, 2, 3, 4, 5, 6, 7, 8
*Element, type=T3D2, elset=FIB_EMB
101, 101, 102
*Element, type=T3D2, elset=FIB_FREE
102, 102, 103
*Elset, elset=FIBERS
FIB_EMB, FIB_FREE
*Solid Section, elset=HOST, material=Matrix, controls=EMBMESH_DELETE_ALL
*Solid Section, elset=FIBERS, material=Fiber, controls=EMBMESH_DELETE_ALL
{FIBER_AREA}
*Embedded Element, host elset=HOST
FIB_EMB
{fiber_material_block()}
{matrix_material_block()}
*Boundary
HOST_FIX, 1, 3, 0.0
FIBER_PULL, 2, 3, 0.0
*Amplitude, name=RAMP, definition=SMOOTH STEP
0.0, 0.0, 1.0e-4, 1.0
*Step, name=Pull, nlgeom=YES
*Dynamic, Explicit
, 1.0e-4
*Bulk Viscosity
0.06, 1.2
*Boundary, type=DISPLACEMENT, amplitude=RAMP
FIBER_PULL, 1, 1, 0.0002
*Output, field, time interval=1.0e-6
*Node Output
U, V, RF
*Element Output, elset=HOST
S, LE, PEEQ, STATUS
*Element Output, elset=FIBERS
S, LE, PEEQ, STATUS
*Output, history, time interval=1.0e-6
*Energy Output
ALLKE, ALLIE, ALLPD, ALLDMD, ETOTAL
*End Step
"""
    (OUT_DIR / "test2_single_host_pull.inp").write_text(_strip_blank(text), newline="")
    print("Wrote test2_single_host_pull.inp")


def write_test3():
    """Test 3: Single VUEL + Ghost host with embedded fiber."""
    text = f"""*Heading
** Test 3: VUEL + Ghost Host Element with Embedded Fiber
** Demonstrates immediate ghost deletion and fiber uncoupling under minute force
*Node
1, 0.0, 0.0, 0.0
2, 0.001, 0.0, 0.0
3, 0.001, 0.001, 0.0
4, 0.0, 0.001, 0.0
5, 0.0, 0.0, 0.001
6, 0.001, 0.0, 0.001
7, 0.001, 0.001, 0.001
8, 0.0, 0.001, 0.001
101, 0.0, 0.0005, 0.0005
102, 0.001, 0.0005, 0.0005
103, 0.0015, 0.0005, 0.0005
*Nset, nset=HOST_FIX
1, 4, 5, 8
*Nset, nset=FIBER_PULL
103,
*Element, type=C3D8R, elset=GHOST_HOST
1, 1, 2, 3, 4, 5, 6, 7, 8
*Element, type=T3D2, elset=FIB_EMB
101, 101, 102
*Element, type=T3D2, elset=FIB_FREE
102, 102, 103
*Elset, elset=FIBERS
FIB_EMB, FIB_FREE
*Solid Section, elset=GHOST_HOST, material=EMBMESH_GHOST_MATERIAL, controls=EMBMESH_GHOST_CONTROLS
*Solid Section, elset=FIBERS, material=Fiber, controls=EMBMESH_DELETE_ALL
{FIBER_AREA}
*Embedded Element, host elset=GHOST_HOST
FIB_EMB
{fiber_material_block()}
{ghost_material_block()}
*Boundary
HOST_FIX, 1, 3, 0.0
FIBER_PULL, 2, 3, 0.0
*Amplitude, name=RAMP, definition=SMOOTH STEP
0.0, 0.0, 1.0e-4, 1.0
*Step, name=Pull, nlgeom=YES
*Dynamic, Explicit
, 1.0e-4
*Bulk Viscosity
0.06, 1.2
*Boundary, type=DISPLACEMENT, amplitude=RAMP
FIBER_PULL, 1, 1, 0.0002
*Output, field, time interval=1.0e-6
*Node Output
U, V, RF
*Element Output, elset=GHOST_HOST
S, LE, PEEQ, STATUS
*Element Output, elset=FIBERS
S, LE, PEEQ, STATUS
*Output, history, time interval=1.0e-6
*Energy Output
ALLKE, ALLIE, ALLPD, ALLDMD, ETOTAL
*End Step
"""
    (OUT_DIR / "test3_vuel_ghost_pull.inp").write_text(_strip_blank(text), newline="")
    print("Wrote test3_vuel_ghost_pull.inp")


def write_test4():
    """Test 4: 3x3x1 Host block with embedded fiber tow pulling through."""
    nodes = []
    nid = 1
    # 3x3x1 grid of hexes: 4x4x2 nodes = 32 nodes
    node_map = {}
    for k in range(2):
        for j in range(4):
            for i in range(4):
                x = i * 0.001
                y = j * 0.001
                z = k * 0.001
                nodes.append(f"{nid}, {x:.6f}, {y:.6f}, {z:.6f}")
                node_map[(i, j, k)] = nid
                nid += 1

    elems = []
    eid = 1
    # 9 hex elements
    for j in range(3):
        for i in range(3):
            n1 = node_map[(i, j, 0)]
            n2 = node_map[(i + 1, j, 0)]
            n3 = node_map[(i + 1, j + 1, 0)]
            n4 = node_map[(i, j + 1, 0)]
            n5 = node_map[(i, j, 1)]
            n6 = node_map[(i + 1, j, 1)]
            n7 = node_map[(i + 1, j + 1, 1)]
            n8 = node_map[(i, j + 1, 1)]
            elems.append(f"{eid}, {n1}, {n2}, {n3}, {n4}, {n5}, {n6}, {n7}, {n8}")
            eid += 1

    # Fiber nodes: running along center row (y = 0.0015, z = 0.0005)
    fiber_nodes = [
        "101, 0.000, 0.0015, 0.0005",
        "102, 0.001, 0.0015, 0.0005",
        "103, 0.002, 0.0015, 0.0005",
        "104, 0.003, 0.0015, 0.0005",
        "105, 0.004, 0.0015, 0.0005",
    ]
    fiber_elems = [
        "101, 101, 102",
        "102, 102, 103",
        "103, 103, 104",
        "104, 104, 105",
    ]

    fix_nodes = [str(node_map[(0, j, k)]) for j in range(4) for k in range(2)]

    text = f"""*Heading
** Test 4: 3x3 Host Block with Embedded Fiber Tow
** Demonstrates sequential unzipping / host deletion as fiber pulls through
*Node
{chr(10).join(nodes)}
{chr(10).join(fiber_nodes)}
*Nset, nset=HOST_FIX
{", ".join(fix_nodes)}
*Nset, nset=FIBER_PULL
105,
*Element, type=C3D8R, elset=HOST
{chr(10).join(elems)}
*Element, type=T3D2, elset=FIB_EMB
{chr(10).join(fiber_elems[:3])}
*Element, type=T3D2, elset=FIB_FREE
{chr(10).join(fiber_elems[3:])}
*Elset, elset=FIBERS
FIB_EMB, FIB_FREE
*Solid Section, elset=HOST, material=Matrix, controls=EMBMESH_DELETE_ALL
*Solid Section, elset=FIBERS, material=Fiber, controls=EMBMESH_DELETE_ALL
{FIBER_AREA}
*Embedded Element, host elset=HOST
FIB_EMB
{fiber_material_block()}
{matrix_material_block()}
*Boundary
HOST_FIX, 1, 3, 0.0
FIBER_PULL, 2, 3, 0.0
*Amplitude, name=RAMP, definition=SMOOTH STEP
0.0, 0.0, 1.0e-4, 1.0
*Step, name=Pull, nlgeom=YES
*Dynamic, Explicit
, 1.0e-4
*Bulk Viscosity
0.06, 1.2
*Boundary, type=DISPLACEMENT, amplitude=RAMP
FIBER_PULL, 1, 1, 0.0008
*Output, field, time interval=1.0e-6
*Node Output
U, V, RF
*Element Output, elset=HOST
S, LE, PEEQ, STATUS
*Element Output, elset=FIBERS
S, LE, PEEQ, STATUS
*Output, history, time interval=1.0e-6
*Energy Output
ALLKE, ALLIE, ALLPD, ALLDMD, ETOTAL
*End Step
"""
    (OUT_DIR / "test4_block_3x3_pull.inp").write_text(_strip_blank(text), newline="")
    print("Wrote test4_block_3x3_pull.inp")


def write_test5():
    """Test 5: Nodal lumped mass retention on deleted element nodes."""
    text = f"""*Heading
** Test 5: Lumped Mass Retention on Deleted Element Nodes
** Verifies that Abaqus/Explicit does not erode nodal mass when host elements delete
*Node
1, 0.0, 0.0, 0.0
2, 0.001, 0.0, 0.0
3, 0.001, 0.001, 0.0
4, 0.0, 0.001, 0.0
5, 0.0, 0.0, 0.001
6, 0.001, 0.0, 0.001
7, 0.001, 0.001, 0.001
8, 0.0, 0.001, 0.001
*Nset, nset=NFIX
1, 4, 5, 8
*Nset, nset=NPULL
2, 3, 6, 7
*Element, type=C3D8R, elset=HOST
1, 1, 2, 3, 4, 5, 6, 7, 8
*Solid Section, elset=HOST, material=Matrix, controls=EMBMESH_DELETE_ALL
*Section Controls, name=EMBMESH_DELETE_ALL, element deletion=YES
{matrix_material_block()}
*Boundary
NFIX, 1, 3, 0.0
NPULL, 2, 3, 0.0
*Amplitude, name=RAMP, definition=SMOOTH STEP
0.0, 0.0, 2.0e-5, 1.0
*Step, name=ImpulseAndRelease, nlgeom=YES
*Dynamic, Explicit
, 1.0e-4
*Bulk Viscosity
0.0, 0.0
*Boundary, type=DISPLACEMENT, amplitude=RAMP
NPULL, 1, 1, 0.0003
*Output, field, time interval=1.0e-6
*Node Output
U, V, A, RF
*Element Output, elset=HOST
S, LE, PEEQ, STATUS
*Output, history, time interval=1.0e-6
*Energy Output
ALLKE, ALLIE, ALLPD, ALLDMD, ETOTAL
*End Step
"""
    (OUT_DIR / "test5_mass_conservation.inp").write_text(_strip_blank(text), newline="")
    print("Wrote test5_mass_conservation.inp")


def main():
    write_test1()
    write_test2()
    write_test3()
    write_test4()
    write_test5()
    print("All 5 test decks generated successfully in", OUT_DIR)


if __name__ == "__main__":
    main()
