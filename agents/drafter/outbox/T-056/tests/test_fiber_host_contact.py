import re
from pathlib import Path
import pytest
import numpy as np

from embmesh.parser import parse_deck
from embmesh.plywise import write_plywise_deck


def make_test_deck():
    """Generate a clean minimal Abaqus deck with Plate and Ball."""
    return '''*Part, name=Plate
*Node
1, 0.0, 0.0, 0.0
2, 0.012, 0.0, 0.0
3, 0.012, 0.018, 0.0
4, 0.0, 0.018, 0.0
5, 0.0, 0.0, 0.00254
6, 0.012, 0.0, 0.00254
7, 0.012, 0.018, 0.00254
8, 0.0, 0.018, 0.00254
*Element, type=C3D8R
1, 1, 2, 3, 4, 5, 6, 7, 8
*Elset, elset=Plate
1
*Solid Section, elset=Plate, material=Matrix
,
*End Part
*Part, name=Ball
*Node
1, 0.006, 0.009, 0.01
*Element, type=MASS, elset=Ball
1, 1
*End Part
*Assembly, name=Assembly
*Instance, name=Plate-1, part=Plate
0, 0, 0
*End Instance
*Instance, name=Ball-1, part=Ball
0, 0, 0
*End Instance
*End Assembly
*Material, name=Matrix
*Density
1000
*Elastic
2e9, 0.3
*Plastic
2e6, 0
3e6, 0.1
*Damage Initiation, criterion=DUCTILE
0.25, 0, 0
*Damage Evolution, type=DISPLACEMENT
0.001
*Material, name=Fiber
*Density
1780.0
*Elastic
2.5e11, 0.2
*Surface Interaction, name=General
*Friction
0.01
*Surface Behavior, pressure-overclosure=HARD
*Surface Interaction, name=Cohesion
*Cohesive Behavior
6e10, 3.6e10, 3.6e10
*Step, name=Step-1, nlgeom=YES
*Dynamic, Explicit
, 1.0e-6
*End Step
'''


def test_fiber_host_contact_default_off(tmp_path):
    """When --fiber-host-contact is 'none' (default), output is byte-identical."""
    src = tmp_path / "src.inp"
    src.write_text(make_test_deck())
    out1 = tmp_path / "out_default.inp"
    out2 = tmp_path / "out_none.inp"

    m1 = write_plywise_deck(
        src, out1, plies=2,
        layup=[0, 90], fiber_diameter=0.000632,
        through_thickness=3, host_mode="vuel-ghost",
        plate_surface="elements"
    )
    m2 = write_plywise_deck(
        src, out2, plies=2,
        layup=[0, 90], fiber_diameter=0.000632,
        through_thickness=3, host_mode="vuel-ghost",
        plate_surface="elements", fiber_host_contact="none"
    )

    assert m1.get("fiber_host_contact") is None
    assert m2.get("fiber_host_contact") is None
    assert out1.read_text() == out2.read_text()
    assert "FiberHostBaseline" not in out1.read_text()
    assert "EMBMESH_HOST_PLY_" not in out1.read_text()


