from __future__ import annotations
import csv,json
from pathlib import Path
import numpy as np

def write_volume_csv(path, rows):
    with open(path,"w",newline="") as f:
        w=csv.writer(f); w.writerow(["element_label","host_volume","fiber_volume","volume_fraction","length_t0","length_t90"]); w.writerows(rows)

def write_report(path, **data): Path(path).write_text(json.dumps(data,indent=2,sort_keys=True))

def write_vtk(path,fibers, fractions=None):
    points=[]; lines=[]
    for f in fibers:
      i=len(points); points.extend(f.points.tolist()); lines.append((i,i+1))
    with open(path,"w") as h:
      h.write("# vtk DataFile Version 3.0\nembmesh fibers\nASCII\nDATASET POLYDATA\n")
      h.write(f"POINTS {len(points)} float\n"+"\n".join("%g %g %g"%tuple(p) for p in points)+"\n")
      h.write(f"LINES {len(lines)} {3*len(lines)}\n"+"\n".join(f"2 {a} {b}" for a,b in lines)+"\n")

def append_fibers_to_deck(original, path, fibers, fiber_type="truss", diameter=1.0, node_offset=100000, element_offset=100000, host_elset="HOST"):
    typ="T3D2" if fiber_type=="truss" else "B31"; out=list(original.splitlines())
    max_node=max_elem=0; sec=''
    for line in out:
      s=line.strip()
      if s.startswith('*'): sec=s.lower()
      elif s and not s.startswith('**'):
        try:
          n=int(s.split(',')[0]);
          if sec.startswith('*node'): max_node=max(max_node,n)
          if sec.startswith('*element'): max_elem=max(max_elem,n)
        except ValueError: pass
    if node_offset<=max_node: raise ValueError(f"fiber node offset {node_offset} collides with existing maximum {max_node}")
    if element_offset<=max_elem: raise ValueError(f"fiber element offset {element_offset} collides with existing maximum {max_elem}")
    nodes=[]; elems=[]; nid=node_offset; eid=element_offset
    for f in fibers:
      ids=[]
      for p in f.points: nodes.append((nid,p)); ids.append(nid); nid+=1
      elems.append((eid,ids)); eid+=1
    out += ["** embmesh generated fibers", "*Node, nset=EMBMESH_NODES"] + [f"{i}, {p[0]:.12g}, {p[1]:.12g}, {p[2]:.12g}" for i,p in nodes]
    out += [f"*Element, type={typ}, elset=EMBMESH_FIBERS"] + [f"{i}, {','.join(map(str,c))}" for i,c in elems]
    if fiber_type=="truss": out += ["*Solid Section, elset=EMBMESH_FIBERS, material=EMBMESH_FIBER", f"{np.pi*diameter**2/4:.15g}"]
    else:
      axis=np.asarray(fibers[0].points[-1]-fibers[0].points[0],float); axis/=np.linalg.norm(axis)
      ref=np.array([0.,0.,1.]);
      if abs(axis@ref)>.9: ref=np.array([0.,1.,0.])
      n1=np.cross(axis,ref); n1/=np.linalg.norm(n1)
      out += ["*Beam Section, elset=EMBMESH_FIBERS, material=EMBMESH_FIBER, section=CIRC", f"{diameter/2:.15g}, {n1[0]:.15g}, {n1[1]:.15g}, {n1[2]:.15g}"]
    out += ["*Material, name=EMBMESH_FIBER", "*Elastic", "1., 0.3", f"*Embedded Element, host elset={host_elset}"]
    out += ["EMBMESH_FIBERS"]
    Path(path).write_text("\n".join(out)+"\n")
