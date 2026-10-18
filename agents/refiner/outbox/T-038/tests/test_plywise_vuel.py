import numpy as np

from embmesh.parser import parse_deck
from embmesh.plywise import write_plywise_deck
from embmesh.vuelghost import GHOST_ELSET
from embmesh.plywise_vuel import finish_plywise_fibers
from embmesh.fibers import Fiber
from embmesh.model import Element, Part


def plate():
    nodes = {1: np.array([0., 0., 0.]), 2: np.array([0., 1., 0.]),
             3: np.array([1., 1., 0.]), 4: np.array([1., 0., 0.])}
    for k in range(1, 5):
        nodes[k + 4] = nodes[k] + np.array([0., 0., .01])
    return Part('Plate', nodes=nodes,
                elements={1: Element(1, (1, 2, 3, 4, 5, 6, 7, 8), 'C3D8R')},
                elsets={'Plate': {1}})


def source(part):
    lines = ['*Part, name=Plate', '*Node']
    lines += [f'{i}, {p[0]}, {p[1]}, {p[2]}' for i, p in part.nodes.items()]
    lines += ['*Element, type=C3D8R', '1, 1, 2, 3, 4, 5, 6, 7, 8',
              '*Elset, elset=Plate', '1', '*Solid Section, elset=Plate, material=Matrix', ',',
              '*End Part', '*Assembly, name=Assembly', '*Instance, name=Plate-1, part=Plate',
              '0, 0, 0', '*End Instance', '*End Assembly', '*Material, name=Matrix',
              '*Elastic', '1, 0.3']
    return '\n'.join(lines) + '\n'


def test_plywise_vuel_ghost(tmp_path):
    part = plate()
    for point in part.nodes.values():
        point[0] *= .012
        point[1] *= .018
    original = source(part).replace('*Elastic\n1, 0.3',
        '*Density\n1000\n*Elastic\n2e9, 0.3\n*Plastic\n2e6, 0\n3e6, 0.1\n'
        '*Damage Initiation, criterion=DUCTILE\n0.25, 0, 0\n'
        '*Damage Evolution, type=DISPLACEMENT\n0.001\n'
        '*Material, name=Fiber\n*Density\n1000\n*Elastic\n2e9, 0.3\n'
        '*Step\n*Dynamic, Explicit\n, 0.001\n*End Step')
    path = tmp_path / 'source.inp'
    out = tmp_path / 'output.inp'
    path.write_text(original)
    meta = write_plywise_deck(path, out, plies=4, layup=[0, 90, 0, 90],
                              fiber_diameter=.001, fiber_gap=.0002,
                              host_mode='vuel-ghost', cohesion=None)
    text = out.read_text()
    deck = parse_deck(out)
    assert len(deck.instances) == 8
    assert '*Element, type=VU1, elset=EMBMESH_VUEL_HOST' in text
    assert '*Element, type=C3D8R, elset=EMBMESH_GHOST_HOST' in text
    ghost_material = text.split('*Material, name=EMBMESH_GHOST_MATERIAL', 1)[1].split('*Material,', 1)[0]
    assert '*Density\n0.1' in ghost_material
    assert '*Elastic\n200000, 0.3' in ghost_material
    assert '*Plastic\n200, 0\n300, 0.1' in ghost_material
    assert text.count('*Initial Conditions, type=SOLUTION') == 4
    assert text.count(f'*Embedded Element, host elset=Ply-') == 4
    assert all(f'*Embedded Element, host elset=Ply-{k}.{GHOST_ELSET}' in text for k in range(1, 5))
    assert 'host elset=Ply-1.PLY' not in text
    assert '*Elset, elset=_Ply-4_top_S2, internal, instance=Ply-4\n2' in text
    assert meta['vuel_ghost']['total_vuel_elements'] == 4
    assert meta['vuel_ghost']['total_ghost_elements'] == 4
    assert meta['vuel_ghost']['ghost_scale'] == 1e-4
    assert meta['vuel_ghost']['expected_host_mass_ratio_including_ghost'] == 1.0001
    fractions = meta['vuel_ghost']['per_ply_fractions']
    assert fractions['Ply-1']['mean'] != fractions['Ply-2']['mean']


def test_assembly_symmetry_reaches_each_fiber_instance(tmp_path):
    path = tmp_path / 'source.inp'
    path.write_text(source(plate()).replace('*End Assembly',
        '*Nset, nset=X, instance=Plate-1\n1, 2, 5, 6\n*End Assembly') +
        '*Boundary\nX, XSYMM\n')
    fiber = Fiber(1, np.array([[0., .2, .002], [.1, .2, .002]]), 0, 'angle_0')
    lines = ['*Assembly', '*End Assembly', '*Step', '*End Step']
    result, counts = finish_plywise_fibers(lines, path, 'Plate-1',
                                           [0, 0], {0: [fiber]}, np.array([0., 0., .0025]), True)
    written = '\n'.join(result)
    assert counts == {'Ply-1': {'X': 1}, 'Ply-2': {'X': 1}}
    assert '*Nset, nset=EMBMESH_PLY1_X_FIBER_SYMM, instance=Fibers-Ply-1\n100000' in written
    assert '*Nset, nset=EMBMESH_PLY2_X_FIBER_SYMM, instance=Fibers-Ply-2\n100000' in written
    assert written.count('*Boundary') == 2
