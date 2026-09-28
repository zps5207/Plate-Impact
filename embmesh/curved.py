from __future__ import annotations
import numpy as np

def triangulate_surface(points, faces=None):
    """Return triangle vertex indices; fan triangulation is deterministic."""
    p=np.asarray(points,float)
    if faces is None:
        if len(p)<3: return np.empty((0,3),dtype=int)
        return np.array([[0,i,i+1] for i in range(1,len(p)-1)],int)
    out=[]
    for f in faces:
        f=list(f)
        for i in range(1,len(f)-1): out.append((f[0],f[i],f[i+1]))
    return np.asarray(out,int)

def smooth_normals(points, triangles, inward=False):
    p=np.asarray(points,float); n=np.zeros_like(p)
    for a,b,c in np.asarray(triangles,int):
        q=np.cross(p[b]-p[a],p[c]-p[a]); q/=max(np.linalg.norm(q),1e-15)
        n[[a,b,c]]+=q
    n/=np.maximum(np.linalg.norm(n,axis=1,keepdims=True),1e-15)
    return -n if inward else n

def director(front_normal, back_normal, tolerance=1e-10):
    s=np.asarray(front_normal,float)+np.asarray(back_normal,float); m=np.linalg.norm(s)
    if m<tolerance: raise ValueError("front/back normals are opposed; director is undefined")
    return s/m

def rk4_streamline(x, vector_field, step, count):
    x=np.asarray(x,float); out=[x.copy()]
    for _ in range(count):
        k1=np.asarray(vector_field(x),float); k1/=max(np.linalg.norm(k1),1e-15)
        k2=np.asarray(vector_field(x+step*k1/2),float); k2/=max(np.linalg.norm(k2),1e-15)
        k3=np.asarray(vector_field(x+step*k2/2),float); k3/=max(np.linalg.norm(k3),1e-15)
        k4=np.asarray(vector_field(x+step*k3),float); k4/=max(np.linalg.norm(k4),1e-15)
        x=x+step*(k1+2*k2+2*k3+k4)/6; out.append(x.copy())
    return np.asarray(out)

def radial_director(points, center=(0,0,0)):
    p=np.asarray(points,float)-np.asarray(center,float); n=np.linalg.norm(p,axis=1); return p/np.maximum(n[:,None],1e-15)

def shell_layers(radius_front,radius_back,pitch):
    if radius_back<radius_front: radius_front,radius_back=radius_back,radius_front
    count=max(1,int(np.floor((radius_back-radius_front)/pitch))+1)
    radii=radius_front+(np.arange(count)+.5)*pitch
    return radii[radii<=radius_back+1e-12]

def spacing_stats(points):
    p=np.asarray(points,float)
    if len(p)<2:return {"min":0.,"max":0.,"mean":0.}
    d=np.linalg.norm(np.diff(p,axis=0),axis=1); return {"min":float(d.min()),"max":float(d.max()),"mean":float(d.mean())}
