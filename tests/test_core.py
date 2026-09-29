import numpy as np
from embmesh.parser import parse_deck
from embmesh.selection import select_elements
from embmesh.errors import HexOnlyError
from embmesh.geometry import inverse_hex, point_in_hex, clip_segment_hex, hex_volume, swept_cylinder_hex_volume
from embmesh.layup import layer_directions
from embmesh.vumat import update_tension_only
from embmesh.fibers import flat_disc_fibers
from embmesh.volume import fiber_volume_rows, fiber_volume_rows_precise
from embmesh.config import load_config

DECK='''*Part, name=P\n*Node\n1,0,0,0\n2,1,0,0\n3,1,1,0\n4,0,1,0\n5,0,0,1\n6,1,0,1\n7,1,1,1\n8,0,1,1\n*Element, type=C3D8, elset=H\n1,1,2,3,4,5,6,7,8\n*Nset, nset=N, generate\n1,8,1\n*End Part\n*Assembly\n*Instance, name=I, part=P\n0,0,0\n*End Instance\n*End Assembly\n'''

def test_parser_and_transform():
 d=parse_deck(DECK); assert d.parts['P'].elements[1].type=='C3D8'; assert np.allclose(d.instance_nodes('I')[1],[0,0,0])

def test_hex_and_geometry():
 d=parse_deck(DECK); es,n=select_elements(d,'I'); p=np.array([n[i] for i in es[1].connectivity]); assert np.isclose(hex_volume(p),1); assert point_in_hex([.5,.5,.5],p); assert inverse_hex([.5,.5,.5],p) is not None; assert abs(clip_segment_hex([-.5,.5,.5],[1.5,.5,.5],p)-1)<1e-6

def test_bad_element():
 d=parse_deck(DECK.replace('C3D8','C3D4')); 
 try: select_elements(d,'I'); assert False
 except HexOnlyError as e: assert 'C3D4' in str(e)

def test_layup_and_vumat():
 ds=layer_directions(4); assert np.allclose(ds[0]@ds[1],0); assert update_tension_only(.01,0,100,2)==(1.,False); assert update_tension_only(-.1,1,100,2)==(0.,False); assert update_tension_only(.02,1,100,2)[1]
 s,dead=update_tension_only(.005,0,100,2); s,dead=update_tension_only(-.01,s,100,2); assert s==0 and not dead

def test_flat_fibers_and_volume():
 d=parse_deck(DECK); fs=flat_disc_fibers(d.instance_nodes('I'),.25,gap=0); assert fs
 rows=fiber_volume_rows(d.parts['P'].elements,d.instance_nodes('I'),fs,.25); assert rows[0][2]>=0 and rows[0][3]<=1

def test_config_validation(tmp_path):
 p=tmp_path/'c.json'; p.write_text('{"fiber_diameter": 0.2, "gap": 0, "fiber_type": "beam"}'); assert load_config(p)['fiber_type']=='beam'

_UNIT_CUBE = np.array([[0,0,0],[1,0,0],[1,1,0],[0,1,0],[0,0,1],[1,0,1],[1,1,1],[0,1,1]], float)

def test_swept_cylinder_volume_fully_inside_matches_length_times_area():
 a,b=np.array([.5,.5,0.]),np.array([.5,.5,1.]); r=.05
 precise=swept_cylinder_hex_volume(a,b,r,_UNIT_CUBE,n_along=9)
 fast=clip_segment_hex(a,b,_UNIT_CUBE)*np.pi*r**2
 assert abs(precise-fast)<1e-9

def test_swept_cylinder_volume_splits_correctly_across_a_shared_face():
 hostA=_UNIT_CUBE
 hostB=np.array([[-1,0,0],[0,0,0],[0,1,0],[-1,1,0],[-1,0,1],[0,0,1],[0,1,1],[-1,1,1]],float)
 a,b=np.array([0.,.5,0.]),np.array([0.,.5,1.]); r=.2  # centerline exactly on the shared x=0 face
 VA=swept_cylinder_hex_volume(a,b,r,hostA,n_along=9); VB=swept_cylinder_hex_volume(a,b,r,hostB,n_along=9)
 true=np.pi*r**2*1.0
 assert abs(VA-VB)<1e-9         # symmetric split
 assert abs(VA+VB-true)<1e-6    # sums to the true cylinder volume, no double count

def test_swept_cylinder_volume_does_not_drop_true_exterior_boundary():
 # fiber endpoints coincide with the host's own outer faces (z=0, z=1) -- these
 # are not a shared face with a neighbor, so the tie-break must not shift them
 # outward and lose real volume (regression for a bug found during development).
 a,b=np.array([.5,.5,0.]),np.array([.5,.5,1.]); r=.05
 precise=swept_cylinder_hex_volume(a,b,r,_UNIT_CUBE,n_along=9)
 assert abs(precise-np.pi*r**2*1.0)<1e-9

def test_fiber_volume_rows_precise_runs_and_is_close_to_fast_for_a_centered_fiber():
 d=parse_deck(DECK); nodes=d.instance_nodes('I')
 fs=flat_disc_fibers(nodes,.1,gap=0.4)  # sparse, well clear of host faces
 fast=fiber_volume_rows(d.parts['P'].elements,nodes,fs,.1)
 precise=fiber_volume_rows_precise(d.parts['P'].elements,nodes,fs,.1)
 assert abs(fast[0][2]-precise[0][2])/fast[0][2]<1e-3
