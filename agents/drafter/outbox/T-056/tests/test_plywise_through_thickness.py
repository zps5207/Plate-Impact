import numpy as np
import pytest

from embmesh.geometry import hex_volume, point_in_hex
from embmesh.model import Element, Part
from embmesh.parser import parse_deck
from embmesh.plywise import (EmbmeshError, build_ply_part,
                             write_plywise_deck)
from embmesh.cli import main


def make_single_hex_plate():
    """A simple 1-element plate 1x1 in plane, 0.01 thick along z."""
    nodes = {1: np.array([0., 0., 0.]), 2: np.array([0., 1., 0.]),
             3: np.array([1., 1., 0.]), 4: np.array([1., 0., 0.])}
    for k in range(1, 5):
        nodes[k + 4] = nodes[k] + np.array([0., 0., 0.01])
    conn = (1, 2, 3, 4, 5, 6, 7, 8)
    return Part('Plate', nodes=nodes, elements={1: Element(1, conn, 'C3D8R')},
                elsets={'Plate': {1}},
                nsets={'fix': {1, 2, 5, 6}})


def make_two_hex_plate():
    """A 2-element plate (adjacent in-plane along x), 1-element thick along z."""
    # Column 1: (0,0) -> 1, 5; Column 2: (0,1) -> 2, 6
    # Column 3: (1,1) -> 3, 7; Column 4: (1,0) -> 4, 8
    # Column 5: (2,1) -> 9, 11; Column 6: (2,0) -> 10, 12
    nodes = {
        1: np.array([0., 0., 0.]), 2: np.array([0., 1., 0.]),
        3: np.array([1., 1., 0.]), 4: np.array([1., 0., 0.]),
        5: np.array([0., 0., 0.01]), 6: np.array([0., 1., 0.01]),
        7: np.array([1., 1., 0.01]), 8: np.array([1., 0., 0.01]),
        9: np.array([2., 1., 0.]), 10: np.array([2., 0., 0.]),
        11: np.array([2., 1., 0.01]), 12: np.array([2., 0., 0.01]),
    }
    conn1 = (1, 2, 3, 4, 5, 6, 7, 8)
    conn2 = (4, 3, 9, 10, 8, 7, 11, 12)
    return Part('Plate', nodes=nodes,
                elements={1: Element(1, conn1, 'C3D8R'), 2: Element(2, conn2, 'C3D8R')},
                elsets={'Plate': {1, 2}},
                nsets={'X': {1, 2, 5, 6}, 'fix': {1, 4, 10, 5, 8, 12}})


def deck_source(part):
    lines = [f'*Part, name={part.name}', '*Node']
    lines += [f'{i}, {p[0]}, {p[1]}, {p[2]}' for i, p in part.nodes.items()]
    lines += ['*Element, type=C3D8R']
    for eid, elem in part.elements.items():
        lines.append(f'{eid}, ' + ', '.join(map(str, elem.connectivity)))
    lines += ['*Elset, elset=Plate']
    lines.append(', '.join(map(str, part.elements.keys())))
    for name, s in part.nsets.items():
        lines.append(f'*Nset, nset={name}')
        lines.append(', '.join(map(str, sorted(s))))
    lines += ['*Solid Section, elset=Plate, material=Matrix', ',',
              '*End Part', '*Assembly, name=Assembly',
              f'*Instance, name=Plate-1, part={part.name}',
              '0, 0, 0', '*End Instance', '*End Assembly',
              '*Material, name=Matrix', '*Elastic', '1, 0.3',
              '*Material, name=Fiber', '*Elastic', '10, 0.2']
    return '\n'.join(lines) + '\n'


def test_regression_through_thickness_1(tmp_path):
    """Default through_thickness=1 produces byte-identical results to explicit 1."""
    part = make_two_hex_plate()
    inp = tmp_path / 'source.inp'
    inp.write_text(deck_source(part))
    out_default = tmp_path / 'out_def.inp'
    out_explicit = tmp_path / 'out_exp.inp'

    write_plywise_deck(inp, out_default, plies=2)
    write_plywise_deck(inp, out_explicit, plies=2, through_thickness=1)

    assert out_default.read_text() == out_explicit.read_text()


def test_invalid_through_thickness_raises(tmp_path):
    """Even values and non-positive counts must raise EmbmeshError."""
    part = make_single_hex_plate()

    # Even values
    for val in (2, 4, 6):
        with pytest.raises(EmbmeshError, match='--through-thickness must be odd'):
            build_ply_part(part, plies=2, through_thickness=val)

    # Non-positive values and invalid types
    for val in (0, -1, -3, 1.5, True, False):
        with pytest.raises(EmbmeshError):
            build_ply_part(part, plies=2, through_thickness=val)

    # CLI exit code 5 on even count
    inp = tmp_path / 'source.inp'
    inp.write_text(deck_source(part))
    out = tmp_path / 'out.inp'
    ret = main(['plywise', str(inp), '--instance', 'Plate-1', '--output', str(out), '--plies', '2', '--through-thickness', '2'])
    assert ret == 5


