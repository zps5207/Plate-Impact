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
    assert interface_pairs(3) == [('Ply-1.PLY_TOP', 'Ply-2.PLY_BOTTOM'),
                                  ('Ply-2.PLY_TOP', 'Ply-3.PLY_BOTTOM')]


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
    assert 'instance=Plate-1' in capsys.readouterr().out
    assert len(parse_deck(out).instances) == 5
