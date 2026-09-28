import numpy as np
from embmesh.parser import parse_deck
from embmesh.selection import select_elements
from embmesh.errors import HexOnlyError
from embmesh.geometry import inverse_hex, point_in_hex, clip_segment_hex, hex_volume
from embmesh.layup import layer_directions
from embmesh.vumat import update_tension_only
from embmesh.fibers import flat_disc_fibers
from embmesh.volume import fiber_volume_rows
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
