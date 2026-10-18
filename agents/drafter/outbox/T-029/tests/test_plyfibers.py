import importlib.util
from pathlib import Path
import sys
import numpy as np
import pytest
import warnings

repo_root = Path(__file__).resolve().parents[5]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))
import embmesh

# Load delivered plyfibers directly
_plyfibers_path = Path(__file__).resolve().parent.parent / "embmesh" / "plyfibers.py"
_spec = importlib.util.spec_from_file_location("embmesh.plyfibers", str(_plyfibers_path))
_mod = importlib.util.module_from_spec(_spec)
sys.modules["embmesh.plyfibers"] = _mod
_spec.loader.exec_module(_mod)

from embmesh.plyfibers import (
    PlyInstanceInfo,
    expand_layup,
    ply_fibers,
    emit_plyfibers_deck,
    append_plyfibers_to_deck,
    format_angle_name,
)
from embmesh.model import Element, Part
from embmesh.parser import parse_deck
from embmesh.geometry import point_in_hex, hex_volume
from tests.test_stacked import plate


def test_layup_expansion():
    # Basic list
    assert expand_layup([0, 90, 45, -45], 4) == [0.0, 90.0, 45.0, -45.0]

    # Repeat
    assert expand_layup([0, 90], 4, repeat=2) == [0.0, 90.0, 0.0, 90.0]

    # Symmetric
    assert expand_layup([0, 90], 4, symmetric=True) == [0.0, 90.0, 90.0, 0.0]
    assert expand_layup([0, 45, -45, 90], 8, symmetric=True) == [0.0, 45.0, -45.0, 90.0, 90.0, -45.0, 45.0, 0.0]

    # Both repeat and symmetric
    assert expand_layup([0, 90], 8, repeat=2, symmetric=True) == [0.0, 90.0, 0.0, 90.0, 90.0, 0.0, 90.0, 0.0]

    # Length mismatch raises ValueError
    with pytest.raises(ValueError, match="does not match requested ply count"):
        expand_layup([0, 90, 45], 4)

    # Invalid repeat raises ValueError
    with pytest.raises(ValueError, match="repeat must be a positive integer"):
        expand_layup([0, 90], 4, repeat=0)


def test_diameter_limits_and_warning():
    elems, nodes = plate(curvature=0.0, nx=4, ny=4, nz=1)
    # nz=1 means plate thickness is 1.0 m
    # 1. diameter > thickness raises ValueError
    with pytest.raises(ValueError, match="exceeds ply thickness"):
        ply_fibers(elems, nodes, angle=0.0, diameter=1.5)

    # 2. diameter > 0.8 * thickness warns UserWarning
    with pytest.warns(UserWarning, match="exceeds 0.8x ply thickness"):
        ply_fibers(elems, nodes, angle=0.0, diameter=0.85)

    # 3. diameter <= 0.8 * thickness emits no warning
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        fibs = ply_fibers(elems, nodes, angle=0.0, diameter=0.5)
        assert len(fibs) > 0


def test_flat_plate_fiber_angles():
    elems, nodes = plate(curvature=0.0, nx=6, ny=6, nz=1)
    test_angles = [0.0, 90.0, 45.0, -45.0, 30.0, 60.0]

    for ang in test_angles:
        fibers = ply_fibers(elems, nodes, angle=ang, diameter=0.15)
        assert len(fibers) > 0
        expected_rad = np.deg2rad(ang)

        for f in fibers:
            pts = f.points
            segs = pts[1:] - pts[:-1]
            lengths = np.linalg.norm(segs, axis=1)
            tangents = segs / lengths[:, None]

            # In-plane tangent angle
            measured_angles = np.arctan2(tangents[:, 1], tangents[:, 0])
            for m in measured_angles:
                # Modulo pi because fiber direction is an orientation axis
                diff = abs(m - expected_rad)
                diff = min(diff, abs(diff - np.pi), abs(diff - 2 * np.pi))
                assert diff < 1e-6, f"Angle mismatch for {ang} deg: measured {np.rad2deg(m)} deg"


def test_curved_plate_containment_and_tangent():
    elems, nodes = plate(curvature=0.08, nx=6, ny=6, nz=1)
    hosts = [np.array([nodes[n] for n in e.connectivity]) for e in elems.values()]

    for ang in [0.0, 90.0, 45.0, -45.0]:
        fibers = ply_fibers(elems, nodes, angle=ang, diameter=0.2)
        assert len(fibers) > 0

        for f in fibers:
            pts = f.points
            mids = 0.5 * (pts[:-1] + pts[1:])
            samples = list(pts) + list(mids)
            for p in samples:
                assert any(
                    np.all(p >= h.min(0) - 1e-9) and np.all(p <= h.max(0) + 1e-9) and point_in_hex(p, h)
                    for h in hosts
                ), f"Sample {p} outside host hexes for angle {ang}"


