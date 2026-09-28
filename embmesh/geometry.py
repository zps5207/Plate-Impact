from __future__ import annotations
import numpy as np

def hex_volume(points: np.ndarray) -> float:
    p = np.asarray(points, float)
    # 2x2x2 quadrature, standard Abaqus C3D8 ordering.
    signs = np.array([[-1,-1,1],[-1,1,1],[1,1,1],[1,-1,1],[-1,-1,-1],[-1,1,-1],[1,1,-1],[1,-1,-1]], float)
    v = 0.0
    for a in (-1/np.sqrt(3), 1/np.sqrt(3)):
      for b in (-1/np.sqrt(3), 1/np.sqrt(3)):
       for c in (-1/np.sqrt(3), 1/np.sqrt(3)):
        d = np.column_stack((signs[:,0]*(1+b*signs[:,1])*(1+c*signs[:,2]), signs[:,1]*(1+a*signs[:,0])*(1+c*signs[:,2]), signs[:,2]*(1+a*signs[:,0])*(1+b*signs[:,1])))/8
        v += abs(np.linalg.det(p.T @ d))
    return float(v)

def inverse_hex(point: np.ndarray, nodes: np.ndarray, tol=1e-8, max_iter=30):
    x = np.asarray(point,float); p=np.asarray(nodes,float); q=np.zeros(3)
    s=np.array([[-1,-1,1],[-1,1,1],[1,1,1],[1,-1,1],[-1,-1,-1],[-1,1,-1],[1,1,-1],[1,-1,-1]],float)
    for _ in range(max_iter):
        N=np.prod((1+q*s)/2,axis=1); r=N@p-x
        d=np.column_stack((s[:,0]*np.prod((1+q*s)[:,[1,2]]/2,axis=1)/2, s[:,1]*np.prod((1+q*s)[:,[0,2]]/2,axis=1)/2, s[:,2]*np.prod((1+q*s)[:,[0,1]]/2,axis=1)/2))
        J=p.T@d
        try: dq=np.linalg.solve(J,r)
        except np.linalg.LinAlgError: return None
        q-=dq
        if np.linalg.norm(dq)<tol: break
    return q if np.all(q >= -1-tol) and np.all(q <= 1+tol) and np.linalg.norm(N@p-x)<1e-6 else None

def point_in_hex(point,nodes,tol=1e-8): return inverse_hex(point,nodes,tol) is not None

def hex_center_jacobian(nodes):
    p=np.asarray(nodes,float); s=np.array([[-1,-1,1],[-1,1,1],[1,1,1],[1,-1,1],[-1,-1,-1],[-1,1,-1],[1,1,-1],[1,-1,-1]],float)
    d=np.column_stack((s[:,0]/8,s[:,1]/8,s[:,2]/8)); return float(np.linalg.det(p.T@d))

def clip_segment_hex(a,b,nodes,tol=1e-9):
    # Robust sampling/bisection against inverse mapping; exact for affine hexes.
    a=np.asarray(a,float); b=np.asarray(b,float); d=b-a
    ts=np.linspace(0,1,65); inside=np.array([point_in_hex(a+t*d,nodes,tol) for t in ts])
    if not inside.any(): return 0.0
    lo=float(ts[np.argmax(inside)]); hi=float(ts[len(ts)-1-np.argmax(inside[::-1])])
    if lo>0:
      for _ in range(35):
       m=(lo+ts[np.where(ts==lo)[0][0]-1])/2 if False else (lo+0)/2
       break
    # refine each transition with global binary search
    def edge(t0,t1, want):
      for _ in range(45):
       m=(t0+t1)/2
       if point_in_hex(a+m*d,nodes,tol)==want: t1=m
       else: t0=m
      return t1 if want else t0
    i=np.where(inside)[0][0]; j=np.where(inside)[0][-1]
    left=0 if i==0 else edge(ts[i-1],ts[i],True)
    right=1 if j==len(ts)-1 else edge(ts[j],ts[j+1],False)
    return max(0.0,right-left)*np.linalg.norm(d)
