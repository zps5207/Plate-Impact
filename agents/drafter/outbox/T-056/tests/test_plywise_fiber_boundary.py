import numpy as np
from embmesh.geometry import boundary_faces
from embmesh.model import Part

from embmesh.plywise_vuel import _finish_boundary_fibers, _on_quad
from tests.test_stacked import plate


def _case(curvature, angle):
    elements, nodes = plate(curvature=curvature, nx=6, ny=6, nz=1)
    part = Part('Ply', nodes=nodes, elements=elements)
    import importlib.util
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / 'embmesh' / 'plyfibers.py'
    spec = importlib.util.spec_from_file_location('embmesh._plyfibers_boundary_test', path)
    module = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    fibers = module.ply_fibers(elements, nodes, angle, .15)
    x = [n for n, p in nodes.items() if abs(p[0]) < 1e-12]
    z = [n for n, p in nodes.items() if abs(p[1]) < 1e-12]
    outside = [n for n, p in nodes.items() if abs(p[0] - 1) < 1e-12 or abs(p[1] - 1) < 1e-12]
    lines = ['*Assembly']
    for ply in (1, 2):
        for name, labels in (('X', x), ('Z', z), ('Outside', outside)):
            lines += [f'*Nset, nset={name}, instance=Ply-{ply}', ', '.join(map(str, labels))]
    lines += ['*End Assembly', '*Step', '*Boundary', 'X, XSYMM', '*Boundary', 'Z, YSYMM',
              '*Boundary', 'Outside, ENCASTRE', '*End Step']
    output, report = _finish_boundary_fibers(lines, [angle, angle], {angle: fibers},
                                             np.array([0., 0., 1.]), False, part)
    return part, fibers, lines, output, report


def _sets(lines):
    result = {}
    for i, line in enumerate(lines):
        if line.startswith('*Nset') and 'instance=Fibers-Ply-' in line:
            name = line.split('nset=')[1].split(',')[0]
            instance = line.split('instance=')[1]
            result[(instance, name)] = {int(x) for x in lines[i + 1].split(',')}
    return result


def test_flat_and_curved_end_faces_and_sets():
    for curve in (0., .08):
        for angle in (0., 90., 45., 135.):
            part, fibers, before, after, report = _case(curve, angle)
            faces = boundary_faces(part.elements)
            quads = [np.array([part.nodes[n] for n in face]) for face in faces]
            memberships = _sets(after)
            for ply in (1, 2):
                key = f'Ply-{ply}'
                assert report[key]['ends_not_on_host_boundary_face'] == []
                assert report[key]['total_fiber_end_nodes'] == 2 * len(fibers)
                offset = 100000
                for fiber in fibers:
                    for label, point in ((offset, fiber.points[0]), (offset + len(fiber.points) - 1, fiber.points[-1])):
                        assert any(_on_quad(point, q, 1e-12) for q in quads)
                        expected = {'X': abs(point[0]) < 1e-12, 'Z': abs(point[1]) < 1e-12,
                                    'Outside': abs(point[0] - 1) < 1e-12 or abs(point[1] - 1) < 1e-12}
                        for name, present in expected.items():
                            assert (label in memberships.get((f'Fibers-Ply-{ply}', name), set())) == present
                    offset += len(fiber.points)
            assert after.count('*Boundary') == before.count('*Boundary')
            assert [line for line in after if line in ('X, XSYMM', 'Z, YSYMM', 'Outside, ENCASTRE')] == [
                line for line in before if line in ('X, XSYMM', 'Z, YSYMM', 'Outside, ENCASTRE')]





def test_corner_joins_both_sets():
    from embmesh.fibers import Fiber
    elements, nodes = plate(curvature=.08, nx=2, ny=2, nz=1)
    part = Part('Ply', nodes=nodes, elements=elements)
    line = Fiber(1, np.array([[0., 0., .5], [1., 0., .58]]), 0, 'angle_0')
    x = [n for n, p in nodes.items() if abs(p[0]) < 1e-12]
    z = [n for n, p in nodes.items() if abs(p[1]) < 1e-12]
    lines = ['*Assembly', '*Nset, nset=X, instance=Ply-1', ', '.join(map(str, x)),
             '*Nset, nset=Z, instance=Ply-1', ', '.join(map(str, z)),
             '*End Assembly', '*Step', '*Boundary', 'X, XSYMM', '*Boundary', 'Z, YSYMM', '*End Step']
    out, report = _finish_boundary_fibers(lines, [0], {0: [line]},
                                          np.array([0., 0., 1.]), False, part)
    sets = _sets(out)
    assert 100000 in sets[('Fibers-Ply-1', 'X')]
    assert 100000 in sets[('Fibers-Ply-1', 'Z')]
    assert report['Ply-1']['ends_not_on_host_boundary_face'] == []
