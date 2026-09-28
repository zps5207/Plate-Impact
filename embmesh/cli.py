from __future__ import annotations
import argparse
from .parser import parse_deck
from .generate import mesh_flat

def main(argv=None):
    p=argparse.ArgumentParser(prog="embmesh"); sub=p.add_subparsers(dest="cmd",required=True)
    q=sub.add_parser("list"); q.add_argument("deck")
    v=sub.add_parser("visualize", help="mesh fibers, preserve the deck, and render host/fiber geometry")
    v.add_argument("deck"); v.add_argument("--instance", required=True); v.add_argument("--diameter", type=float, required=True)
    v.add_argument("--output", required=True); v.add_argument("--elset"); v.add_argument("--gap", type=float, default=0.0)
    v.add_argument("--fiber-type", choices=("truss", "beam"), default="truss")
    v.add_argument("--preview", action="store_true", help="also render a PNG (requires matplotlib)")
    a=p.parse_args(argv)
    if a.cmd=="list":
      d=parse_deck(a.deck)
      for n,part in d.parts.items():
        types={}
        for e in part.elements.values(): types[e.type.upper()]=types.get(e.type.upper(),0)+1
        lo,hi=part.bbox(); print(f"part {n}: nodes={len(part.nodes)} elements={len(part.elements)} types={types} bbox={lo.tolist()}..{hi.tolist()} sets={sorted(set(part.nsets)|set(part.elsets))} surfaces={sorted(part.surfaces)}")
      for n,i in d.instances.items(): print(f"instance {n}: part={i.part} translation={i.translation.tolist()} rotation_angle={i.rotation_angle:g}")
    elif a.cmd == "visualize":
      fibers, rows = mesh_flat(a.deck, a.instance, a.diameter, a.output, a.elset, a.gap, a.fiber_type, preview=a.preview)
      print(f"patched deck: {a.output}/output.inp")
      print(f"host/fiber VTK: {a.output}/host_fibers.vtk")
      if a.preview: print(f"preview: {a.output}/preview.png")
      print(f"fibers: {len(fibers)}; host elements: {len(rows)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
