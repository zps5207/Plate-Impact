import numpy as np
from embmesh.curved import radial_director, shell_layers
from embmesh.curved_layup import concentric_shell_fibers

def test_curved_director_and_layers():
 p=np.array([[2.,0,0],[0,2.,0],[-2,0,0]]); assert np.allclose(radial_director(p),p/2)
 fs,rs=concentric_shell_fibers(2,3,1,.2); assert len(rs)>0; assert all(abs(np.linalg.norm(f.points[0])-rs[f.layer])<1e-12 for f in fs)
