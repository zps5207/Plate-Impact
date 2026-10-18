"""Build the native curved 10-ply v500 comparison deck."""
import argparse
import json
import math
from collections import Counter
from pathlib import Path
import numpy as np
from stack_and_fibers import load_base, stack_length, stack, make_fibers, merge_short_segments


def blocks(lines):
    starts=[i for i,s in enumerate(lines) if s.startswith('*') and not s.startswith('**')]
    for j,a in enumerate(starts):
        yield a,starts[j+1] if j+1<len(starts) else len(lines),lines[a].split(',')[0].lower()


def rows(ids):
    ids=list(ids)
    return [', '.join(map(str,ids[i:i+16])) for i in range(0,len(ids),16)]


def setblock(kind,name,ids,instance=None):
    suffix=f', instance={instance}' if instance else ''
    return [f'*{kind}, {kind.lower()}={name}{suffix}']+rows(ids)


def build(base,baseline,out,duplicate=False,no_fibers=False):
    top,quads=load_base(base);total,_=stack_length(base)
    nplies=10;d=.00096;n=len(top);m=len(quads)
    host,elems=stack(top,quads,nplies,total,duplicate)
    raw=[] if no_fibers else make_fibers(top,quads,nplies,d,total)
    runs,merge=merge_short_segments(raw,top,quads)
    source=base.read_text().splitlines();v500=baseline.read_text().splitlines()
    bb=list(blocks(source));vb=list(blocks(v500))
    ball_start=next(a for a,z,k in bb if k=='*part' and 'name=ball' in source[a].lower())
    ball_end=next(z for a,z,k in bb if a>=ball_start and k=='*end part')
    asm_start=next(a for a,z,k in bb if k=='*assembly');asm_end=next(z for a,z,k in bb if a>=asm_start and k=='*end assembly')
    plate=['*Part, name=Plate','*Node']
    plate += [f'{i}, {p[0]:.12g}, {p[1]:.12g}, {p[2]:.12g}' for i,p in enumerate(host,1)]
    plate += ['*Element, type=C3D8R']
    plate += [f'{i}, '+', '.join(str(int(x)+1) for x in conn) for i,conn in enumerate(elems,1)]
    if no_fibers:
        plate+=setblock('Elset','Plate',range(1,len(elems)+1))
        plate += ['*Solid Section, elset=Plate, controls=EC-1, material=Matrix',',']
    else:
        for p in range(nplies):
            plate+=setblock('Elset',f'PLY_{p+1}',range(p*m+1,(p+1)*m+1))
            plate += [f'*Solid Section, elset=PLY_{p+1}, controls=EC-1, material=Matrix',',']
    plate+=['*End Part']
    fiber=['*Part, name=EMBFIB','*Node'];fconn=[];plyids=[[] for _ in range(nplies)];dirids=[[],[]]
    fcoords=[]
    for ply,pts,_ in runs:
        first=len(fcoords)+1
        fcoords.extend(pts)
        for j in range(len(pts)-1):
            eid=len(fconn)+1;fconn.append((eid,first+j,first+j+1))
            plyids[ply].append(eid);dirids[ply%2].append(eid)
    fiber += [f'{i}, {p[0]:.12g}, {p[1]:.12g}, {p[2]:.12g}' for i,p in enumerate(fcoords,1)]
    fiber += ['*Element, type=T3D2']+[f'{e}, {a}, {b}' for e,a,b in fconn]
    for p,ids in enumerate(plyids,1):fiber+=setblock('Elset',f'FIBERS_PLY_{p}',ids)
    for direction,ids in zip((0,90),dirids):
        name=f'EMBMESH_FIBERS_T{direction}'
        fiber+=setblock('Elset',name,ids)
        fiber += [f'*Solid Section, elset={name}, material=Fiber',f'{math.pi*d*d/4:.15g}']
    fiber+=['*End Part']
    # Preserve exact instance transforms and Ball-side set/surface blocks.
    oldasm=source[asm_start:asm_end];assembly=[]
    for a,z,k in blocks(oldasm):
        head=oldasm[a].lower()
        if k in ('*assembly','*instance','*end instance') or (k in ('*nset','*elset') and 'instance=ball-1' in head) or (k=='*surface' and 'name=surf-2' in head):
            assembly+=oldasm[a:z]
    if not no_fibers:assembly+=['*Instance, name=EMBFIB-1, part=EMBFIB','*End Instance']
    # Part axes are X,Z, thickness Y. Outer rim excludes symmetry edges.
    r=np.linalg.norm(top[:,[0,2]],axis=1);rmax=r.max()
    sets={'Outside':np.where(r>=rmax-1e-5)[0],
          'X':np.where(abs(top[:,0])<1e-8)[0],
          'Y':np.where(abs(top[:,2])<1e-8)[0]}
    for name,indices in sets.items():
        levels=range(2*nplies) if duplicate else range(nplies+1)
        assembly+=setblock('Nset',name,(p*n+int(i)+1 for p in levels for i in indices),'Plate-1')
    assembly+=setblock('Nset','plate',range(1,len(host)+1),'Plate-1')
    assembly+=setblock('Elset','plate',range(1,len(elems)+1),'Plate-1')
    if not no_fibers:
        for p in range(nplies):
            assembly+=setblock('Elset',f'PLY_{p+1}',range(p*m+1,(p+1)*m+1),'Plate-1')
    # Exterior top and lateral faces, using the top quad's connectivity order.
    incidence=Counter()
    for q in quads:
        for j in range(4):incidence[tuple(sorted((int(q[j]),int(q[(j+1)%4]))))]+=1
    faces={1:list(range(1,m+1)),3:[],4:[],5:[],6:[]}
    for p in range(nplies):
        for e,q in enumerate(quads):
            for j,fid in enumerate((3,4,5,6)):
                if incidence[tuple(sorted((int(q[j]),int(q[(j+1)%4]))))]==1:faces[fid].append(p*m+e+1)
    for fid,ids in faces.items():
        if ids:assembly+=setblock('Elset',f'_Surf-1_S{fid}',ids,'Plate-1')
    assembly+=['*Surface, type=ELEMENT, name=Surf-1']+[f'_Surf-1_S{fid}, S{fid}' for fid,ids in faces.items() if ids]
    if not no_fibers:
        for p in range(nplies):
            assembly += [f'*Embedded Element, host elset=PLY_{p+1}',f'EMBFIB-1.FIBERS_PLY_{p+1}']
        assembly+=setblock('Elset','EMBMESH_HOST',range(1,len(elems)+1),'Plate-1')
        assembly+=setblock('Nset','EMBMESH_PLATE_ALL_NODES',range(1,len(host)+1),'Plate-1')
        assembly+=['*Surface, type=NODE, name=EMBMESH_PLATE_NODES','EMBMESH_PLATE_ALL_NODES,']
        assembly+=setblock('Nset','EMBMESH_FIBER_ALL_NODES',range(1,len(fcoords)+1),'EMBFIB-1')
        assembly+=['*Surface, type=NODE, name=EMBMESH_FIBER_NODES','EMBMESH_FIBER_ALL_NODES,']
    # Ball contact element set from the untouched Ball part.
    ball_eids=[];inside=False
    for line in source[ball_start:ball_end]:
        if line.lower().startswith('*element'):inside=True;continue
        if line.startswith('*'):inside=False
        if inside and line.strip():ball_eids.append(int(line.split(',')[0]))
    if not no_fibers:
        assembly+=setblock('Elset','EMBMESH_BALL_ELEMENTS',ball_eids,'Ball-1')
        assembly+=['*Surface, type=ELEMENT, name=EMBMESH_BALL_SURF','EMBMESH_BALL_ELEMENTS,']
    assembly+=['*End Assembly']
    # Baseline's material and loading blocks, excluding VUEL/ghost material
    # and its enormous per-element solution state initialization.
    mat0=next(a for a,z,k in vb if k=='*material' and 'name=fiber' in v500[a].lower())
    step0=next(a for a,z,k in vb if k=='*step')
    # *Section Controls EC-1 sits before the first material in the baseline, so
    # it is not in tail; the plate sections below reference it.
    ec1=next(a for a,z,k in vb if k=='*section controls' and 'name=ec-1' in v500[a].lower())
    tail=v500[ec1:ec1+2]+v500[mat0:]
    # The initial solution state precedes material definitions in this deck;
    # copying from Fiber keeps material, BC, initial velocity and step.
    filtered=[];skip=False
    for a,z,k in blocks(tail):
        chunk=tail[a:z]
        if k=='*element output' and ('GHOST' in chunk[0] or 'VUEL' in chunk[0]):continue
        if k=='*output' and chunk[0].lower()=='*output, field, number interval=1000':continue
        if no_fibers and k=='*contact inclusions':
            filtered+=['*Contact Inclusions','Surf-1 , Surf-2','Surf-2 , Surf-1','Surf-1 ,','Surf-2 ,'];continue
        if k=='*contact inclusions':
            filtered+=['*Contact Inclusions','Surf-1 , Surf-2','Surf-2 , Surf-1','Surf-1 ,','Surf-2 ,','EMBMESH_PLATE_NODES , EMBMESH_BALL_SURF','EMBMESH_FIBER_NODES , EMBMESH_BALL_SURF'];continue
        if k=='*surface property assignment':continue
        filtered+=chunk
        if k=='*contact property assignment' and not no_fibers:
            edge_lengths=np.linalg.norm(np.roll(top[quads],-1,axis=1)-top[quads],axis=2).ravel()
            h=total/nplies
            host_edge=float(np.median(np.r_[edge_lengths,np.full(8*m,h)]))
            flens=np.array([np.linalg.norm(np.asarray(fcoords[b-1])-fcoords[a-1]) for _,a,b in fconn])
            filtered+=['*Surface Property Assignment, property=THICKNESS',f'EMBMESH_PLATE_NODES, {host_edge/2:.15g}',
                       '*Surface Property Assignment, property=THICKNESS',f'EMBMESH_FIBER_NODES, {min(host_edge,float(np.median(flens)))/2:.15g}']
    # Drop stale comments that refer to ghost and VUEL outputs.
    filtered=[s for s in filtered if 'embmesh: native ghost' not in s and 'embmesh: host VU1' not in s]
    deck=source[:ball_start]+source[ball_start:ball_end]+plate+([] if no_fibers else fiber)+assembly+filtered
    out.write_text('\n'.join(deck)+'\n')
    if no_fibers:
        print(json.dumps(dict(hosts=len(elems),host_nodes=len(host),fiber_count=0)))
        return
    lengths=np.array([np.linalg.norm(np.asarray(fcoords[b-1])-fcoords[a-1]) for _,a,b in fconn])
    stats=dict(hosts=len(elems),host_nodes=len(host),fiber_nodes=len(fcoords),fiber_segments=len(fconn),fiber_runs=len(runs),
               per_ply_segments=list(map(len,plyids)),per_ply_fibers=[sum(p==ply for p,_,_ in runs) for ply in range(nplies)],fiber_length_m=float(lengths.sum()),fiber_volume_m3=float(lengths.sum()*math.pi*d*d/4),
               min_segment_m=float(lengths.min()),median_segment_m=float(np.median(lengths)),diameter_m=d,merge=merge,
               boundary_nodes={k:len(v)*(2*nplies if duplicate else nplies+1) for k,v in sets.items()},
               contact_thickness_plate_m=host_edge/2,contact_thickness_fiber_m=min(host_edge,float(np.median(lengths)))/2)
    out.with_suffix('.json').write_text(json.dumps(stats,indent=2))
    print(json.dumps(stats,indent=2))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('base',type=Path);ap.add_argument('baseline',type=Path);ap.add_argument('output',type=Path)
    ap.add_argument('--duplicate-interface-nodes',action='store_true')
    ap.add_argument('--no-fibers',action='store_true')
    a=ap.parse_args();build(a.base,a.baseline,a.output,a.duplicate_interface_nodes,a.no_fibers)
