import numpy as np
from embmesh.model import Element, Instance
from embmesh.fibers import flat_disc_fibers
from embmesh.stacked import stacked_surface_fibers
from embmesh.geometry import point_in_hex
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
        samples=list(f.points)+[.5*(a+b) for a,b in zip(f.points[:-1],f.points[1:])]
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


def test_short_segment_merge():
    elems,nodes=plate(.04,nx=6,ny=6)
    # d/2 = .165 sits 1.67 mm from the first x-grid crossing at 1/6.
    fibers=stacked_surface_fibers(elems,nodes,.33)
    lengths=np.concatenate([np.linalg.norm(np.diff(f.points,axis=0),axis=1) for f in fibers])
    assert lengths.min()>.05/6
    inside_all(fibers,elems,nodes)
