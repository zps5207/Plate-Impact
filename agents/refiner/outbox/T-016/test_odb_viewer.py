"""Data and camera-bounds checks; no PyVista plotter is created."""
from collections import defaultdict
from pathlib import Path
import sys
import tempfile

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "verification" / "roar"))
from odb_viewer import ODBData  # noqa: E402


REAL_NPZ = ROOT / "agents" / "drafter" / "inbox" / "T-012" / "v500_viewer.npz"
REFERENCE_FACE_DEFS = {
    "C3D8R": ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
               (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)),
    "C3D6R": ((0, 1, 2), (3, 5, 4), (0, 1, 4, 3),
               (1, 2, 5, 4), (2, 0, 3, 5)),
}


def load_data(path):
    data = ODBData(str(path))
    data.raw.close()  # np.load keeps an open ZIP handle on Windows.
    return data


@pytest.fixture
def tmp_path():
    # Some Windows installations deny pytest's global temporary directory.
    with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
        yield Path(directory)


def cells(flat):
    """Parse variable-length VTK face cells without depending on PyVista."""
    result = []
    i = 0
    while i < len(flat):
        size = int(flat[i])
        assert size in (3, 4)
        result.append(tuple(map(int, flat[i + 1:i + 1 + size])))
        i += size + 1
    assert i == len(flat)
    return result


def two_hexes():
    coords = np.array([[x, y, z] for z in (0, 1) for y in (0, 1)
                       for x in (0, 1, 2)], dtype=np.float32)
    def node(x, y, z):
        return z * 6 + y * 3 + x
    conn = []
    for x in (0, 1):
        conn.append([node(x, 0, 0), node(x + 1, 0, 0),
                     node(x + 1, 1, 0), node(x, 1, 0),
                     node(x, 0, 1), node(x + 1, 0, 1),
                     node(x + 1, 1, 1), node(x, 1, 1)])
    return coords, np.array(conn, dtype=np.int32)


def save_host(tmp_path, coords, connections, status, **extra):
    status = np.asarray(status, dtype=np.uint8)
    payload = dict(times=np.arange(len(status), dtype=float),
                   host_coords0=np.asarray(coords, dtype=np.float32),
                   host_pos=np.repeat(np.asarray(coords, dtype=np.float32)[None],
                                      len(status), axis=0),
                   host_status=status)
    payload.update(connections)
    payload.update(extra)
    path = tmp_path / "fixture.npz"
    np.savez(path, **payload)
    return path


def canonical(face):
    return frozenset(face)


def reference_faces(connections, status):
    """Straightforward exporter-order face incidence and alive-neighbor rule."""
    occurrence = defaultdict(list)
    offset = 0
    for kind in sorted(connections):
        for local_idx, element in enumerate(connections[kind]):
            for face in REFERENCE_FACE_DEFS[kind]:
                nodes = frozenset(int(element[i]) for i in face)
                occurrence[nodes].append(offset + local_idx)
        offset += len(connections[kind])
    return {face for face, owners in occurrence.items()
            if sum(status[owner] == 1 for owner in owners) == 1}


def test_two_hex_face_ownership_and_deletion(tmp_path):
    coords, conn = two_hexes()
    states = np.array([[1, 1], [1, 0], [0, 1], [0, 0]], dtype=np.uint8)
    data = load_data(save_host(tmp_path, coords, {"host_conn_C3D8R": conn}, states))
    shared = frozenset((1, 4, 7, 10))
    assert data.total_host_elements == 2
    assert data.n_quads == 11
    shared_idx = [i for i, row in enumerate(data.quad_pv_cells)
                  if canonical(row[1:]) == shared]
    assert len(shared_idx) == 1
    assert {int(data.quad_e1[shared_idx[0]]), int(data.quad_e2_safe[shared_idx[0]])} == {0, 1}
    expected = [10, 6, 6, 0]
    for frame, count in enumerate(expected):
        visible = {canonical(face) for face in cells(data.get_host_faces(frame))}
        assert len(visible) == count
        assert visible == reference_faces({"C3D8R": conn}, states[frame])
        assert (shared in visible) == (frame in (1, 2))


