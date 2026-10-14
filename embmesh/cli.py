from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from .parser import parse_deck
from .generate import mesh
from .errors import HexOnlyError, MesherInputError
from .vuelghost import VuelGhostOptions


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
    v.add_argument("--host-mode", choices=("native", "vuel-ghost"), default="native",
                   help="retain native C3D8R hosts (default), or emit VU1 real hosts plus node-coincident C3D8R ghosts")
    v.add_argument("--ghost-scale", type=float, default=1e-4,
                   help="scale ghost density, modulus, and plastic stresses together (default: 1e-4)")
    v.add_argument("--ghost-ductile-failure-strain", type=float,
                   help="strictly positive override for the ghost's cloned ductile initiation strain (default: retain host value)")
    v.add_argument("--vuel-eps-fail", type=float,
                   help="VU1 engineering-strain failure threshold (default: host ductile initiation strain)")
    v.add_argument("--vuel-yield-stress", type=float,
                   help="VU1 initial yield stress (default: first host *Plastic stress)")
    v.add_argument("--vuel-hardening-modulus", type=float,
                   help="VU1 linear hardening modulus (default: slope of the first two host *Plastic points)")
    v.add_argument("--vuel-jac-fail", type=float, default=0.05,
                   help="VU1 det(F) collapse threshold (default: 0.05)")
    v.add_argument("--vuel-degrade-time", type=float, default=0.0,
                   help="VU1 post-trigger linear degradation time (default: immediate)")
    v.add_argument("--vuel-compression-residual", type=float, default=0.0,
                   help="VU1 residual compression-only bulk fraction, 0..1 (default: 0)")
    v.add_argument("--plate-node-contact", action="store_true",
                   help="contact the ball with a node surface over every host-instance node")
    v.add_argument("--fiber-node-contact", action="store_true",
                   help="contact the ball with a node surface over every generated fiber node")
    v.add_argument("--ball-instance",
                   help="assembly instance used to build the ball exterior surface (required with node contact)")
    v.add_argument("--contact-thickness", default="auto",
                   help="node-surface contact thickness in deck units, or auto (default: auto)")
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

            vuel_options = VuelGhostOptions(
                ghost_scale=a.ghost_scale,
                ghost_ductile_failure_strain=a.ghost_ductile_failure_strain,
                eps_fail=a.vuel_eps_fail,
                sigy0=a.vuel_yield_stress, hardening_modulus=a.vuel_hardening_modulus,
                jac_fail=a.vuel_jac_fail, degrade_time=a.vuel_degrade_time,
                compression_residual_bulk_fraction=a.vuel_compression_residual)
            fibers, rows = mesh(a.deck, a.instance, a.diameter, a.output, elset=a.elset, gap=a.gap,
                                 fiber_type=a.fiber_type, preview=a.preview, thickness_axis=a.thickness_axis,
                                 curved=a.curved, curve_axis_point=a.curve_axis_point, curve_axis_dir=a.curve_axis_dir,
                                 curve_center=a.curve_center, curve_pole_axis=a.curve_pole_axis,
                                 node_offset=a.node_offset, element_offset=a.element_offset,
                                 fiber_material=a.fiber_material, precise_volume=a.precise_volume,
                                 host_mode=a.host_mode, vuel_ghost_options=vuel_options,
                                 plate_node_contact=a.plate_node_contact,
                                 fiber_node_contact=a.fiber_node_contact,
                                 ball_instance=a.ball_instance,
                                 contact_thickness=a.contact_thickness,
                                 progress=progress)
            print(f"patched deck: {a.output}/output.inp")
            print(f"host/fiber VTK: {a.output}/host_fibers.vtk")
            if a.preview: print(f"preview: {a.output}/preview.html")
            if a.precise_volume: print(f"precise per-host volumes: {a.output}/fiber_volume_precise.csv")
            print(f"fibers: {len(fibers)}; host elements: {len(rows)}")
            if a.plate_node_contact or a.fiber_node_contact:
                report = json.loads(Path(a.output, 'report.json').read_text())
                contact = report['ball_node_contact']
                surfaces = [x for x in (contact['plate_surface'], contact['fiber_surface']) if x]
                print(f"ball contact: {', '.join(surfaces)} -> {contact['ball_surface']}")
                print(f"contact nodes: plate={contact['plate_node_count']} fibers={contact['fiber_node_count']}")
                print(f"contact thickness: plate={contact['plate_contact_thickness']} fibers={contact['fiber_contact_thickness']}")
                action = 'reused' if contact['interaction_reused'] else 'created'
                print(f"contact interaction: {contact['interaction']} ({action})")
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
