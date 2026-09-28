from __future__ import annotations
import numpy as np

def orthogonal_directions(reference=(1,0,0), normal=(0,0,1)):
    r=np.asarray(reference,float); n=np.asarray(normal,float); n/=np.linalg.norm(n)
    t0=r-n*np.dot(r,n)
    if np.linalg.norm(t0)<1e-10: t0=np.array([1.,0,0])-n*n[0]
    t0/=np.linalg.norm(t0); return t0, np.cross(n,t0)/np.linalg.norm(np.cross(n,t0))

def layer_directions(count, reference=(1,0,0), normal=(0,0,1)):
    a,b=orthogonal_directions(reference,normal); return [a if i%2==0 else b for i in range(count)]

