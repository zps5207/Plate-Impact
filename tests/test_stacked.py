import importlib.util
from pathlib import Path
import sys
import numpy as np
import pytest

repo_root = Path(__file__).resolve().parents[5]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))
import embmesh

_stacked_path = Path(__file__).resolve().parent.parent / "embmesh" / "stacked.py"
if _stacked_path.exists():
    _spec = importlib.util.spec_from_file_location("embmesh.stacked", str(_stacked_path))
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    sys.modules["embmesh.stacked"] = _mod

from embmesh.model import Element, Instance
from embmesh.fibers import flat_disc_fibers
from embmesh.stacked import stacked_surface_fibers, oriented_hex_faces, _SIGNS
from embmesh.geometry import point_in_hex, hex_volume
from embmesh.writers import append_fibers_to_deck


def plate(curvature=0., nx=5, ny=5, nz=2):
    nodes={}; elems={}
    def label(i,j,k):return 1+k*(nx+1)*(ny+1)+j*(nx+1)+i
    for k in range(nz+1):
        for j in range(ny+1):
            for i in range(nx+1):
                x=i/nx; y=j/ny
                nodes[label(i,j,k)]=np.array([x,y,curvature*(x*x+y*y)+k/nz])
    eid=0
    for k in range(nz):
        for j in range(ny):
            for i in range(nx):
                eid+=1
                ids=(label(i,j,k),label(i,j+1,k),label(i+1,j+1,k),label(i+1,j,k),
                     label(i,j,k+1),label(i,j+1,k+1),label(i+1,j+1,k+1),label(i+1,j,k+1))
                elems[eid]=Element(eid,ids,'C3D8R')
    return elems,nodes


def inside_all(fibers,elems,nodes):
    hosts=[np.array([nodes[n] for n in e.connectivity]) for e in elems.values()]
    for f in fibers:
        samples=list(f.points)+[(1-t)*a+t*b for a,b in zip(f.points[:-1],f.points[1:])
                                for t in (1/6,2/6,3/6,4/6,5/6)]
        for p in samples:
            assert any(np.all(p>=h.min(0)-1e-9) and np.all(p<=h.max(0)+1e-9) and point_in_hex(p,h) for h in hosts)


def test_flat_identical():
    elems,nodes=plate()
    a=flat_disc_fibers(elems,nodes,.25)
    b,meta=stacked_surface_fibers(elems,nodes,.25,return_meta=True)
    assert len(a)==len(b) and meta['layer_count']==4
    for x,y in zip(a,b):
        assert (x.label,x.layer,x.direction)==(y.label,y.layer,y.direction)
        np.testing.assert_array_equal(x.points,y.points)


def test_curved_containment_and_overlap():
    elems,nodes=plate(.08)
    fibers,meta=stacked_surface_fibers(elems,nodes,.25,return_meta=True)
    assert meta['layer_count']==4
    assert np.isclose(meta['max_neighbour_overlap_fraction'],1-np.cos(np.deg2rad(meta['theta_max_deg'])))
    inside_all(fibers,elems,nodes)


def test_even_chords_on_curved_plate():
    elems,nodes=plate(.08)
    fibers,meta=stacked_surface_fibers(elems,nodes,.25,return_meta=True)
    target=meta['target_segment_length_m']
    for fiber in fibers:
        seg=np.linalg.norm(np.diff(fiber.points,axis=0),axis=1)
        assert np.ptp(seg)/np.median(seg)<1e-9
        if fiber.curvature_data['geometric_path_length_m']>=target/2:
            assert seg.min()>=target/2
    assert meta['per_fiber_segment_spread_max_relative']<1e-9


def test_world_frame_and_writer(tmp_path):
    elems,nodes=plate(.08)
    inst=Instance('Plate-1','Plate',translation=np.array([2.,3.,4.]),
                  rotation_axis=np.array([1.,0.,0.]),rotation_angle=90.)
    world={i:inst.transform(p) for i,p in nodes.items()}
    fibers=stacked_surface_fibers(elems,world,.25)
    inside_all(fibers,elems,world)
    source='*Part, name=Plate\n*End Part\n*Assembly, name=Assembly\n*Instance, name=Plate-1, part=Plate\n2, 3, 4\n0, 0, 0, 1, 0, 0, 90\n*End Instance\n*End Assembly\n'
    output=tmp_path/'deck.inp'
    append_fibers_to_deck(source,output,fibers,diameter=.25,host_instance='Plate-1',host_labels=list(elems))
    text=output.read_text()
    assert '*Instance, name=EMBFIB-1, part=EMBFIB\n*End Instance' in text


def test_near_grid_line_has_even_segments():
    elems,nodes=plate(.04,nx=6,ny=6)
    # d/2 = .165 sits 1.67 mm from the first x-grid crossing at 1/6.
    fibers=stacked_surface_fibers(elems,nodes,.33)
    lengths=np.concatenate([np.linalg.norm(np.diff(f.points,axis=0),axis=1) for f in fibers])
    assert lengths.min()>.05/6
    assert all(np.ptp(v:=np.linalg.norm(np.diff(f.points,axis=0),axis=1))/np.median(v)<1e-9 for f in fibers)
    inside_all(fibers,elems,nodes)


