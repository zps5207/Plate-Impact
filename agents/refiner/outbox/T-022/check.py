"""Validate real C-mesh translation plies and fibers; writes a JSON report."""
import argparse
import json
import math
import os
import sys
import threading
import time
from pathlib import Path

import numpy as np
import psutil

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from embmesh.fibers import Fiber
from embmesh.geometry import inverse_hex, hex_volume
from embmesh.model import Element
from embmesh.volume import fiber_volume_rows
from stack_and_fibers import load_base, stack_length, slopes, stack, make_fibers, save_vtk, boundary_edges, edge_clearance


def quad_height_at(pt, q):
    """Bilinear top-face height at projected (x,z), with unconstrained Newton."""
    u=v=.5
    xz=pt[[0,2]]
    for _ in range(12):
        val=(1-u)*(1-v)*q[0]+u*(1-v)*q[1]+u*v*q[2]+(1-u)*v*q[3]
        du=(1-v)*(q[1]-q[0])+v*(q[2]-q[3])
        dv=(1-u)*(q[3]-q[0])+u*(q[2]-q[1])
        delta=np.linalg.solve(np.column_stack((du[[0,2]],dv[[0,2]])),val[[0,2]]-xz)
        u-=delta[0];v-=delta[1]
        if np.linalg.norm(delta)<1e-10:break
    val=(1-u)*(1-v)*q[0]+u*(1-v)*q[1]+u*v*q[2]+(1-u)*v*q[3]
    return val[1]


def normal_clearance_sphere(pt,p,h):
    """Distance to analytic spherical interfaces matching the source warp."""
    R=.25
    r2=pt[0]**2+pt[2]**2
    center_top=.02-p*h+R
    center_bot=center_top-h
    dt=abs(math.sqrt(r2+(pt[1]-center_top)**2)-R)
    db=abs(math.sqrt(r2+(pt[1]-center_bot)**2)-R)
    return min(dt,db)


def plot_preview(path,top,quads,runs):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    fig,ax=plt.subplots(figsize=(8,8))
    edge=[]
    for q in quads:
        x=top[q][:,[0,2]]
        edge.extend([(x[i],x[(i+1)%4]) for i in range(4)])
    ax.add_collection(LineCollection(edge,colors='#bbbbbb',linewidths=.23))
    for p,points,_ in runs:
        if p==0:
            arr=np.asarray(points)
            ax.plot(arr[:,0],arr[:,2],color='#bd2d2d',lw=.65)
    ax.set_aspect('equal');ax.set_xlabel('Part X (m)');ax.set_ylabel('Part Z (m)')
    ax.set_title('Ply 1 fibers over real C-mesh, top view')
    ax.autoscale();fig.tight_layout();fig.savefig(path/'fibers_top.png',dpi=160);plt.close(fig)
    fig,ax=plt.subplots(figsize=(8,4))
    for p,points,_ in runs:
        if p==0:
            arr=np.asarray(points)
            ax.plot(arr[:,0],arr[:,1],color='#bd2d2d',lw=.5)
    ax.set_xlabel('Part X (m)');ax.set_ylabel('Part Y (m)')
    ax.set_title('Ply 1 fibers, side view (0 degree lines)')
    fig.tight_layout();fig.savefig(path/'fibers_side.png',dpi=160);plt.close(fig)


