from pathlib import Path
from embmesh.parser import parse_deck
from embmesh.fibers import Fiber
from embmesh.writers import append_fibers_to_deck

def test_truss_beam_decks_roundtrip(tmp_path):
 text='*Part, name=P\n*Node\n1,0,0,0\n2,1,0,0\n*End Part\n*Assembly, name=A\n*Instance, name=P-1, part=P\n*End Instance\n*End Assembly\n'
 f=[Fiber(1,__import__('numpy').array([[0.,0,0],[1.,0,0]]),0,'t0')]
 for typ,key in [('truss','*Solid Section'),('beam','*Beam Section')]:
  p=tmp_path/(typ+'.inp'); append_fibers_to_deck(text,p,f,typ,.2); out=p.read_text(); assert key in out; assert '*Element, type='+('T3D2' if typ=='truss' else 'B31') in out; assert 'material=Fiber' in out; assert '*Material, name=EMBMESH_FIBER' not in out; assert parse_deck(p).parts
