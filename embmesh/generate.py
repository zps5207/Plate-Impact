from __future__ import annotations
import numpy as np
from .parser import parse_deck
from .selection import select_elements
from .fibers import flat_disc_fibers
from .volume import fiber_volume_rows
from .writers import write_volume_csv, write_report, write_vtk, append_fibers_to_deck
from .geometry import point_in_hex

def mesh_flat(deck_path, instance, diameter, output_dir, elset=None, gap=0., fiber_type="truss", reference=(1,0,0)):
    d=parse_deck(deck_path); elems,nodes=select_elements(d,instance,elset); fibers=flat_disc_fibers(nodes,diameter,gap=gap,reference=reference)
    out=__import__('pathlib').Path(output_dir); out.mkdir(parents=True,exist_ok=True)
    rows=fiber_volume_rows(elems,nodes,fibers,diameter); write_volume_csv(out/'fiber_volume.csv',rows)
    inside=sum(1 for f in fibers for p in f.points if any(point_in_hex(p,[nodes[i] for i in e.connectivity[:8]]) for e in elems.values()))
    stable_dt=None
    # Longitudinal wave estimate for a fiber segment (units follow the input deck).
    if fibers:
      stable_dt=min((np.linalg.norm(f.points[-1]-f.points[0]) for f in fibers),default=0.)
    write_report(out/'report.json',fiber_count=len(fibers),host_count=len(elems),total_fiber_volume=sum(r[2] for r in rows),volume_fraction_min=min((r[3] for r in rows),default=0),volume_fraction_max=max((r[3] for r in rows),default=0),embedded_endpoints_inside=inside,embedded_endpoint_total=2*len(fibers),estimated_stable_time_increment=stable_dt)
    write_vtk(out/'fibers.vtk',fibers)
    append_fibers_to_deck('\n'.join(d.original_lines),out/'output.inp',fibers,fiber_type,diameter,host_elset=elset or 'HOST')
    return fibers,rows
