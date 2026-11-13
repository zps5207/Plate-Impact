"""Through-thickness smearing of the per-host fiber fraction (plywise_vuel.smear_through_thickness)."""
from types import SimpleNamespace

import numpy as np
import pytest

from embmesh.plywise_vuel import convert_plywise_hosts, smear_through_thickness


def _column_part(n_cols=4, layers=3):
    nodes, elements, label, nid = {}, {}, 1, 1
    for c in range(n_cols):
        x0 = c * 1.0
        for k in range(layers + 1):
            for (dx, dy) in ((0, 0), (1, 0), (1, 1), (0, 1)):
                nodes[nid] = np.array([x0 + dx, dy, k / layers])
                nid += 1
    for c in range(n_cols):
        for k in range(layers):
            base = 1 + c * 4 * (layers + 1) + 4 * k
            conn = list(range(base, base + 4)) + list(range(base + 4, base + 8))
            elements[label] = SimpleNamespace(label=label, connectivity=conn)
            label += 1
    return elements, nodes


def test_smear_averages_each_column_and_conserves_volume():
    elements, nodes = _column_part()
    raw = {}
    for lab in elements:
        raw[lab] = {0: 0.1, 1: 0.9, 2: 0.2}[(lab - 1) % 3]   # outer, middle, outer
    out = smear_through_thickness(raw, elements, nodes)
    assert set(out) == set(raw)
    assert all(v == pytest.approx(0.4) for v in out.values())
    assert sum(out.values()) == pytest.approx(sum(raw.values()))
    assert min(1 - v for v in out.values()) > 0.5


def test_smear_keeps_columns_separate():
    elements, nodes = _column_part()
    raw = {lab: float((lab - 1) // 3) for lab in elements}   # constant per column
    out = smear_through_thickness(raw, elements, nodes)
    assert out == pytest.approx(raw)


def test_smear_requires_precise():
    with pytest.raises(ValueError):
        convert_plywise_hosts([], None, [0.0], {}, 1e-3, smear=True, precise=False)