def check_case(deck,nplies,d,out,make_preview=False):
    started=time.perf_counter()
    process=psutil.Process(os.getpid());peak=[process.memory_info().rss];running=[True]
    def poll():
        while running[0]:
            peak[0]=max(peak[0],process.memory_info().rss)
            time.sleep(.05)
    thread=threading.Thread(target=poll,daemon=True);thread.start()
    top,quads=load_base(deck)
    total,stack_dev=stack_length(deck)
    slope=slopes(top,quads)
    h=total/nplies;dmax=h/math.sqrt(1+(math.tan(math.radians(slope['theta_max_deg'])))**2)
    nodes,elems=stack(top,quads,nplies,total)
    runs=make_fibers(top,quads,nplies,d,total)
    out.mkdir(parents=True,exist_ok=True)
    if make_preview:
        save_vtk(out/'fibers_ply1.vtk',runs)
        plot_preview(out,top,quads,runs)
    vertices=midpoints=bad_v=bad_m=bad_sample=0
    max_chord=0.;max_out=0.;min_normal=float('inf')
    edge_min=float('inf');edge_geom=boundary_edges(top,quads)
    short=0;shortest=float('inf');snap_bad=0;snap_total=0
    snapped_shortest=float('inf');snapped_short=0
    local_edges=np.linalg.norm(np.roll(top[quads][:,:,[0,2]],-1,axis=1)-top[quads][:,:,[0,2]],axis=2).min(axis=1)
    for p,points,hosts in runs:
        pts=np.asarray(points)
        across_axis=2 if p%2==0 else 0
        along_axis=0 if p%2==0 else 2
        for endpoint in (pts[0],pts[-1]):
            edge_min=min(edge_min,edge_clearance(endpoint[along_axis],endpoint[across_axis],across_axis,edge_geom))
        for i,pt in enumerate(pts):
            vertices+=1
            candidate=([hosts[i-1]] if i else [])+([hosts[i]] if i<len(hosts) else [])
            if not any(inverse_hex(pt,nodes[elems[p*len(quads)+e]]) is not None for e in candidate):bad_v+=1
            min_normal=min(min_normal,normal_clearance_sphere(pt,p,h))
        for i,(a,b,eid) in enumerate(zip(pts[:-1],pts[1:],hosts)):
            hp=nodes[elems[p*len(quads)+eid]]
            seglen=float(np.linalg.norm(b-a));shortest=min(shortest,seglen)
            if seglen<.05*local_edges[eid]:short+=1
            midpoints+=1
            if inverse_hex((a+b)/2,hp) is None:bad_m+=1
            for t in (.2,.4,.5,.6,.8):
                pt=a+t*(b-a)
                if inverse_hex(pt,hp) is None:bad_sample+=1
                surface_y=quad_height_at(pt,top[quads[eid]])-(p+.5)*h
                chord=abs(pt[1]-surface_y)
                max_chord=max(max_chord,chord)
                max_out=max(max_out,max(0.,chord-h/2))
                min_normal=min(min_normal,normal_clearance_sphere(pt,p,h))
        # Snap: remove vertices that create a segment shorter than 5% of
        # its host's local edge. Check new midpoints against adjacent hosts.
        keep=[0]
        for i,eid in enumerate(hosts):
            if i+1<len(hosts) and np.linalg.norm(pts[i+1]-pts[keep[-1]])<.05*local_edges[eid]:
                continue
            keep.append(i+1)
        if keep[-1]!=len(pts)-1:keep.append(len(pts)-1)
        for a_idx,b_idx in zip(keep[:-1],keep[1:]):
            snap_total+=1
            newlen=float(np.linalg.norm(pts[b_idx]-pts[a_idx]))
            snapped_shortest=min(snapped_shortest,newlen)
            if newlen<.05*min(local_edges[e] for e in hosts[a_idx:b_idx]):snapped_short+=1
            m=(pts[a_idx]+pts[b_idx])/2
            candidates=set(hosts[a_idx:b_idx])
            if not any(inverse_hex(m,nodes[elems[p*len(quads)+e]]) is not None for e in candidates):
                snap_bad+=1
    # Use project volume machinery on ply 1 only (single process, low RAM).
    base_nodes={i+1:nodes[i] for i in range(2*len(top))}
    base_elems={i+1:Element(i+1,tuple((elems[i]+1).tolist()),'C3D8R') for i in range(len(quads))}
    base_fibers=[Fiber(i+1,np.asarray(points),p,'t0') for i,(p,points,_) in enumerate(runs) if p==0]
    rows=fiber_volume_rows(base_elems,base_nodes,base_fibers,d,n_jobs=1)
    vf=np.array([r[3] for r in rows])
    running[0]=False;thread.join(timeout=.2)
    result=dict(plies=nplies,d_m=d,h_m=h,stack_deviation_m=stack_dev,theta_max_deg=slope['theta_max_deg'],
                theta_edge_deg=slope['theta_edge_deg'],theta_bilinear_deg=slope['theta_bilinear_deg'],
                d_max_m=dmax,N_max=math.floor(total*math.cos(math.radians(slope['theta_max_deg']))/d),
                fibers=len(runs),vertices=vertices,vertices_outside=bad_v,
                midpoints=midpoints,midpoints_outside=bad_m,
                sampled_segment_points_outside=bad_sample,
                max_chord_error_m=max_chord,max_chord_error_over_d=max_chord/d,
                max_outside_host_m=max_out,max_outside_host_over_d=max_out/d,
                min_center_normal_distance_m=min_normal,half_d_m=d/2,
                min_endpoint_outline_clearance_m=edge_min,
                normal_fit=min_normal>=d/2,formula_fit=d<=dmax,
                shortest_segment_m=shortest,segments_below_5pct_edge=short,
                snapped_midpoints=snap_total,snapped_midpoints_outside=snap_bad,
                snapped_shortest_segment_m=snapped_shortest,snapped_segments_below_5pct_edge=snapped_short,
                vf_min=float(vf.min()),vf_max=float(vf.max()),vf_mean=float(vf.mean()),
                detJ_ratio_min=slope['detJ_ratio_min'],detJ_ratio_max=slope['detJ_ratio_max'],
                skew_min=slope['skew_min'],skew_max=slope['skew_max'],run_seconds=time.perf_counter()-started,
                peak_rss_mb=peak[0]/1024**2)
    (out/'checks.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result))
    return result


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('deck',type=Path)
    ap.add_argument('--plies',type=int,required=True)
    ap.add_argument('--diameter',type=float,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--preview',action='store_true')
    args=ap.parse_args()
    check_case(args.deck,args.plies,args.diameter,args.output,args.preview)


if __name__=='__main__':main()
