from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from .layup import layer_directions, orthogonal_directions

@dataclass
class Fiber:
    label: int
    points: np.ndarray
    layer: int
    direction: str

def flat_disc_fibers(nodes, diameter, thickness_axis=None, gap=0.0, reference=(1,0,0), end_inset=0.0):
    pts=np.asarray(list(nodes.values()),float); axis=np.linalg.svd(pts-pts.mean(0),full_matrices=False)[2][-1] if thickness_axis is None else np.asarray(thickness_axis,float); axis/=np.linalg.norm(axis)
    center=pts.mean(0); t0,t1=orthogonal_directions(reference,axis); u=pts@t0; v=pts@t1; w=pts@axis; pitch=diameter+gap; lo,hi=w.min(),w.max(); n=max(1,int(np.floor((hi-lo)/pitch))+1); fibers=[]; label=1
    for k in range(n):
      z=lo+diameter/2+gap/2+k*pitch
      if z>hi-diameter/2: continue
      j = k % 2; d = t0 if j == 0 else t1
      for _unused in (0,):
       perp=t1 if j==0 else t0; q=pts
       mn,mx=(q@perp).min(),(q@perp).max()
       for s in np.arange(mn+diameter/2,mx-diameter/2+pitch/2,pitch):
        lo2,hi2=(pts@d).min()-center@d+end_inset,(pts@d).max()-center@d-end_inset
        if hi2<=lo2: continue
        base=center+(z-center@axis)*axis+(s-center@perp)*perp
        fibers.append(Fiber(label,np.array([base+lo2*d,base+hi2*d]),k,"t0" if j==0 else "t90")); label+=1
    return fibers
