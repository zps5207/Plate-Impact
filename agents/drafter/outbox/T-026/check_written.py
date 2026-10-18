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
from embmesh.geometry import HEX_FACES

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
ends=np.array([(fibnodes[e.connectivity[0]],fibnodes[e.connectivity[1]]) for e in fiber_elements])
interior=np.array([[(1-t)*a+t*b for t in (1/6,2/6,3/6,4/6,5/6)] for a,b in ends])
midpoints=interior[:,2]
hexes=np.array([[world[n] for n in e.connectivity[:8]] for e in host.values()])
lo=hexes.min(1);hi=hexes.max(1)
tree=cKDTree(hexes.mean(1))

def point_segment_distance(p,a,b):
    v=b-a
    t=np.clip(np.dot(p-a,v)/np.dot(v,v),0.,1.)
    return float(np.linalg.norm(p-(a+t*v)))

def point_triangle_distance(p,a,b,c):
    n=np.cross(b-a,c-a)
    norm=np.linalg.norm(n)
    if norm<1e-15:return min(point_segment_distance(p,a,b),point_segment_distance(p,b,c),point_segment_distance(p,c,a))
    projected=p-n*(np.dot(p-a,n)/(norm*norm))
    u=b-a;v=c-a;w=projected-a
    d00=np.dot(u,u);d01=np.dot(u,v);d11=np.dot(v,v);d20=np.dot(w,u);d21=np.dot(w,v)
    denom=d00*d11-d01*d01
    if abs(denom)>1e-20:
        beta=(d11*d20-d01*d21)/denom;gamma=(d00*d21-d01*d20)/denom
        if beta>=0 and gamma>=0 and beta+gamma<=1:
            return float(abs(np.dot(p-a,n))/norm)
    return min(point_segment_distance(p,a,b),point_segment_distance(p,b,c),point_segment_distance(p,c,a))

def distance_to_hex(p,h):
    return min(point_triangle_distance(p,h[f[0]],h[f[1]],h[f[2]]) if tri==0 else
               point_triangle_distance(p,h[f[0]],h[f[2]],h[f[3]])
               for f in HEX_FACES for tri in (0,1))

def audit(samples):
    bad=[]
    max_distance=0.
    for i,p in enumerate(samples):
        _,ids=tree.query(p,k=32)
        if not any(np.all(p>=lo[j]-1e-9) and np.all(p<=hi[j]+1e-9) and point_in_hex(p,hexes[j]) for j in ids):
            bad.append(i)
            max_distance=max(max_distance,min(distance_to_hex(p,hexes[j]) for j in ids))
    return bad,max_distance

bad_points,node_distance=audit(points)
bad_midpoints,midpoint_distance=audit(midpoints)
bad_interior,interior_distance=audit(interior.reshape(-1,3))
lengths=np.array([np.linalg.norm(fibnodes[e.connectivity[1]]-fibnodes[e.connectivity[0]]) for e in fiber_elements])
fiber_segment_lengths=[];current=[];previous_end=None
for e,length in zip(fiber_elements,lengths):
    a,b=e.connectivity
    if previous_end is not None and a!=previous_end:
        fiber_segment_lengths.append(np.asarray(current));current=[]
    current.append(length);previous_end=b
if current:fiber_segment_lengths.append(np.asarray(current))
spread=max((float(np.ptp(x)/np.median(x)) for x in fiber_segment_lengths),default=0.)
report=json.loads(Path(sys.argv[1]).with_name('report.json').read_text())
target=report.get('target_segment_length_m')
result=dict(hosts=len(host),fibers=len(points)-len(fiber_elements),
            fiber_nodes=len(points),fiber_segments=len(fiber_elements),vertices_outside=len(bad_points),
            midpoints_outside=len(bad_midpoints),first_bad_vertices=bad_points[:10],first_bad_midpoints=bad_midpoints[:10],
            five_interior_samples_per_segment=len(interior.reshape(-1,3)),interior_samples_outside=len(bad_interior),
            max_sample_outside_distance_m=max(node_distance,interior_distance),
            max_sample_outside_distance_um=1e6*max(node_distance,interior_distance),
            max_sample_outside_distance_over_d=max(node_distance,interior_distance)/.001,
            total_fiber_length_m=float(lengths.sum()),shortest_segment_m=float(lengths.min()),
            longest_segment_m=float(lengths.max()),per_fiber_segment_spread_max_relative=spread,
            segment_length_over_target_min=float(lengths.min()/target) if target else None,
            segment_length_over_target_median=float(np.median(lengths)/target) if target else None,
            segment_length_over_target_max=float(lengths.max()/target) if target else None,
            section_area_m2=float(np.pi*.001**2/4),fiber_volume_m3=float(lengths.sum()*np.pi*.001**2/4))
Path(sys.argv[2]).write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
if bad_points:sys.exit(1)