def test_sorted_element_types_match_status_columns(tmp_path):
    # The NPZ stores hex first deliberately; exporter status columns put wedge first.
    coords, hexes = two_hexes()
    wedge_coords = np.array([[10, 0, 0], [11, 0, 0], [10, 1, 0],
                             [10, 0, 1], [11, 0, 1], [10, 1, 1]], dtype=np.float32)
    coords = np.vstack((coords, wedge_coords))
    wedge = np.arange(12, 18, dtype=np.int32)[None]
    conn = {"host_conn_C3D8R": hexes[:1], "host_conn_C3D6R": wedge}
    status = np.array([[1, 1], [0, 1], [1, 0]], dtype=np.uint8)
    data = load_data(save_host(tmp_path, coords, conn, status))
    all_cells = [cells(data.get_host_faces(i)) for i in range(3)]
    assert [len(c) for c in all_cells] == [11, 6, 5]
    assert [sum(len(face) == 3 for face in c) for c in all_cells] == [2, 0, 2]
    assert all(set(face).isdisjoint(set(wedge[0])) for face in all_cells[1])
    assert all(set(face).isdisjoint(set(hexes[0])) for face in all_cells[2])


def test_wedge_triangles_and_quads(tmp_path):
    coords = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0],
                       [0, 0, 1], [1, 0, 1], [0, 1, 1]], dtype=np.float32)
    conn = np.arange(6, dtype=np.int32)[None]
    data = load_data(save_host(tmp_path, coords, {"host_conn_C3D6R": conn}, [[1], [0]]))
    visible = cells(data.get_host_faces(0))
    assert sorted(map(len, visible)) == [3, 3, 4, 4, 4]
    assert {canonical(face) for face in visible if len(face) == 3} == {
        frozenset((0, 1, 2)), frozenset((3, 4, 5))}
    assert all(len(set(face)) == len(face) for face in visible)
    assert cells(data.get_host_faces(1)) == []


def test_animation_bounds_include_ball_fiber_and_intermediate_host(tmp_path):
    coords, conn = two_hexes()
    host_pos = np.repeat(coords[None], 3, axis=0)
    host_pos[1, 0, 0] = -12
    ball_pos = np.array([[[0, 0, 0]], [[15, 0, 0]], [[0, 0, 0]]], dtype=np.float32)
    fiber_pos = np.array([[[0, 0, 0], [0, 0, 0]],
                          [[0, -8, 0], [0, 0, 0]],
                          [[0, 0, 0], [0, 0, 0]]], dtype=np.float32)
    path = save_host(tmp_path, coords, {"host_conn_C3D8R": conn[:1]},
                     [[1], [1], [1]], host_pos=host_pos,
                     ball_coords0=ball_pos[0], ball_pos=ball_pos,
                     fiber_coords0=fiber_pos[0], fiber_pos=fiber_pos,
                     fiber_conn_T3D2=np.array([[0, 1]], dtype=np.int32))
    data = load_data(path)
    for positions in (ball_pos, fiber_pos, host_pos):
        assert np.all(positions >= data.bounds_min)
        assert np.all(positions <= data.bounds_max)


@pytest.mark.skipif(not REAL_NPZ.is_file(), reason="v500_viewer.npz is absent")
def test_real_v500_status_and_reference_faces():
    data = load_data(REAL_NPZ)
    status = data.host_status
    assert status.shape[1] == 24000
    assert int(status[0].sum()) == 24000
    assert int(status[-1].sum()) == 22316
    assert np.all(status[1:] <= status[:-1])
    with np.load(REAL_NPZ) as raw:
        connections = {key.removeprefix("host_conn_"): raw[key]
                       for key in raw.files if key.startswith("host_conn_")}
    for frame in sorted({0, data.n_frames // 2, data.n_frames - 1}):
        drawn = {canonical(face) for face in cells(data.get_host_faces(frame))}
        expected = reference_faces(connections, status[frame])
        assert drawn == expected
