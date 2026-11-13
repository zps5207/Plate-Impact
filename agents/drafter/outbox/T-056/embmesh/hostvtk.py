from __future__ import annotations
import numpy as np

HEX_EDGES = ((0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4), (0, 4), (1, 5), (2, 6), (3, 7))

def write_host_fiber_vtk(path, elements, nodes, fibers, fractions=None):
    points=[]; lines=[]; values=[]
    for label, element in elements.items():
        ids=[]
        for node in element.connectivity[:8]: ids.append(len(points)); points.append(np.asarray(nodes[node],float))
        for a,b in HEX_EDGES: lines.append((ids[a],ids[b])); values.append(float((fractions or {}).get(label,0.)))
    for fiber in fibers:
        start=len(points); pts=np.asarray(fiber.points,float); points.extend(pts.tolist())
        for k in range(len(pts)-1): lines.append((start+k,start+k+1)); values.append(-1.)
    with open(path,'w',encoding='utf-8') as f:
        f.write('# vtk DataFile Version 3.0\nembmesh host/fiber visualization\nASCII\nDATASET POLYDATA\n')
        f.write(f'POINTS {len(points)} float\n'+'\n'.join('%.12g %.12g %.12g'%tuple(p) for p in points)+'\n')
        f.write(f'LINES {len(lines)} {3*len(lines)}\n'+'\n'.join(f'2 {a} {b}' for a,b in lines)+'\n')
        f.write(f'CELL_DATA {len(lines)}\nSCALARS host_volume_fraction float 1\nLOOKUP_TABLE default\n'+'\n'.join('%.12g'%x for x in values)+'\n')