def test_scrambled_hex_ordering_gives_identical_fibers():
    elems, nodes = plate(curvature=0.08, nx=5, ny=5, nz=1)
    SIGNS = np.array([[-1,-1,1],[-1,1,1],[1,1,1],[1,-1,1],[-1,-1,-1],[-1,1,-1],[1,1,-1],[1,-1,-1]], float)

    perm_rot_z = [int(np.where(np.all(SIGNS == [s[1], -s[0], s[2]], axis=1))[0][0]) for s in SIGNS]
    perm_cyc1 = [int(np.where(np.all(SIGNS == [s[2], s[0], s[1]], axis=1))[0][0]) for s in SIGNS]
    perm_cyc2 = [int(np.where(np.all(SIGNS == [s[1], s[2], s[0]], axis=1))[0][0]) for s in SIGNS]
    perms = [perm_rot_z, perm_cyc1, perm_cyc2]

    rng = np.random.default_rng(123)
    scrambled_elems = {}
    for eid, elem in elems.items():
        p = perms[rng.integers(0, len(perms))]
        new_conn = tuple(elem.connectivity[i] for i in p)
        assert hex_volume([nodes[n] for n in new_conn]) > 0
        scrambled_elems[eid] = Element(eid, new_conn, elem.type)

    for ang in [0.0, 90.0, 45.0, -45.0]:
        fibers_orig = ply_fibers(elems, nodes, angle=ang, diameter=0.25)
        fibers_scrambled = ply_fibers(scrambled_elems, nodes, angle=ang, diameter=0.25)

        assert len(fibers_orig) == len(fibers_scrambled)
        for f1, f2 in zip(fibers_orig, fibers_scrambled):
            assert f1.label == f2.label
            np.testing.assert_allclose(f1.points, f2.points, atol=1e-12)


def test_world_coordinates_containment_after_translation(tmp_path):
    # Single-hex ply
    elems, nodes = plate(curvature=0.08, nx=5, ny=5, nz=1)
    ply_thickness = 1.0  # nz=1 on [0, 1] has thickness 1.0
    plies = 4
    ply_angles = [0.0, 90.0, 45.0, -45.0]
    step = np.array([0.0, 0.0, ply_thickness])

    # Distinct angle fibers generated in ply Part frame
    fibers_by_angle = {
        ang: ply_fibers(elems, nodes, angle=ang, diameter=0.25)
        for ang in set(ply_angles)
    }

    # Instance definitions
    ply_instances = [
        PlyInstanceInfo(name=f"Ply-{k}", translation=(k - 1) * step)
        for k in range(1, plies + 1)
    ]

    # Write deck
    source_deck = "*Part, name=Ply\n*End Part\n*Assembly, name=Assembly\n"
    for inst in ply_instances:
        source_deck += f"*Instance, name={inst.name}, part=Ply\n{inst.translation[0]}, {inst.translation[1]}, {inst.translation[2]}\n*End Instance\n"
    source_deck += "*End Assembly\n"

    source_path = tmp_path / "source.inp"
    source_path.write_text(source_deck)
    output_path = tmp_path / "output.inp"

    append_plyfibers_to_deck(
        source_path, output_path, ply_instances, fibers_by_angle, ply_angles, diameter=0.25
    )

    deck = parse_deck(output_path)

    # Audit in world coordinates for each ply instance
    for k, ply_inst in enumerate(ply_instances, start=1):
        ang = ply_angles[k - 1]
        ang_str = format_angle_name(ang)
        fiber_inst_name = f"Fibers-Ply-{k}"

        # Host elements in world coordinates
        ply_trans = ply_inst.translation
        ply_hexes = [
            np.array([nodes[n] + ply_trans for n in e.connectivity])
            for e in elems.values()
        ]

        # Fiber nodes in world coordinates
        fib_nodes = deck.instance_nodes(fiber_inst_name)
        fpart = deck.parts[f"Fibers-{ang_str}"]

        bad_points = []
        for e in fpart.elements.values():
            p0 = fib_nodes[e.connectivity[0]]
            p1 = fib_nodes[e.connectivity[1]]
            mid = 0.5 * (p0 + p1)
            for p in (p0, p1, mid):
                inside = any(
                    np.all(p >= h.min(0) - 1e-9) and np.all(p <= h.max(0) + 1e-9) and point_in_hex(p, h)
                    for h in ply_hexes
                )
                if not inside:
                    bad_points.append(p)

        assert len(bad_points) == 0, f"Found {len(bad_points)} fiber points outside host in Ply-{k}"
