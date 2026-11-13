from __future__ import annotations
import numpy as np

def orthogonal_directions(reference=(1,0,0), normal=(0,0,1)):
    # BUG-004 fix: the old fallback re-tried the same fixed (1,0,0) vector, which is
    # itself degenerate whenever `normal` is (close to) (1,0,0) -- e.g. a plate whose
    # thickness axis is X -- producing a zero vector and propagating NaN/inf downstream.
    # Pick whichever global axis has the smallest component along `normal` instead,
    # which is never parallel to it.
    r=np.asarray(reference,float); n=np.asarray(normal,float); n/=np.linalg.norm(n)
    t0=r-n*np.dot(r,n)
    if np.linalg.norm(t0)<1e-8:
        alt = np.eye(3)[int(np.argmin(np.abs(n)))]
        t0 = alt-n*np.dot(alt,n)
    t0/=np.linalg.norm(t0); return t0, np.cross(n,t0)/np.linalg.norm(np.cross(n,t0))

def layer_directions(count, reference=(1,0,0), normal=(0,0,1)):
    a,b=orthogonal_directions(reference,normal); return [a if i%2==0 else b for i in range(count)]

