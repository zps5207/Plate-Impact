from __future__ import annotations
import numpy as np
from .curved import radial_director, shell_layers, spacing_stats
from .fibers import Fiber

def concentric_shell_fibers(radius_front, radius_back, axial_length, diameter, gap=0., count=32):
    pitch=diameter+gap; radii=shell_layers(radius_front,radius_back,pitch); fibers=[]; label=1
    angles=np.arange(count)*2*np.pi/count
    for k,r in enumerate(radii):
      for th in angles:
        p0=np.array([r*np.cos(th),r*np.sin(th),0.]); p1=np.array([r*np.cos(th),r*np.sin(th),axial_length])
        fibers.append(Fiber(label,np.array([p0,p1]),k,"t0" if k%2==0 else "t90")); label+=1
    return fibers, radii

