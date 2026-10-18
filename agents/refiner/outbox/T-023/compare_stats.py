"""Read baseline fiber and host counts without loading its VUEL state block."""
import argparse,json,math
from pathlib import Path
import numpy as np

def stats(path):
    part='';mode='';nodes={};count={};conn=[];fiber_area=None;fiber_names=set();sets={}
    for line in path.open():
        s=line.strip()
        if s.startswith('**') or not s:continue
        if s.startswith('*'):
            mode=s.split(',')[0].lower()
            if mode=='*part':part=next(x.split('=',1)[1].strip() for x in s.split(',') if 'name=' in x.lower())
            if mode=='*end part':part=''
            if mode=='*element':
                typ=next((x.split('=',1)[1].strip() for x in s.split(',') if 'type=' in x.lower()),'')
                name=next((x.split('=',1)[1].strip() for x in s.split(',') if 'elset=' in x.lower()),'')
            if mode=='*solid section' and 'material=Fiber' in s:mode='*fiber section'
            continue
        if mode=='*node' and part:
            v=s.split(',');nodes.setdefault(part,{})[int(v[0])]=np.array(list(map(float,v[1:4])))
        if mode=='*element' and part:
            v=[int(x) for x in s.split(',') if x.strip()]
            count[(part,typ)]=count.get((part,typ),0)+1
            if typ=='T3D2':conn.append((v[1],v[2]));fiber_names.add(name)
        if mode=='*fiber section':
            try:fiber_area=float(s.split(',')[0])
            except ValueError:pass
    fiber_nodes=nodes['EMBFIB'];lengths=[float(np.linalg.norm(fiber_nodes[b]-fiber_nodes[a])) for a,b in conn];length=sum(lengths)
    return {'part_nodes':{k:len(v) for k,v in nodes.items()},'element_counts':{f'{a}/{b}':n for (a,b),n in count.items()},
            'fiber_segments':len(conn),'fiber_length_m':length,'minimum_fiber_segment_m':min(lengths),'fiber_section_area_m2':fiber_area,
            'fiber_volume_m3':length*fiber_area,'fiber_elsets':sorted(fiber_names)}

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('baseline',type=Path);ap.add_argument('output',type=Path)
    a=ap.parse_args();r=stats(a.baseline);a.output.write_text(json.dumps(r,indent=2));print(json.dumps(r,indent=2))