def test_fiber_host_contact_baseline_generation(tmp_path):
    """When --fiber-host-contact is 'baseline', verify surfaces, inclusions, properties, and clearances."""
    src = tmp_path / "src.inp"
    src.write_text(make_test_deck())
    out = tmp_path / "out_baseline.inp"

    meta = write_plywise_deck(
        src, out, plies=2,
        layup=[0, 90], fiber_diameter=0.000632,
        through_thickness=3, host_mode="vuel-ghost",
        plate_surface="elements", fiber_host_contact="baseline"
    )

    fh = meta.get("fiber_host_contact")
    assert fh is not None, "fiber_host_contact metadata must be present"
    assert pytest.approx(fh["chosen_thickness"], rel=1e-4) == 0.000632
    assert fh["inclusion_lines_count"] == 4  # 2 plies: 2x2 = 4 inclusion lines
    assert fh["min_clearance_own_ply"] < 0.0  # Overclosed
    assert pytest.approx(fh["min_clearance_own_ply"], abs=1e-5) == -0.00010433
    assert fh["min_clearance_adjacent_ply"] > 0.0  # Clear
    assert pytest.approx(fh["min_clearance_adjacent_ply"], abs=1e-5) == 0.000319

    content = out.read_text()

    # 1. Surface definitions in assembly
    for k in (1, 2):
        assert f"*Surface, type=ELEMENT, name=EMBMESH_HOST_PLY_{k}" in content
        assert f"Ply-{k}.EMBMESH_GHOST_HOST," in content
        assert f"Ply-{k}.EMBMESH_GHOST_HOST, INTERIOR" in content
        assert f"*Surface, type=NODE, name=EMBMESH_FIBER_NODES_PLY_{k}" in content
        assert f"*Nset, nset=EMBMESH_FIBER_NODES_PLY_{k}, instance=Fibers-Ply-{k}" in content

    # 2. Surface interaction FiberHostBaseline
    assert "*Surface Interaction, name=FiberHostBaseline, USER, PROPERTIES=2, DEPVAR=2" in content
    # Ensure no *Surface Behavior under FiberHostBaseline
    inter_block = content[content.find("name=FiberHostBaseline"):content.find("name=FiberHostBaseline") + 200]
    assert "*Surface Behavior" not in inter_block

    # 3. Contact Inclusions
    assert "EMBMESH_FIBER_NODES_PLY_1 , EMBMESH_HOST_PLY_1" in content
    assert "EMBMESH_FIBER_NODES_PLY_1 , EMBMESH_HOST_PLY_2" in content
    assert "EMBMESH_FIBER_NODES_PLY_2 , EMBMESH_HOST_PLY_2" in content
    assert "EMBMESH_FIBER_NODES_PLY_2 , EMBMESH_HOST_PLY_1" in content

    # 4. Contact Property Assignment
    assert "EMBMESH_FIBER_NODES_PLY_1 , EMBMESH_HOST_PLY_1 , FiberHostBaseline" in content
    assert "EMBMESH_FIBER_NODES_PLY_2 , EMBMESH_HOST_PLY_2 , FiberHostBaseline" in content

    # 5. Nodal erosion controls with NO data line
    assert "*Contact Controls Assignment, nodal erosion=YES" in content
    lines = content.splitlines()
    for i, l in enumerate(lines):
        if l.strip() == "*Contact Controls Assignment, nodal erosion=YES":
            next_line = lines[i + 1].strip()
            assert next_line.startswith("*"), f"Expected next line to be a keyword, got: {next_line}"

    # 6. Contact thickness assignment
    for k in (1, 2):
        assert f"EMBMESH_FIBER_NODES_PLY_{k}, 0.000632" in content


def test_fortran_subroutines_formatting():
    """Verify that both Fortran .for files comply with fixed-form 72-column limits and standard structure."""
    outbox_dir = Path(__file__).resolve().parent.parent
    f1 = outbox_dir / "vuinteraction_baseline.for"
    f2 = outbox_dir / "VUEL_material_plus_vuinteraction.for"

    assert f1.exists(), f"Missing {f1}"
    assert f2.exists(), f"Missing {f2}"

    # Check vuinteraction_baseline.for strictly <= 72 columns on every single line
    lines1 = f1.read_text().splitlines()
    long_lines1 = [(i + 1, len(l), l) for i, l in enumerate(lines1) if len(l) > 72]
    assert not long_lines1, f"vuinteraction_baseline.for has lines exceeding 72 chars: {long_lines1[:5]}"

    # Verify key keywords in vuinteraction_baseline.for
    c1 = f1.read_text()
    assert "SUBROUTINE VUINTERACTION (" in c1.upper()
    assert "INCLUDE 'vaba_param.inc'" in c1
    assert "STATE(1, 1, K) = D0" in c1
    assert "STATE(2, 1, K) = 1.0D0" in c1
    assert "STRESS(1, K) = PRESS" in c1

    # Verify VUEL_material_plus_vuinteraction.for contains both VUEL and VUINTERACTION
    c2 = f2.read_text()
    assert "SUBROUTINE VUEL(" in c2.upper()
    assert "SUBROUTINE VUINTERACTION (" in c2.upper()
    assert len(c2.splitlines()) > 1500
