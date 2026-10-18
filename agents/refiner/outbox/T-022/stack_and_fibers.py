"""Translation plies and 0/90 fibers clipped to the real projected C-mesh.

All coordinates are Plate PART coordinates: projection=(X,Z), stack=-Y.
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from embmesh.parser import parse_deck
from embmesh.fibers import Fiber, _layer_positions
from embmesh.model import Element


def load_base(path):
    p = parse_deck(path).parts['Plate']
    n = len(p.nodes)//2
    top = np.array([p.nodes[i] for i in range(1,n+1)])
    quads = np.array([p.elements[i].connectivity[:4] for i in sorted(p.elements)], dtype=int)-1
    return top, quads


def stack_length(path):
    p=parse_deck(path).parts['Plate']
    n=len(p.nodes)//2
    top=np.array([p.nodes[i] for i in range(1,n+1)])
    bot=np.array([p.nodes[i+n] for i in range(1,n+1)])
    delta=bot-top
    s=delta.mean(axis=0)
    err=float(np.linalg.norm(delta-s,axis=1).max())
    if err>1e-8 or s[1]>=0 or abs(s[1])/np.linalg.norm(s)<.999:
        raise ValueError(f'non-translation or non-Y stack: s={s}, max deviation={err}')
    return float(np.linalg.norm(s)),err


def slopes(top, quads):
    p = top[quads]
    edge_vec = np.roll(p,-1,axis=1)-p
    edge_slope = np.abs(edge_vec[:,:,1])/np.maximum(np.linalg.norm(edge_vec[:,:,[0,2]],axis=2),1e-15)
    max_edge = float(edge_slope.max())
    grad_max = 0.; grad_min=float('inf')
    for u,v in ((0,0),(1,0),(1,1),(0,1),(.5,.5)):
        du=(1-v)*(p[:,1]-p[:,0])+v*(p[:,2]-p[:,3])
        dv=(1-u)*(p[:,3]-p[:,0])+u*(p[:,2]-p[:,1])
        mat=np.stack((du[:,[0,2]],dv[:,[0,2]]),axis=2)
        rhs=np.stack((du[:,1],dv[:,1]),axis=1)
        grad=np.linalg.solve(mat.transpose(0,2,1),rhs[...,None])[...,0]
        norms=np.linalg.norm(grad,axis=1)
        grad_max=max(grad_max,float(norms.max()))
        grad_min=min(grad_min,float(norms.min()))
    # In translated hexes, 3D detJ varies with projected quad area.
    areas=[]
    for u,v in ((0,0),(1,0),(1,1),(0,1),(.5,.5)):
        du=(1-v)*(p[:,1]-p[:,0])+v*(p[:,2]-p[:,3])
        dv=(1-u)*(p[:,3]-p[:,0])+u*(p[:,2]-p[:,1])
        areas.append(np.abs(du[:,0]*dv[:,2]-du[:,2]*dv[:,0]))
    aa=np.stack(areas,axis=1)
    ratio=aa.min(1)/aa.max(1)
    return dict(theta_edge_deg=float(np.degrees(np.arctan(max_edge))),
                theta_bilinear_deg=float(np.degrees(np.arctan(grad_max))),
                theta_max_deg=float(np.degrees(np.arctan(max(max_edge,grad_max)))),
                detJ_ratio_min=float(ratio.min()),detJ_ratio_max=float(ratio.max()),
                skew_min=float(np.sqrt(1+grad_min**2)),
                skew_max=float(np.sqrt(1+max(max_edge,grad_max)**2)))


def stack(top, quads, nplies,total_thickness=.01):
    h=total_thickness/nplies
    n=len(top); m=len(quads)
    nodes=np.empty((nplies*2*n,3),float)
    elems=np.empty((nplies*m,8),np.int32)
    for p in range(nplies):
        offset=p*2*n
        nodes[offset:offset+n]=top-np.array([0,p*h,0])
        nodes[offset+n:offset+2*n]=top-np.array([0,(p+1)*h,0])
        elems[p*m:(p+1)*m,:4]=quads+offset
        elems[p*m:(p+1)*m,4:]=quads+offset+n
    return nodes,elems


def scan_intervals(top, quads, across_axis, c):
    """Intersections of one projected scanline with every convex top quad."""
    along_axis = 2 if across_axis == 0 else 0
    p=top[quads]
    q=np.roll(p,-1,axis=1)
    a=p[:,:,across_axis]; b=q[:,:,across_axis]
    cross=((a<=c)&(c<b))|((b<=c)&(c<a))
    t=np.divide(c-a,b-a,out=np.zeros_like(a),where=np.abs(b-a)>1e-14)
    u=p[:,:,along_axis]+t*(q[:,:,along_axis]-p[:,:,along_axis])
    y=p[:,:,1]+t*(q[:,:,1]-p[:,:,1])
    ids=np.where(cross.sum(axis=1)==2)[0]
    out=[]
    for eid in ids:
        us=u[eid,cross[eid]]; ys=y[eid,cross[eid]]
        o=np.argsort(us)
        if us[o[1]]-us[o[0]]>1e-12:
            out.append((float(us[o[0]]),float(us[o[1]]),float(ys[o[0]]),float(ys[o[1]]),int(eid)))
    return sorted(out)


def boundary_edges(top,quads):
    count=Counter()
    for face in quads:
        for i in range(4):
            a,b=int(face[i]),int(face[(i+1)%4])
            count[tuple(sorted((a,b)))]+=1
    return np.array([(top[a][[0,2]],top[b][[0,2]]) for (a,b),n in count.items() if n==1])


def edge_clearance(u,c,across_axis,edges):
    xz=np.array([u,c]) if across_axis==2 else np.array([c,u])
    a=edges[:,0,:];v=edges[:,1,:]-a
    t=np.clip(np.sum((xz-a)*v,axis=1)/np.sum(v*v,axis=1),0,1)
    return float(np.sqrt(np.sum((xz-(a+t[:,None]*v))**2,axis=1)).min())


def inset_run(lo,hi,c,across_axis,edges,r):
    """Trim both ends until projected centerline clears every outline edge."""
    if hi-lo<=2*r:return None
    def first_good(start,end):
        u=start
        step=max(r/8,1e-7)
        while u<end and edge_clearance(u,c,across_axis,edges)<r-1e-10:
            u=min(end,u+step)
        if edge_clearance(u,c,across_axis,edges)<r-1e-10:return None
        a=max(start,u-step);b=u
        for _ in range(22):
            m=(a+b)/2
            if edge_clearance(m,c,across_axis,edges)>=r:b=m
            else:a=m
        return b
    a=first_good(lo,(lo+hi)/2)
    if a is None:return None
    # Reflect the coordinate for the right end.
    def right():
        u=hi;step=max(r/8,1e-7)
        while u>(lo+hi)/2 and edge_clearance(u,c,across_axis,edges)<r-1e-10:
            u=max((lo+hi)/2,u-step)
        if edge_clearance(u,c,across_axis,edges)<r-1e-10:return None
        aa=u;bb=min(hi,u+step)
        for _ in range(22):
            m=(aa+bb)/2
            if edge_clearance(m,c,across_axis,edges)>=r:aa=m
            else:bb=m
        return aa
    b=right()
    return (a,b) if b is not None and b-a>1e-10 else None


def make_fibers(top,quads,nplies,d,total_thickness=.01):
    h=total_thickness/nplies
    runs=[]
    edges=boundary_edges(top,quads)
    for p in range(nplies):
        across_axis=2 if p%2==0 else 0
        along_axis=0 if p%2==0 else 2
        for c in _layer_positions(float(top[:,across_axis].min()),float(top[:,across_axis].max()),d,0):
            intervals=scan_intervals(top,quads,across_axis,c)
            groups=[]; group=[]; hi=-np.inf
            for x in intervals:
                if group and x[0]>hi+2e-8:
                    groups.append(group);group=[]
                group.append(x);hi=max(hi,x[1])
            if group:groups.append(group)
            for group in groups:
                bounds=inset_run(group[0][0],max(x[1] for x in group),c,across_axis,edges,d/2)
                if bounds is None:continue
                lo,end=bounds
                points=[]; hosts=[]
                for a,b,ya,yb,eid in group:
                    aa=max(lo,a);bb=min(end,b)
                    if bb-aa<=1e-11: continue
                    def pt(u):
                        xyz=np.empty(3)
                        xyz[along_axis]=u;xyz[across_axis]=c
                        xyz[1]=ya+(yb-ya)*(u-a)/(b-a)-(p+.5)*h
                        return xyz
                    pa,pb=pt(aa),pt(bb)
                    if points and np.linalg.norm(pa-points[-1])>2e-7:
                        # The line left the mesh or numerical gap was too large.
                        if len(points)>1:runs.append((p,points,hosts))
                        points=[];hosts=[]
                    if not points:points.append(pa)
                    points.append(pb);hosts.append(eid)
                if len(points)>1:runs.append((p,points,hosts))
    return runs


def save_vtk(path,runs,ply=0):
    fibers=[r for r in runs if r[0]==ply]
    pts=np.concatenate([np.asarray(r[1]) for r in fibers],axis=0) if fibers else np.empty((0,3))
    lines=[];offset=0
    for _,q,_ in fibers:
        lines.append([len(q)]+list(range(offset,offset+len(q))))
        offset+=len(q)
    with path.open('w') as f:
        f.write('# vtk DataFile Version 3.0\ncurved ply fibers\nASCII\nDATASET POLYDATA\n')
        f.write(f'POINTS {len(pts)} float\n')
        for x in pts:f.write(f'{x[0]:.9g} {x[1]:.9g} {x[2]:.9g}\n')
        f.write(f'LINES {len(lines)} {sum(len(x) for x in lines)}\n')
        for x in lines:f.write(' '.join(map(str,x))+'\n')


def write_abaqus_deck(base_path,out_path,nodes,elems,quads,runs,nplies,d):
    """Write a native-host smoke deck with per-ply fiber embedding, no cohesive law."""
    lines=base_path.read_text().splitlines()
    def key(s):return s.strip().split(',')[0].lower()
    p0=next(i for i,x in enumerate(lines) if key(x)=='*part' and 'name=plate' in x.lower())
    p1=next(i+1 for i in range(p0+1,len(lines)) if key(lines[i])=='*end part')
    a0=next(i for i,x in enumerate(lines) if key(x)=='*assembly')
    a1=next(i+1 for i in range(a0+1,len(lines)) if key(lines[i])=='*end assembly')
    part=['*Part, name=Plate','*Node']
    for i,x in enumerate(nodes,1):part.append(f'{i}, {x[0]:.12g}, {x[1]:.12g}, {x[2]:.12g}')
    fiber_n0=len(nodes);fiber_e0=len(elems)
    fiber_connect=[];fiber_ply=[]
    for p,pts,_ in runs:
        first=fiber_n0+1
        for x in pts:
            fiber_n0+=1
            part.append(f'{fiber_n0}, {x[0]:.12g}, {x[1]:.12g}, {x[2]:.12g}')
        for j in range(len(pts)-1):
            fiber_e0+=1
            fiber_connect.append((fiber_e0,first+j,first+j+1))
            fiber_ply.append(p)
    part.append('*Element, type=C3D8R')
    for i,c in enumerate(elems,1):part.append(f'{i}, '+', '.join(str(int(x)+1) for x in c))
    part.append('*Element, type=T3D2')
    for e,a,b in fiber_connect:part.append(f'{e}, {a}, {b}')
    def set_rows(labels):
        vals=sorted(labels)
        return [', '.join(map(str,vals[i:i+16])) for i in range(0,len(vals),16)]
    m=len(quads)
    for p in range(nplies):
        part.append(f'*Elset, elset=PLY_{p+1}')
        part+=set_rows(range(p*m+1,(p+1)*m+1))
        part.append(f'*Solid Section, elset=PLY_{p+1}, controls=EC-1, material=Matrix')
        part.append(',')
        fiber_ids=[e for (e,_,_),layer in zip(fiber_connect,fiber_ply) if layer==p]
        part.append(f'*Elset, elset=FIBERS_PLY_{p+1}')
        part+=set_rows(fiber_ids)
        part.append(f'*Solid Section, elset=FIBERS_PLY_{p+1}, material=Fiber')
        part.append(f'{np.pi*d*d/4:.15g}')
    part.append('*End Part')
    # Rebuild assembly sets of Plate-1; preserve Ball-1 untouched.
    asm=lines[a0:a1]
    old_sets={}
    kept=[]
    starts=[i for i,x in enumerate(asm) if x.lstrip().startswith('*') and not x.lstrip().startswith('**')]
    for j,start in enumerate(starts):
        end=starts[j+1] if j+1<len(starts) else len(asm)
        head=asm[start];k=key(head);chunk=asm[start:end]
        if k=='*nset' and 'instance=Plate-1' in head:
            name=next((v.split('=',1)[1].strip() for v in head.split(',') if 'nset=' in v.lower()),'')
            vals=[int(x) for row in chunk[1:] if row.strip() and not row.lstrip().startswith('**') for x in row.split(',') if x.strip()]
            old_sets[name]=vals
        elif k in ('*assembly','*end assembly','*instance','*end instance') or ('instance=Ball-1' in head) or (k=='*surface' and 'name=Surf-2' in head):
            kept+=chunk
    insert=[];nbase=2*len(nodes)//(2*nplies) # 2*top-node count
    for name,vals in old_sets.items():
        if name.lower()=='plate':
            members=range(1,len(nodes)+1)
        else:
            members=(v+p*nbase for p in range(nplies) for v in vals)
        insert.append(f'*Nset, nset={name}, instance=Plate-1')
        insert+=set_rows(members)
    insert.append('*Elset, elset=plate, instance=Plate-1')
    insert+=set_rows(range(1,len(elems)+1))
    for p in range(nplies):
        insert.append(f'*Elset, elset=PLY_{p+1}, instance=Plate-1')
        insert+=set_rows(range(p*m+1,(p+1)*m+1))
        insert.append(f'*Elset, elset=FIBERS_PLY_{p+1}, instance=Plate-1')
        insert+=set_rows(e for (e,_,_),layer in zip(fiber_connect,fiber_ply) if layer==p)
    # For each projected boundary edge, expose corresponding lateral face.
    incidence=Counter()
    for face in quads:
        for j in range(4):incidence[tuple(sorted((int(face[j]),int(face[(j+1)%4]))))]+=1
    surface={1:list(range(1,m+1))}
    for fid in (3,4,5,6):surface[fid]=[]
    for p in range(nplies):
        for e,face in enumerate(quads):
            for j,fid in enumerate((3,4,5,6)):
                if incidence[tuple(sorted((int(face[j]),int(face[(j+1)%4]))))]==1:
                    surface[fid].append(p*m+e+1)
    for fid,ids in surface.items():
        insert.append(f'*Elset, elset=_Surf-1_S{fid}, instance=Plate-1')
        insert+=set_rows(ids)
    insert.append('*Surface, type=ELEMENT, name=Surf-1')
    insert += [f'_Surf-1_S{fid}, S{fid}' for fid in surface]
    for p in range(nplies):
        insert.append(f'*Embedded Element, host elset=PLY_{p+1}')
        insert.append(f'FIBERS_PLY_{p+1}')
    endidx=next(i for i,x in enumerate(kept) if key(x)=='*end assembly')
    kept[endidx:endidx]=insert
    out_path.write_text('\n'.join(lines[:p0]+part+lines[p1:a0]+kept+lines[a1:])+'\n')


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('deck',type=Path)
    ap.add_argument('--plies',type=int,required=True)
    ap.add_argument('--diameter',type=float,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--abaqus-deck',action='store_true',help='write native-host deck with per-ply embedded T3D2 fibers')
    args=ap.parse_args()
    top,quads=load_base(args.deck)
    total,stack_dev=stack_length(args.deck)
    nodes,elems=stack(top,quads,args.plies,total)
    runs=make_fibers(top,quads,args.plies,args.diameter,total)
    args.output.mkdir(parents=True,exist_ok=True)
    offsets=[0];points=[];hosts=[];ply=[]
    for p,pts,hs in runs:
        points.extend(pts);hosts.extend(hs);ply.append(p);offsets.append(len(points))
    np.savez_compressed(args.output/'stack_fibers.npz',nodes=nodes,elements=elems,
                        fiber_points=np.asarray(points),fiber_offsets=np.asarray(offsets),
                        fiber_segment_hosts=np.asarray(hosts),fiber_ply=np.asarray(ply),
                        top=top,quads=quads,diameter=args.diameter,
                        ply_elset_names=np.asarray([f'PLY_{p+1}' for p in range(args.plies)]),
                        ply_elset_ranges=np.asarray([[p*len(quads)+1,(p+1)*len(quads)] for p in range(args.plies)]))
    save_vtk(args.output/'fibers_ply1.vtk',runs)
    if args.abaqus_deck:
        write_abaqus_deck(args.deck,args.output/'stacked_fibers.inp',nodes,elems,quads,runs,args.plies,args.diameter)
    print(json.dumps(dict(plies=args.plies,diameter=args.diameter,stack_deviation_m=stack_dev,fibers=len(runs),
                          vertices=len(points),segments=len(hosts),nodes=len(nodes),elements=len(elems))))


if __name__=='__main__':main()
