from __future__ import annotations
import numpy as np
from .geometry import clip_segment_hex, hex_volume

def host_volume_rows(elements, nodes, fibers):
    rows=[]
    for label,e in elements.items():
        hp=np.array([nodes[i] for i in e.connectivity[:8]],float)
        total=t0=t90=0.0
        for f in fibers:
            L=clip_segment_hex(f.points[0],f.points[-1],hp)
            total+=L
            if f.direction=="t0": t0+=L
            else: t90+=L
        area=getattr(fibers[0],"diameter",0.0) # optional metadata
        rows.append((label,hex_volume(hp),total*area if area else total,t0,t90))
    return rows

def fiber_volume_rows(elements,nodes,fibers,diameter):
    area=np.pi*diameter**2/4; out=[]
    for label,e in elements.items():
        hp=np.array([nodes[i] for i in e.connectivity[:8]],float); host=hex_volume(hp); l0=l90=0.
        hmin,hmax=hp.min(0),hp.max(0)
        for f in fibers:
            fmin,fmax=f.points.min(0),f.points.max(0)
            if np.any(fmax < hmin) or np.any(fmin > hmax): continue
            L=clip_segment_hex(f.points[0],f.points[-1],hp)
            if f.direction=="t0": l0+=L
            else: l90+=L
        fv=(l0+l90)*area; out.append((label,host,fv,fv/host if host else 0.,l0,l90))
    return out
