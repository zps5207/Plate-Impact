"""Check deck labels/references and sampled fiber containment."""
import argparse,json,sys
from collections import defaultdict
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
sys.path.insert(0,str(Path(__file__).resolve().parents[4]))
from embmesh.geometry import inverse_hex
from stack_and_fibers import load_base,stack_length,stack,make_fibers,merge_short_segments,slopes,boundary_edges,edge_clearance

def blocks(lines):
    starts=[i for i,s in enumerate(lines) if s.startswith('*') and not s.startswith('**')]
    for j,a in enumerate(starts):yield lines[a],lines[a+1:starts[j+1] if j+1<len(starts) else len(lines)]

def opt(head,name):
    return next((s.split('=',1)[1].strip() for s in head.split(',')[1:] if s.strip().lower().startswith(name.lower()+'=')),None)

def nums(data,generate=False):
    v=[int(x) for s in data if s.strip() and not s.startswith('**') for x in s.split(',') if x.strip()]
    if generate:
        assert len(v)%3==0
        return [x for a,b,h in zip(v[::3],v[1::3],v[2::3]) for x in range(a,b+1,h)]
    return v

def check(deck,base,out):
    lines=deck.read_text().splitlines();scope='';parts=defaultdict(lambda:{'nodes':{},'elems':{}});instances={};sets={};surfaces={};emb=[];sections=[];dups=[];materials=[]
    for head,data in blocks(lines):
        key=head.split(',')[0].lower()
        if key=='*part':scope=opt(head,'name');continue
        if key=='*end part':scope='';continue
        if key=='*instance':
            name=opt(head,'name');dups+= [('instance',name)] if name in instances else []
            instances[name]=opt(head,'part');continue
        if key=='*node':
            for s in data:
                if not s.strip() or s.startswith('**'):continue
                v=s.split(',');i=int(v[0]);dups += [('node',scope,i)] if i in parts[scope]['nodes'] else []
                parts[scope]['nodes'][i]=tuple(map(float,v[1:4]))
        if key=='*element':
            for s in data:
                if not s.strip() or s.startswith('**'):continue
                v=[int(x) for x in s.split(',') if x.strip()];i=v[0]
                dups += [('element',scope,i)] if i in parts[scope]['elems'] else []
                parts[scope]['elems'][i]=v[1:]
        if key in ('*nset','*elset'):
            kind=key[1:];name=opt(head,kind);inst=opt(head,'instance');identity=(scope,inst,kind,name.lower())
            dups += [('set',identity)] if identity in sets else []
            sets[identity]=nums(data,'generate' in head.lower())
        if key=='*surface':
            name=opt(head,'name').lower();dups += [('surface',name)] if name in surfaces else []
            surfaces[name]=(opt(head,'type').lower(),[s.strip().split(',')[0].strip() for s in data if s.strip() and not s.startswith('**')])
        if key=='*embedded element':emb.append((opt(head,'host elset'),[s.strip() for s in data if s.strip() and not s.startswith('**')]))
        if key=='*solid section':sections.append((scope,opt(head,'elset'),opt(head,'material')))
        if key=='*material':materials.append(opt(head,'name').strip('"'))
    assert not dups,dups[:10]
    assert instances=={'Plate-1':'Plate','Ball-1':'Ball','EMBFIB-1':'EMBFIB'},instances
    for scope,p in parts.items():
        for eid,conn in p['elems'].items():assert all(n in p['nodes'] for n in conn),(scope,eid)
    for (scope,inst,kind,name),ids in sets.items():
        pool=parts[instances[inst] if inst else scope]['nodes' if kind=='nset' else 'elems']
        assert ids and len(ids)==len(set(ids)) and all(i in pool for i in ids),(scope,inst,name)
    for name,(kind,refs) in surfaces.items():
        for ref in refs:assert any(k==('nset' if kind=='node' else 'elset') and nm==ref.lower() for sc,ins,k,nm in sets),(name,ref)
    assert len(emb)==10 and len([x for x in sections if x[0]=='Plate'])==10 and len([x for x in sections if x[0]=='EMBFIB'])==2
    assert set(materials)=={'Fiber','Matrix','Mild Steel'}
    for scope,name,material in sections:
        assert material.strip('"') in materials
        assert (scope,None,'elset',name.lower()) in sets,(scope,name)
    for p,(host,refs) in enumerate(emb,1):
        assert host==f'PLY_{p}' and refs==[f'EMBFIB-1.FIBERS_PLY_{p}']
        assert ('','Plate-1','elset',host.lower()) in sets and ('EMBFIB',None,'elset',f'fibers_ply_{p}') in sets
    for name in ('Outside','X','Y'):
        assert ('','Plate-1','nset',name.lower()) in sets
    assert any('EMBMESH_FIBER_NODES , EMBMESH_BALL_SURF' in s for s in lines)
    assert any('EMBMESH_PLATE_NODES , EMBMESH_BALL_SURF' in s for s in lines)
    assert any('Ball-1.Ball, 3, -500.' in s for s in lines)
    top,quads=load_base(base);total,_=stack_length(base);nodes,elems=stack(top,quads,10,total)
    runs,merge=merge_short_segments(make_fibers(top,quads,10,.00096,total),top,quads)
    tree=cKDTree(top[quads][:,:,[0,2]].mean(axis=1))
    edge=np.linalg.norm(np.roll(top[quads][:,:,[0,2]],-1,axis=1)-top[quads][:,:,[0,2]],axis=2).min(axis=1)
    bad=short=count=0;minimum=float('inf');minimum_ratio=float('inf');normal_min=float('inf');outline_min=float('inf')
    boundary=boundary_edges(top,quads)
    fiber_node_id=1
    plate_nodes=parts['Plate']['nodes'];plate_elems=parts['Plate']['elems'];fiber_nodes=parts['EMBFIB']['nodes']
    for ply,pts,hosts in runs:
        across=2 if ply%2==0 else 0;along=0 if ply%2==0 else 2
        for endpoint in (pts[0],pts[-1]):outline_min=min(outline_min,edge_clearance(endpoint[along],endpoint[across],across,boundary))
        for j,eid in enumerate(hosts):
            a=np.asarray(fiber_nodes[fiber_node_id+j]);b=np.asarray(fiber_nodes[fiber_node_id+j+1])
            length=float(np.linalg.norm(np.asarray(b)-a));minimum=min(minimum,length);minimum_ratio=min(minimum_ratio,length/edge[eid]);short+=length<.05*edge[eid]
            for t in (0,.25,.5,.75,1):
                point=(1-t)*np.asarray(a)+t*np.asarray(b);candidates=np.atleast_1d(tree.query(point[[0,2]],k=12)[1])
                bad+=not any(inverse_hex(point,np.asarray([plate_nodes[n] for n in plate_elems[ply*len(quads)+int(e)+1]])) is not None for e in candidates)
                r2=point[0]**2+point[2]**2;ct=.27-ply*.001;cb=ct-.001
                normal_min=min(normal_min,abs(np.sqrt(r2+(point[1]-ct)**2)-.25),abs(np.sqrt(r2+(point[1]-cb)**2)-.25))
                count+=1
        fiber_node_id+=len(pts)
    assert fiber_node_id-1==len(fiber_nodes)
    result={'parts':{k:{'nodes':len(v['nodes']),'elements':len(v['elems'])} for k,v in parts.items()},
            'sets':len(sets),'surfaces':len(surfaces),'embedded_blocks':len(emb),'sections':sections,
            'duplicate_labels_or_names':dups,'missing_references':0,'sampled_fiber_points':count,
            'sampled_fiber_points_outside_ply':bad,'segments_below_5pct_local_edge':int(short),
            'minimum_segment_m':minimum,'minimum_segment_over_local_edge':minimum_ratio,
            'minimum_normal_clearance_m':normal_min,'minimum_endpoint_outline_clearance_m':outline_min,
            'half_diameter_m':.00048,'merge':merge}
    out.write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
    assert bad==0

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('deck',type=Path);ap.add_argument('base',type=Path);ap.add_argument('output',type=Path)
    a=ap.parse_args();check(a.deck,a.base,a.output)
