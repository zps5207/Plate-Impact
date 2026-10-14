from pathlib import Path

import numpy as np
import pytest

from embmesh.fibers import Fiber, flat_disc_fibers
from embmesh.generate import mesh_flat
from embmesh.model import Element
from embmesh.parser import parse_deck
from embmesh.volume import fiber_volume_rows, fiber_volume_rows_precise
from embmesh.writers import append_fibers_to_deck


def _single_box(length):
    nodes = {
        1: np.array([0.0, 0.0, 0.0]),
        2: np.array([length, 0.0, 0.0]),
        3: np.array([length, 1.0, 0.0]),
        4: np.array([0.0, 1.0, 0.0]),
        5: np.array([0.0, 0.0, 1.0]),
        6: np.array([length, 0.0, 1.0]),
        7: np.array([length, 1.0, 1.0]),
        8: np.array([0.0, 1.0, 1.0]),
    }
    return {1: Element(1, tuple(nodes), "C3D8")}, nodes


def _one_row_for_target_ratio(ratio):
    # With a length x 1 x 1 host, length/cbrt(volume) = length**(2/3).
    length = ratio ** 1.5
    elems, nodes = _single_box(length)
    boundary_eps = np.linalg.norm(np.array([length, 1.0, 1.0])) * 1e-6
    fibers = flat_disc_fibers(
        elems,
        nodes,
        diameter=1.0,
        thickness_axis="z",
        end_inset=-boundary_eps,
    )
    assert len(fibers) == 1
    return length, fibers[0]


@pytest.mark.parametrize(
    ("ratio", "expected_segments"),
    [(3.0, 3), (2.6, 3), (2.4, 2), (0.4, 1)],
    ids=["exact-multiple", "round-up", "round-down", "short-row"],
)
def test_flat_row_uses_rounded_target_count_and_equal_spacing(ratio, expected_segments):
    length, fiber = _one_row_for_target_ratio(ratio)
    segment_lengths = np.linalg.norm(np.diff(fiber.points, axis=0), axis=1)

    assert len(segment_lengths) == expected_segments
    assert np.allclose(segment_lengths, length / expected_segments)
    assert np.isclose(segment_lengths.sum(), length)
    assert fiber.curvature_data == {}


def test_target_length_uses_median_host_volume():
    nodes = {}
    elems = {}
    node_ids = {}
    x0 = 0.0
    for label, width in enumerate((1.0, 8.0, 27.0), start=1):
        x1 = x0 + width
        coords = (
            (x0, 0, 0), (x1, 0, 0), (x1, 1, 0), (x0, 1, 0),
            (x0, 0, 1), (x1, 0, 1), (x1, 1, 1), (x0, 1, 1),
        )
        ids = []
        for point in coords:
            if point not in node_ids:
                node_ids[point] = len(node_ids) + 1
                nodes[node_ids[point]] = np.asarray(point, float)
            ids.append(node_ids[point])
        ids = tuple(ids)
        elems[label] = Element(label, ids, "C3D8")
        x0 = x1

    boundary_eps = np.linalg.norm(np.array([36.0, 1.0, 1.0])) * 1e-6
    fibers = flat_disc_fibers(
        elems, nodes, diameter=1.0, thickness_axis="z", end_inset=-boundary_eps
    )

    # Volumes are 1, 8, 27, so cbrt(median) is 2 and the 36-unit row has 18 segments.
    assert len(fibers) == 1
    assert len(fibers[0].points) - 1 == 18
    assert np.allclose(np.diff(fibers[0].points, axis=0)[:, 0], 2.0)


def test_writer_and_volume_paths_accept_multi_segment_straight_fibers(tmp_path):
    elems, nodes = _single_box(1.0)
    plain = Fiber(1, np.array([[0.1, 0.5, 0.5], [0.9, 0.5, 0.5]]), 0, "t0")
    segmented = Fiber(
        1,
        np.array([[0.1, 0.5, 0.5], [0.3, 0.5, 0.5], [0.6, 0.5, 0.5], [0.9, 0.5, 0.5]]),
        0,
        "t0",
    )
    fast_plain = fiber_volume_rows(elems, nodes, [plain], 0.1, n_jobs=1)
    fast_segmented = fiber_volume_rows(elems, nodes, [segmented], 0.1, n_jobs=1)
    precise_plain = fiber_volume_rows_precise(elems, nodes, [plain], 0.1, n_jobs=1)
    precise_segmented = fiber_volume_rows_precise(elems, nodes, [segmented], 0.1, n_jobs=1)
    assert np.allclose(fast_plain, fast_segmented)
    assert np.allclose(precise_plain, precise_segmented)

    source = """*Part, name=P
*Node
1,0,0,0
2,1,0,0
*End Part
*Assembly
*Instance, name=P-1, part=P
*End Instance
*End Assembly
"""
    output = tmp_path / "segmented.inp"
    append_fibers_to_deck(source, output, [segmented], "truss", 0.1)
    deck = parse_deck(output)
    trusses = [e for part in deck.parts.values() for e in part.elements.values() if e.type == "T3D2"]
    assert len(trusses) == 3


def test_existing_flat_plate_fixture_writes_all_new_segments(tmp_path):
    fixture = Path("verification/evidence/work/t13_flat_a.inp")
    fibers, _ = mesh_flat(fixture, "PLATE-1", 0.25, tmp_path, preview=False)
    expected_elements = sum(len(f.points) - 1 for f in fibers)

    assert len(fibers) == 32
    assert expected_elements == 128  # formerly one element per row: 32
    deck = parse_deck(tmp_path / "output.inp")
    trusses = [e for part in deck.parts.values() for e in part.elements.values() if e.type == "T3D2"]
    assert len(trusses) == expected_elements
    assert "*Embedded Element" in (tmp_path / "output.inp").read_text()
