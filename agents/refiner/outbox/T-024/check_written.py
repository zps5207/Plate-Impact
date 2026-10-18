"""Independent world-coordinate containment audit of the written deck."""
import json
import sys
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree

sys.path.insert(0,str(Path(__file__).resolve().parent))
from embmesh.parser import parse_deck
from embmesh.selection import select_elements
from embmesh.geometry import point_in_hex

deck=parse_deck(sys.argv[1])
raw=Path(sys.argv[1]).read_text().splitlines()
fiber_instance_line=next(i for i,line in enumerate(raw) if line.lower().strip()=='*instance, name=embfib-1, part=embfib')
assert raw[fiber_instance_line+1].lower().strip()=='*end instance'
host,world=select_elements(deck,'Plate-1')
fpart=deck.parts['EMBFIB']
assert deck.instances['EMBFIB-1'].rotation_angle==0
assert np.allclose(deck.instances['EMBFIB-1'].translation,0)
fibnodes=deck.instance_nodes('EMBFIB-1')
fiber_elements=list(fpart.elements.values())
points=np.array(list(fibnodes.values()))
midpoints=np.array([.5*(fibnodes[e.connectivity[0]]+fibnodes[e.connectivity[1]]) for e in fiber_elements])
hexes=np.array([[world[n] for n in e.connectivity[:8]] for e in host.values()])
lo=hexes.min(1);hi=hexes.max(1)
tree=cKDTree(hexes.mean(1))

def audit(samples):
    bad=[]
    for i,p in enumerate(samples):
        _,ids=tree.query(p,k=32)
        if not any(np.all(p>=lo[j]-1e-9) and np.all(p<=hi[j]+1e-9) and point_in_hex(p,hexes[j]) for j in ids):
            bad.append(i)
    return bad

bad_points=audit(points);bad_midpoints=audit(midpoints)
lengths=np.array([np.linalg.norm(fibnodes[e.connectivity[1]]-fibnodes[e.connectivity[0]]) for e in fiber_elements])
result=dict(hosts=len(host),fibers=len(points)-len(fiber_elements),
            fiber_nodes=len(points),fiber_segments=len(fiber_elements),vertices_outside=len(bad_points),
            midpoints_outside=len(bad_midpoints),first_bad_vertices=bad_points[:10],first_bad_midpoints=bad_midpoints[:10],
            total_fiber_length_m=float(lengths.sum()),shortest_segment_m=float(lengths.min()),
            section_area_m2=float(np.pi*.001**2/4),fiber_volume_m3=float(lengths.sum()*np.pi*.001**2/4))
Path(sys.argv[2]).write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
if bad_points or bad_midpoints:sys.exit(1)