def test_segment_statistics_with_short_runs_and_json_serializable():
    import json
    from embmesh.stacked import _segment_statistics
    from embmesh.fibers import Fiber
    f_short = Fiber(1, np.array([[0., 0., 0.], [0.05, 0., 0.]]), 0, 't0')
    f_normal = Fiber(2, np.array([[0., 0., 0.], [0.5, 0., 0.], [1.0, 0., 0.]]), 0, 't0')
    target = 0.5
    short_runs = sum(np.linalg.norm(np.diff(f.points, axis=0), axis=1).sum() < target/2 for f in [f_short, f_normal])
    stats = _segment_statistics([f_short, f_normal], target, short_runs)
    assert isinstance(stats['short_fiber_run_count'], int)
    assert not isinstance(stats['short_fiber_run_count'], np.generic)
    assert stats['short_fiber_run_count'] == 1
    # Check JSON serializability
    serialized = json.dumps(stats)
    assert '"short_fiber_run_count": 1' in serialized


def test_oriented_hex_faces_all_axes_and_signs():
    # 1. Local zeta aligns with world +Z
    bot_p, top_p, bot_id, top_id = oriented_hex_faces(_SIGNS, np.array([0., 0., 1.]))
    assert bot_id == (4, 5, 6, 7) and top_id == (0, 1, 2, 3)

    # 2. Local zeta aligns with world -Z
    bot_p, top_p, bot_id, top_id = oriented_hex_faces(_SIGNS, np.array([0., 0., -1.]))
    assert bot_id == (0, 1, 2, 3) and top_id == (4, 5, 6, 7)

    # 3. Local eta aligns with world +Z
    H_eta = _SIGNS[:, [0, 2, 1]]
    bot_p, top_p, bot_id, top_id = oriented_hex_faces(H_eta, np.array([0., 0., 1.]))
    assert bot_id == (4, 7, 3, 0) and top_id == (5, 6, 2, 1)

    # 4. Local eta aligns with world -Z
    bot_p, top_p, bot_id, top_id = oriented_hex_faces(H_eta, np.array([0., 0., -1.]))
    assert bot_id == (5, 6, 2, 1) and top_id == (4, 7, 3, 0)

    # 5. Local xi aligns with world +Z
    H_xi = _SIGNS[:, [2, 1, 0]]
    bot_p, top_p, bot_id, top_id = oriented_hex_faces(H_xi, np.array([0., 0., 1.]))
    assert bot_id == (4, 0, 1, 5) and top_id == (7, 3, 2, 6)

    # 6. Local xi aligns with world -Z
    bot_p, top_p, bot_id, top_id = oriented_hex_faces(H_xi, np.array([0., 0., -1.]))
    assert bot_id == (7, 3, 2, 6) and top_id == (4, 0, 1, 5)


def test_scrambled_hex_node_ordering_identical_output(tmp_path):
    elems, nodes = plate(0.08)
    fibers_orig, meta_orig = stacked_surface_fibers(elems, nodes, 0.25, return_meta=True)

    # Positive-volume node order permutations that swap local axes
    perm_rot_z = [int(np.where(np.all(_SIGNS == [s[1], -s[0], s[2]], axis=1))[0][0]) for s in _SIGNS]
    perm_cyc1 = [int(np.where(np.all(_SIGNS == [s[2], s[0], s[1]], axis=1))[0][0]) for s in _SIGNS]
    perm_cyc2 = [int(np.where(np.all(_SIGNS == [s[1], s[2], s[0]], axis=1))[0][0]) for s in _SIGNS]
    perms = [perm_rot_z, perm_cyc1, perm_cyc2]

    rng = np.random.default_rng(42)
    scrambled_elems = {}
    for eid, elem in elems.items():
        p = perms[rng.integers(0, len(perms))]
        new_conn = tuple(elem.connectivity[i] for i in p)
        assert hex_volume([nodes[n] for n in new_conn]) > 0
        scrambled_elems[eid] = Element(eid, new_conn, elem.type)

    fibers_scrambled, meta_scrambled = stacked_surface_fibers(scrambled_elems, nodes, 0.25, return_meta=True)
    assert len(fibers_orig) == len(fibers_scrambled)
    for f1, f2 in zip(fibers_orig, fibers_scrambled):
        assert (f1.label, f1.layer, f1.direction) == (f2.label, f2.layer, f2.direction)
        np.testing.assert_allclose(f1.points, f2.points, atol=1e-12)

    # Check written deck is identical
    source = '*Part, name=Plate\n*End Part\n*Assembly, name=Assembly\n*Instance, name=Plate-1, part=Plate\n*End Instance\n*End Assembly\n'
    out1 = tmp_path / 'deck1.inp'
    out2 = tmp_path / 'deck2.inp'
    append_fibers_to_deck(source, out1, fibers_orig, diameter=0.25, host_instance='Plate-1', host_labels=list(elems))
    append_fibers_to_deck(source, out2, fibers_scrambled, diameter=0.25, host_instance='Plate-1', host_labels=list(scrambled_elems))
    assert out1.read_text() == out2.read_text()


def test_non_congruent_plate_raises_mismatch_error():
    elems, nodes = plate(0.08)
    # Genuinely bump one bottom node by more than the tolerance
    nodes[1] = nodes[1] + np.array([0.1, 0., 0.])
    with pytest.raises(ValueError, match='face translation mismatch'):
        stacked_surface_fibers(elems, nodes, 0.25)
