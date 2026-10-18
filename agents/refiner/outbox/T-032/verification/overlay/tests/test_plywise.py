import numpy as np
import pytest

from embmesh.geometry import hex_volume
from embmesh.model import Element, Part
from embmesh.parser import parse_deck
from embmesh.plywise import (EmbmeshError, build_ply_part, interface_pairs,
                             write_plywise_deck)
from embmesh.cli import main


def plate(scrambled=False, warped=False):
    nodes = {1: np.array([0., 0., 0.]), 2: np.array([0., 1., 0.]),
             3: np.array([1., 1., 0.]), 4: np.array([1., 0., 0.])}
    for k in range(1, 5):
        nodes[k + 4] = nodes[k] + np.array([0., 0., 0.01])
    if warped:
        nodes[8] += [0.2, 0., 0.]
    conn = (1, 2, 3, 4, 5, 6, 7, 8)
    if scrambled:
        conn = (1, 5, 6, 2, 4, 8, 7, 3)
    return Part('Plate', nodes=nodes, elements={1: Element(1, conn, 'C3D8R')},
                elsets={'Plate': {1}})


def source(part):
    lines = ['*Part, name=Plate', '*Node']
    lines += [f'{i}, {p[0]}, {p[1]}, {p[2]}' for i, p in part.nodes.items()]
    lines += ['*Element, type=C3D8R', '1, ' + ', '.join(map(str, part.elements[1].connectivity)),
              '*Elset, elset=Plate', '1', '*Solid Section, elset=Plate, material=Matrix', ',',
              '*End Part', '*Assembly, name=Assembly', '*Instance, name=Plate-1, part=Plate',
              '0, 0, 0', '*End Instance', '*End Assembly', '*Material, name=Matrix',
              '*Elastic', '1, 0.3']
    return '\n'.join(lines) + '\n'


def test_count_and_faces():
    for scrambled in (False, True):
        part = plate(scrambled)
        ply, meta = build_ply_part(part, plies=5)
        assert meta['plies'] == 5
        assert meta['resulting_ply_thickness'] == pytest.approx(.002)
        assert ply.surfaces['PLY_BOTTOM'] == [(1, 'S1' if not scrambled else 'S6')]
        assert ply.surfaces['PLY_TOP'] == [(1, 'S2' if not scrambled else 'S4')]
        _, target = build_ply_part(part, ply_thickness=.002)
        assert target['plies'] == 5
        assert ply.elsets['PLY'] == {1}
    assert interface_pairs(3) == [('Ply-1_top', 'Ply-2_bottom'),
                                  ('Ply-2_top', 'Ply-3_bottom')]


def test_nontranslation_raises():
    with pytest.raises(EmbmeshError, match='translation mismatch'):
        build_ply_part(plate(warped=True), plies=2)


def test_adjacent_hexes_with_different_local_axes():
    left = plate()
    nodes = dict(left.nodes)
    nodes.update({9: np.array([2., 0., 0.]), 10: np.array([2., 1., 0.]),
                  11: np.array([2., 0., .01]), 12: np.array([2., 1., .01])})
    right = (4, 8, 7, 3, 9, 11, 12, 10)
    # Here zeta is in plane; local eta is the stack direction.
    part = Part('Plate', nodes=nodes,
                elements={1: left.elements[1], 2: Element(2, right, 'C3D8R')})
    ply, meta = build_ply_part(part, plies=2)
    assert meta['plies'] == 2
    assert ply.surfaces['PLY_BOTTOM'][0] == (1, 'S1')
    assert ply.surfaces['PLY_BOTTOM'][1][1] != 'S1'


