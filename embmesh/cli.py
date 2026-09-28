from __future__ import annotations
import argparse
from .parser import parse_deck

def main(argv=None):
    p=argparse.ArgumentParser(prog="embmesh"); sub=p.add_subparsers(dest="cmd",required=True)
    q=sub.add_parser("list"); q.add_argument("deck")
    a=p.parse_args(argv)
    if a.cmd=="list":
      d=parse_deck(a.deck)
      for n,part in d.parts.items():
        types={}
        for e in part.elements.values(): types[e.type.upper()]=types.get(e.type.upper(),0)+1
        lo,hi=part.bbox(); print(f"part {n}: nodes={len(part.nodes)} elements={len(part.elements)} types={types} bbox={lo.tolist()}..{hi.tolist()} sets={sorted(set(part.nsets)|set(part.elsets))} surfaces={sorted(part.surfaces)}")
      for n,i in d.instances.items(): print(f"instance {n}: part={i.part} translation={i.translation.tolist()} rotation_angle={i.rotation_angle:g}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
