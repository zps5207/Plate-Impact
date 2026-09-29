import math
import numpy as np
from embmesh.curved import radial_director, shell_layers
from embmesh.curved_layup import concentric_shell_fibers, cylindrical_fibers, spherical_fibers


def test_curved_director_and_layers():
    p = np.array([[2., 0, 0], [0, 2., 0], [-2, 0, 0]])
    assert np.allclose(radial_director(p), p / 2)
    fs, rs = concentric_shell_fibers(2, 3, 1, .2)
    assert len(rs) > 0
    # every fiber's points sit on its own layer's radius (horizontal distance from the z axis)
    assert all(abs(np.linalg.norm(f.points[0][:2]) - rs[f.layer]) < 1e-9 for f in fs)


def test_cylindrical_fibers_alternate_and_stay_on_radius():
    nn = {}
    idx = 1
    for r in (2.0, 3.0):
        for th in np.linspace(0, 2 * np.pi, 24, endpoint=False):
            for z in (0.0, 5.0):
                nn[idx] = np.array([r * np.cos(th), r * np.sin(th), z]); idx += 1
    fibers, meta = cylindrical_fibers(nn, 0.2, axis_point=(0, 0, 0), axis_dir=(0, 0, 1))
    assert meta["full_circle"] is True
    axial = [f for f in fibers if f.direction == "t0"]; hoop = [f for f in fibers if f.direction == "t90"]
    assert axial and hoop
    # axial fibers run parallel to the axis (constant x,y)
    for f in axial:
        assert np.allclose(f.points[:, 0], f.points[0, 0], atol=1e-9)
        assert np.allclose(f.points[:, 1], f.points[0, 1], atol=1e-9)
    # hoop fibers stay at a constant radius and constant z
    for f in hoop:
        r = np.linalg.norm(f.points[:, :2], axis=1)
        assert np.allclose(r, r[0], atol=1e-9)
        assert np.allclose(f.points[:, 2], f.points[0, 2], atol=1e-9)
    # layers alternate directions
    by_layer = sorted({(f.layer, f.direction) for f in fibers})
    dirs = [d for _, d in by_layer]
    assert all(dirs[i] != dirs[i + 1] for i in range(len(dirs) - 1))


def test_spherical_fibers_alternate_and_stay_on_radius():
    nn = {}
    idx = 1
    for r in (2.0, 2.5):
        for phi in np.linspace(0.3, math.pi - 0.3, 10):
            for th in np.linspace(0, 2 * math.pi, 16, endpoint=False):
                nn[idx] = np.array([r * math.sin(phi) * math.cos(th), r * math.sin(phi) * math.sin(th), r * math.cos(phi)])
                idx += 1
    fibers, meta = spherical_fibers(nn, 0.15, center=(0, 0, 0), pole_axis=(0, 0, 1))
    merid = [f for f in fibers if f.direction == "t0"]; lat = [f for f in fibers if f.direction == "t90"]
    assert merid and lat
    for f in lat:  # latitude fibers: constant radius and constant z (colatitude)
        r = np.linalg.norm(f.points, axis=1)
        assert np.allclose(r, r[0], atol=1e-6)
        assert np.allclose(f.points[:, 2], f.points[0, 2], atol=1e-6)
    for f in merid:  # meridian fibers: constant radius, constant longitude
        r = np.linalg.norm(f.points, axis=1)
        assert np.allclose(r, r[0], atol=1e-6)
