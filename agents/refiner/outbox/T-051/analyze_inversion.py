"""Analyze ball hex corner-Jacobian inversion in local viewer NPZ files.

Usage: python analyze_inversion.py [project-root] [output-json]
Only reads viewer NPZ and neighboring extract JSON files. Coordinates are SI.
The output is geometric: these inputs have no ball element STATUS or contact forces.
"""
import glob
import json
import os
import sys

import numpy as np

NBR = {0:(1,3,4), 1:(2,0,5), 2:(3,1,6), 3:(0,2,7),
       4:(7,5,0), 5:(4,6,1), 6:(5,7,2), 7:(6,4,3)}
EDGES = [(0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),
         (0,4),(1,5),(2,6),(3,7)]


def min_sj(p):
    """Minimum of eight corner scaled Jacobians for C3D8R node order."""
    out = np.full(len(p), np.inf)
    for v, (a,b,c) in NBR.items():
        e1,e2,e3 = p[:,a]-p[:,v],p[:,b]-p[:,v],p[:,c]-p[:,v]
        det = np.einsum('ij,ij->i',np.cross(e1,e2),e3)
        den = np.linalg.norm(e1,axis=1)*np.linalg.norm(e2,axis=1)*np.linalg.norm(e3,axis=1)
        out = np.minimum(out,det/np.maximum(den,1e-30))
    return out


def analyze(path):
    d = np.load(path)
    xyz = d['ball_coords0'].astype(np.float64)
    conn = d['ball_conn_C3D8R']
    wedge = d['ball_conn_C3D6R'] if 'ball_conn_C3D6R' in d else np.empty((0,6),dtype=np.int32)
    pos = d['ball_pos']
    t = d['times']*1e6
    ctr = xyz[conn].mean(axis=1)
    center = np.array([0.,0.,0.011])
    radius = 0.009525
    r = np.linalg.norm(ctr-center,axis=1)
    edges = np.stack([np.linalg.norm(xyz[conn[:,a]]-xyz[conn[:,b]],axis=1)
                      for a,b in EDGES],axis=1)
    initial_sj = min_sj(xyz[conn])
    nodal_r = np.linalg.norm(xyz-center,axis=1)
    surface = np.abs(nodal_r-radius)<3e-5
    nose = (xyz[:,2]<0.0025)&surface
    on_plane = (np.abs(xyz[:,0])<2e-6)|(np.abs(xyz[:,1])<2e-6)
    n_surf = surface[conn].sum(axis=1)
    n_nose = nose[conn].sum(axis=1)
    n_plane = on_plane[conn].sum(axis=1)
    inv_first = np.full(len(conn),-1,dtype=np.int16)
    counts=[]
    first_frame = None
    first_ids = None
    snapshots = {}
    for i in range(len(t)):
        sj = min_sj(pos[i].astype(np.float64)[conn])
        bad = sj<=0
        counts.append(int(bad.sum()))
        newly = bad & (inv_first<0)
        inv_first[newly]=i
        if first_frame is None and bad.any():
            first_frame=i
            first_ids=np.flatnonzero(bad)
        if i==len(t)-1 or (first_frame is not None and i==first_frame):
            snapshots[str(i)]={'time_us':float(t[i]),'count':int(bad.sum()),
                'with_surface_node':int((bad&(n_surf>0)).sum()),
                'with_nose_node':int((bad&(n_nose>0)).sum()),
                'with_symmetry_plane_node':int((bad&(n_plane>0)).sum()),
                'mean_initial_z_mm':float(ctr[bad,2].mean()*1e3) if bad.any() else None,
                'mean_initial_radial_mm':float(r[bad].mean()*1e3) if bad.any() else None}
    x = {'name':os.path.basename(path),'frames':len(t),'time_end_us':float(t[-1]),
         'hexes':len(conn),'wedges':len(wedge),
         'first_inversion_bracket_us':[float(t[first_frame-1]),float(t[first_frame])] if first_frame else None,
         'first_inversion_count':len(first_ids) if first_ids is not None else 0,
         'first_inversion_indices_0based':first_ids.tolist() if first_ids is not None else [],
         'initial_min_sj_quantiles':np.percentile(initial_sj,[0,1,50,99]).tolist(),
         'initial_min_edge_mm_quantiles':(np.percentile(edges.min(axis=1),[0,1,50,99])*1e3).tolist(),
         'end_inverted':counts[-1],'ever_inverted':int((inv_first>=0).sum()),
         'snapshots':snapshots}
    if first_ids is not None:
        k=first_ids
        x['first_location']={'centroids_mm':(ctr[k]*1e3).round(4).tolist(),
          'radius_from_ball_center_mm':(r[k]*1e3).round(4).tolist(),
          'min_edge_mm':(edges[k].min(axis=1)*1e3).round(4).tolist(),
          'initial_min_sj':initial_sj[k].round(4).tolist(),
          'surface_node_count':n_surf[k].tolist(),
          'nose_node_count':n_nose[k].tolist(),
          'symmetry_plane_node_count':n_plane[k].tolist()}
    extract = path.replace('_viewer.npz','_extract.json')
    if os.path.exists(extract):
        j=json.load(open(extract,encoding='utf-8'))
        deletion = [(v['t']*1e6,v['cnt']['ball'][1]) for v in j['status']]
        q=next((i for i,(_,n) in enumerate(deletion) if n>0),None)
        x['first_deletion_bracket_us']=[deletion[q-1][0],deletion[q][0]] if q else None
        x['first_deletion_sample_count']=deletion[q][1] if q is not None else 0
        x['end_deleted']=deletion[-1][1]
        x['ALLKE_initial_raw']=j['energy']['ALLKE'][0][1]
    return x


def main():
    root=sys.argv[1] if len(sys.argv)>1 else os.path.abspath(os.path.join(os.path.dirname(__file__),'../../../..'))
    out=sys.argv[2] if len(sys.argv)>2 else os.path.join(os.path.dirname(__file__),'inversion_summary.json')
    paths=[]
    for sub in ['vals-plywise-balltests','vals-plywise-balltests2']:
        paths+=sorted(glob.glob(os.path.join(root,'Meshing',sub,'results','*_viewer.npz')))
    results={}
    for path in paths:
        x=analyze(path)
        results[x['name'].replace('_viewer.npz','')]=x
        print(x['name'],x['first_inversion_bracket_us'],x['end_inverted'],flush=True)
    with open(out,'w',encoding='utf-8') as f:
        json.dump(results,f,indent=2)


if __name__=='__main__':
    main()