def test_write_reparse_volumes_and_interfaces(tmp_path):
    original = plate(scrambled=True)
    inp = tmp_path / 'source.inp'
    out = tmp_path / 'ply.inp'
    inp.write_text(source(original))
    meta = write_plywise_deck(inp, out, plies=5)
    deck = parse_deck(out)
    assert meta['plies'] == 5
    assert list(deck.instances) == [f'Ply-{k}' for k in range(1, 6)]
    assert all(deck.instances[f'Ply-{k}'].translation[2] == pytest.approx((k - 1) * .002)
               for k in range(1, 6))
    assert '*Solid Section, elset=Plate, material=Matrix' in out.read_text()
    assert '*Surface, type=ELEMENT, name=Ply-1_bottom' in out.read_text()
    assert '*Elset, elset=_Ply-1_bottom_S6, internal, instance=Ply-1' in out.read_text()
    assert '*Surface, type=ELEMENT, name=PLY_BOTTOM' not in out.read_text()
    original_volume = hex_volume(np.array([original.nodes[i] for i in original.elements[1].connectivity]))
    ply = deck.parts['Plate']
    ply_volume = hex_volume(np.array([ply.nodes[i] for i in ply.elements[1].connectivity]))
    assert 5 * ply_volume == pytest.approx(original_volume, abs=1e-12)
    for k in range(1, 5):
        a = deck.instance_nodes(f'Ply-{k}')
        b = deck.instance_nodes(f'Ply-{k + 1}')
        for bottom, top in ((1, 5), (2, 6), (3, 7), (4, 8)):
            np.testing.assert_allclose(a[top], b[bottom], atol=1e-9)


def test_cli_and_old_instance_reference_report(tmp_path, capsys):
    inp, out = tmp_path / 'source.inp', tmp_path / 'ply.inp'
    inp.write_text(source(plate()).replace('*End Assembly',
              '*Nset, nset=Fixture, instance=Plate-1\n1, 2\n*End Assembly'))
    assert main(['plywise', str(inp), '--instance', 'Plate-1', '--output', str(out),
                 '--plywise', '--ply-thickness', '.002']) == 0
    assert 'assembly_sets_rewritten' in capsys.readouterr().out
    assert 'instance=Plate-1' not in out.read_text()
    assert '*Nset, nset=Fixture, instance=Ply-5' in out.read_text()
    assert len(parse_deck(out).instances) == 5


def test_rotated_instance_and_assembly_sets(tmp_path):
    inp, out = tmp_path / 'source.inp', tmp_path / 'ply.inp'
    text = source(plate()).replace('0, 0, 0\n*End Instance',
              '1, 2, 3\n0, 0, 0, 0, 1, 0, 90\n*End Instance')
    text = text.replace('*End Assembly',
              '*Nset, nset=Outside, instance=Plate-1\n1, 2\n'
              '*Elset, elset=plate, instance=Plate-1\n1\n'
              '*Elset, elset=_Surf-1_S2, internal, instance=Plate-1\n1\n*End Assembly')
    inp.write_text(text)
    old = parse_deck(inp).instance_nodes('Plate-1')
    meta = write_plywise_deck(inp, out, plies=5)
    deck = parse_deck(out)
    first = deck.instance_nodes('Ply-1')
    for label in (1, 2, 3, 4):
        np.testing.assert_allclose(first[label], old[label], atol=1e-12)
    assert all(deck.instances[f'Ply-{k}'].rotation_angle == 0 for k in range(1, 6))
    for k in range(1, 5):
        a, b = deck.instance_nodes(f'Ply-{k}'), deck.instance_nodes(f'Ply-{k+1}')
        for bottom, top in ((1, 5), (2, 6), (3, 7), (4, 8)):
            np.testing.assert_allclose(a[top], b[bottom], atol=1e-12)
    written = out.read_text()
    assert written.count('*Nset, nset=Outside, instance=Ply-') == 5
    assert written.count('*Elset, elset=plate, instance=Ply-') == 5
    assert '*Elset, elset=_Surf-1_S2, internal, instance=Plate-1' in written
    assert meta['expected_interface_gap_max'] == 0
    assert meta['impact_surface_elsets_left'] == ['*elset _Surf-1_S2']
