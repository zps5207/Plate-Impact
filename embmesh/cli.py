from __future__ import annotations
import argparse
import sys
from .parser import parse_deck
from .generate import mesh
from .errors import HexOnlyError, MesherInputError


def _vec3(s):
    v = [float(x) for x in s.split(",")]
    if len(v) != 3:
        raise argparse.ArgumentTypeError(f"expected 3 comma-separated numbers, got {s!r}")
    return v


def build_parser():
    p = argparse.ArgumentParser(prog="embmesh")
    sub = p.add_subparsers(dest="cmd", required=True)
    q = sub.add_parser("list"); q.add_argument("deck")
    v = sub.add_parser("visualize", help="mesh fibers, preserve the deck, and render host/fiber geometry")
    v.add_argument("deck"); v.add_argument("--instance", required=True); v.add_argument("--diameter", type=float, required=True)
    v.add_argument("--output", required=True); v.add_argument("--elset"); v.add_argument("--gap", type=float, default=0.0)
    v.add_argument("--fiber-type", choices=("truss", "beam"), default="truss")
    v.add_argument("--preview", action="store_true",
                    help="also render an interactive, rotatable HTML preview (requires plotly)")
    v.add_argument("--thickness-axis", help="flat/box layup only: 'x', 'y', 'z', or 'dx,dy,dz'; "
                                             "auto-detected from the host bounding box if omitted")
    v.add_argument("--curved", choices=("flat", "cylindrical", "spherical"), default="flat",
                    help="layup family: flat plate/box/cube (default), a plate curved about a single "
                         "axis, or a spherically curved plate")
    v.add_argument("--curve-axis-point", type=_vec3, default=[0, 0, 0], help="cylindrical: a point on the curve axis, 'x,y,z'")
    v.add_argument("--curve-axis-dir", type=_vec3, default=[0, 0, 1], help="cylindrical: the curve axis direction, 'dx,dy,dz'")
    v.add_argument("--curve-center", type=_vec3, default=[0, 0, 0], help="spherical: the sphere center, 'x,y,z'")
    v.add_argument("--curve-pole-axis", type=_vec3, default=[0, 0, 1],
                    help="spherical: the pole axis for the meridian/latitude parametrization "
                         "(pick whichever axis is most representative of the shell), 'dx,dy,dz'")
    v.add_argument("--node-offset", type=int, default=100000, help="first generated fiber node label")
    v.add_argument("--element-offset", type=int, default=100000, help="first generated fiber element label")
    v.add_argument("--fiber-material", default="Fiber",
                    help="name of the material already defined in the input deck (default: Fiber)")
    v.add_argument("--precise-volume", action="store_true",
                    help="also write fiber_volume_precise.csv using true cross-section-weighted "
                         "cylinder/hex intersection volume instead of the default centerline-length "
                         "x area approximation (slower; most useful near host boundaries or when the "
                         "host size approaches the fiber pitch)")
    return p


def main(argv=None):
    p = build_parser()
    a = p.parse_args(argv)
    try:
        if a.cmd == "list":
            d = parse_deck(a.deck)
            for n, part in d.parts.items():
                types = {}
                for e in part.elements.values(): types[e.type.upper()] = types.get(e.type.upper(), 0) + 1
                lo, hi = part.bbox()
                print(f"part {n}: nodes={len(part.nodes)} elements={len(part.elements)} types={types} "
                      f"bbox={lo.tolist()}..{hi.tolist()} sets={sorted(set(part.nsets)|set(part.elsets))} surfaces={sorted(part.surfaces)}")
            for n, i in d.instances.items():
                print(f"instance {n}: part={i.part} translation={i.translation.tolist()} rotation_angle={i.rotation_angle:g}")
        elif a.cmd == "visualize":
            def progress(percent, message):
                print(f"PROGRESS {percent} {message}", flush=True)

            fibers, rows = mesh(a.deck, a.instance, a.diameter, a.output, elset=a.elset, gap=a.gap,
                                 fiber_type=a.fiber_type, preview=a.preview, thickness_axis=a.thickness_axis,
                                 curved=a.curved, curve_axis_point=a.curve_axis_point, curve_axis_dir=a.curve_axis_dir,
                                 curve_center=a.curve_center, curve_pole_axis=a.curve_pole_axis,
                                 node_offset=a.node_offset, element_offset=a.element_offset,
                                 fiber_material=a.fiber_material, precise_volume=a.precise_volume,
                                 progress=progress)
            print(f"patched deck: {a.output}/output.inp")
            print(f"host/fiber VTK: {a.output}/host_fibers.vtk")
            if a.preview: print(f"preview: {a.output}/preview.html")
            if a.precise_volume: print(f"precise per-host volumes: {a.output}/fiber_volume_precise.csv")
            print(f"fibers: {len(fibers)}; host elements: {len(rows)}")
        return 0
    except FileNotFoundError as e:
        print(f"embmesh: {e}", file=sys.stderr); return 2
    except HexOnlyError as e:
        print(f"embmesh: {e}", file=sys.stderr); return 3
    except KeyError as e:
        print(f"embmesh: not found: {e}", file=sys.stderr); return 4
    except (ValueError, MesherInputError) as e:
        print(f"embmesh: {e}", file=sys.stderr); return 5


if __name__ == "__main__":
    raise SystemExit(main())
