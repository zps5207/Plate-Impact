import json
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
from embmesh.parser import parse_deck
from embmesh.selection import select_elements

host=parse_deck(sys.argv[1]);source=parse_deck(sys.argv[2])
he,hn=select_elements(host,'Plate-1')
se,sn=select_elements(source,'Plate-1')
lines=Path(sys.argv[1]).read_text().lower()
assert len(he)==24000 and len(se)==2400
assert 'embfib' not in lines and '*embedded element' not in lines and 'ply_' not in lines
assert len(host.parts['Plate'].elsets['Plate'])==24000
assert len([line for line in lines.splitlines() if line.startswith('*solid section, elset=plate')])==1
assert len(host.parts['Plate'].nodes)==27401
assert len(host.instances)==2
for name in ('Outside','X','Y'):
    assert f'nset={name.lower()}, instance=plate-1' in lines
raw=Path(sys.argv[1]).read_text().splitlines()
plate_start=next(i for i,line in enumerate(raw) if line.lower().strip()=='*part, name=plate')
plate_end=next(i for i in range(plate_start+1,len(raw)) if raw[i].lower().strip()=='*end part')
mode='';node_labels=[];element_labels=[]
for line in raw[plate_start:plate_end]:
    if line.startswith('*'):
        mode=line.split(',')[0].lower();continue
    if not line.strip() or line.startswith('**'):continue
    if mode=='*node':node_labels.append(int(line.split(',')[0]))
    if mode=='*element':element_labels.append(int(line.split(',')[0]))
assert len(node_labels)==len(set(node_labels))==27401
assert len(element_labels)==len(set(element_labels))==24000
assert all(n in host.parts['Plate'].nodes for e in he.values() for n in e.connectivity)
def assembly_nodes(name):
    head=f'*nset, nset={name.lower()}, instance=plate-1'
    start=next(i for i,line in enumerate(raw) if line.lower().strip()==head)
    end=next(i for i in range(start+1,len(raw)) if raw[i].startswith('*'))
    return [int(v) for row in raw[start+1:end] for v in row.split(',') if v.strip()]
plate_world=host.instance_nodes('Plate-1')
plate_sets={name:assembly_nodes(name) for name in ('Outside','X','Y')}
assert all(len(ids)==len(set(ids)) and all(i in plate_world for i in ids) for ids in plate_sets.values())
assert all(abs(plate_world[i][0])<1e-8 for i in plate_sets['X'])
assert all(abs(plate_world[i][1])<1e-8 for i in plate_sets['Y'])
assert all(np.linalg.norm(plate_world[i][:2])>.049 for i in plate_sets['Outside'])
hb=np.asarray(list(hn.values()));sb=np.asarray(list(sn.values()))
result=dict(host_count=len(he),source_host_count=len(se),host_nodes=len(hn),source_nodes=len(sn),
            world_bbox_min=hb.min(0).tolist(),world_bbox_max=hb.max(0).tolist(),
            source_world_bbox_min=sb.min(0).tolist(),source_world_bbox_max=sb.max(0).tolist(),
            bbox_max_abs_difference_m=float(max(np.abs(hb.min(0)-sb.min(0)).max(),np.abs(hb.max(0)-sb.max(0)).max())),
            plate_nsets={name:len(ids) for name,ids in plate_sets.items()},
            assembly_set_lines={name:sum(1 for line in lines.splitlines() if f'nset={name.lower()}, instance=plate-1' in line) for name in ('Outside','X','Y')})
Path(sys.argv[3]).write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