def test_through_thickness_3_counts_and_geometry():
    """N_t = 3 produces 3x elements per ply and 4x nodes per column."""
    part = make_two_hex_plate()
    ply, meta = build_ply_part(part, plies=2, through_thickness=3)

    assert meta['through_thickness'] == 3
    assert meta['resulting_ply_thickness'] == pytest.approx(0.005)
    assert meta['through_thickness_element_thickness'] == pytest.approx(0.005 / 3.0)

    # 2 elements originally * 3 layers = 6 elements
    assert len(ply.elements) == 6
    E_stride = meta['E_stride']
    N_stride = meta['N_stride']
    assert E_stride >= 10
    assert N_stride >= 100

    # 6 columns * 4 node levels = 24 nodes
    assert len(ply.nodes) == 24

    # Verify Jacobian volume of each subdivided element
    for eid, elem in ply.elements.items():
        pts = np.array([ply.nodes[n] for n in elem.connectivity])
        vol = hex_volume(pts)
        assert vol > 0.0
        # Total ply volume must be 0.005 * 2.0 = 0.01 m^3
        # Each element volume = 1.0 * 1.0 * (0.005 / 3) = 0.005 / 3
        assert vol == pytest.approx(0.005 / 3.0, rel=1e-6)


def test_through_thickness_3_surfaces_exterior_only():
    """PLY_BOTTOM and PLY_TOP must only contain exterior faces, never interior faces."""
    part = make_two_hex_plate()
    ply, meta = build_ply_part(part, plies=2, through_thickness=3)
    E_stride = meta['E_stride']

    bot_elements = {eid for eid, _ in ply.surfaces['PLY_BOTTOM']}
    top_elements = {eid for eid, _ in ply.surfaces['PLY_TOP']}

    # Bottom surface elements must be layer 0 elements (1 and 2)
    assert bot_elements == {1, 2}

    # Top surface elements must be layer 2 elements (1 + 2*E_stride, 2 + 2*E_stride)
    assert top_elements == {1 + 2 * E_stride, 2 + 2 * E_stride}

    # No middle layer elements (layer 1) in exterior surfaces
    mid_elements = {1 + E_stride, 2 + E_stride}
    assert not (bot_elements & mid_elements)
    assert not (top_elements & mid_elements)


def test_through_thickness_3_fiber_containment(tmp_path):
    """Fibers generated on the ply mid-plane must be strictly hosted inside layer 1 (middle layer)."""
    part = make_single_hex_plate()
    inp = tmp_path / 'source.inp'
    inp.write_text(deck_source(part))
    out = tmp_path / 'out_fibers.inp'

    # Ply thickness = 0.01 / 2 = 0.005 m. Subdivided element thickness = 0.005 / 3 = 0.001667 m.
    # Fiber diameter 0.002 m is > element thickness (0.001667 m) but < ply thickness (0.005 m).
    meta = write_plywise_deck(
        inp, out, plies=2, through_thickness=3,
        layup=[0, 0], fiber_diameter=0.002, fiber_gap=0.1
    )

    deck = parse_deck(out)
    ply_part = deck.parts['Plate']
    E_stride = meta['E_stride']
    mid_elem_id = 1 + E_stride  # layer 1 is middle layer

    mid_elem = ply_part.elements[mid_elem_id]
    mid_pts = np.array([ply_part.nodes[n] for n in mid_elem.connectivity])

    # Check that fiber instance exists and nodes lie inside mid_pts
    assert 'Fibers-Ply-1' in deck.instances
    fiber_nodes = deck.instance_nodes('Fibers-Ply-1')
    assert len(fiber_nodes) > 0

    z_min_mid = mid_pts[:, 2].min()
    z_max_mid = mid_pts[:, 2].max()
    mid_plane_z = 0.5 * (z_min_mid + z_max_mid)

    for nid, pt in fiber_nodes.items():
        # z-coordinate should be on the mid-plane of the ply (and middle element)
        assert pt[2] == pytest.approx(mid_plane_z, abs=1e-8)
        assert z_min_mid - 1e-8 <= pt[2] <= z_max_mid + 1e-8


def test_through_thickness_3_boundary_nodes_expanded(tmp_path):
    """Boundary conditions on part / instance sets expand to include intermediate node levels."""
    part = make_two_hex_plate()
    inp = tmp_path / 'source.inp'
    inp.write_text(deck_source(part))
    out = tmp_path / 'out_bcs.inp'

    meta = write_plywise_deck(inp, out, plies=2, through_thickness=3)
    deck = parse_deck(out)
    ply_part = deck.parts['Plate']
    N_stride = meta['N_stride']

    # Column 1 (nodes 1 and 5) is in 'X'.
    # In ply_part.nsets['X'], nodes 1, 5, plus intermediate nodes 1 + N_stride, 1 + 2*N_stride must exist.
    assert 1 in ply_part.nsets['X']
    assert 5 in ply_part.nsets['X']
    assert 1 + N_stride in ply_part.nsets['X']
    assert 1 + 2 * N_stride in ply_part.nsets['X']
