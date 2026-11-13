import numpy as np

from embmesh.fibers import _layer_positions
from embmesh.plyfibers import _centered_layer_positions


def test_centered_grid_splits_leftover_evenly():
    lo, hi, d = 0.0, 101.6, 0.632
    base = _layer_positions(lo, hi, d, 0.0)
    cen = _centered_layer_positions(lo, hi, d, 0.0)
    assert len(cen) == len(base) == 160
    left = cen[0] - d / 2 - lo
    right = hi - (cen[-1] + d / 2)
    assert abs(left - right) < 1e-9 and 0 < left < d / 2
    assert np.allclose(np.diff(cen), d)


def test_centered_grid_exact_fit_unchanged_and_empty():
    assert np.allclose(_centered_layer_positions(0.0, 1.0, 0.25, 0.0), _layer_positions(0.0, 1.0, 0.25, 0.0))
    assert _centered_layer_positions(0.0, 0.1, 0.25, 0.0) == []
