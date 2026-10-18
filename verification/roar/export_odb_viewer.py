"""Export ODB geometry and motion for the interactive HTML viewer.

Run where Abaqus is installed (the ODB format needs odbAccess):
    abaqus python export_odb_viewer.py job.odb --output job_viewer.npz \
        --start-time 0 --end-time 7e-5 --frame-count 150

Writes one compressed .npz with three roles, each with its own node list:
    host  - the ghost host elements (set EMBMESH_GHOST_DIAGNOSTICS), with per-frame STATUS
    ball  - every element of the impactor instance
    fiber - the fiber elements (element sets EMBMESH_FIBERS_T0 / _T90 of EMBFIB-1)
Per role: <role>_coords0 (n,3), <role>_pos (frames,n,3) deformed positions,
<role>_types (element type names), <role>_conn_<TYPE> (elements,k) node indices into the
role's node list. The host also has host_status (frames, elements) uint8, 1 = alive.
"""
from __future__ import print_function

import argparse
import json

import numpy as np
from odbAccess import openOdb

GHOST_ELSET = "EMBMESH_GHOST_DIAGNOSTICS"
PLATE_INSTANCE = "PLATE-1"
BALL_INSTANCE = "BALL-1"
FIBER_INSTANCE = "EMBFIB-1"
FIBER_ELSETS = ("EMBMESH_FIBERS_T0", "EMBMESH_FIBERS_T90")


def flatten_elements(container):
    """Yield mesh elements from an element-set payload (array, or tuple of arrays)."""
    if hasattr(container, "label") and hasattr(container, "connectivity"):
        yield container
        return
    for item in container:
        for element in flatten_elements(item):
            yield element


def evenly_sample(indices, count):
    if count <= 0 or count >= len(indices):
        return list(indices)
    positions = np.linspace(0, len(indices) - 1, count)
    return [indices[int(round(p))] for p in positions]


def build_role(odb, name, elements_by_instance):
    """elements_by_instance: {instance name: [OdbMeshElement,...]} -> role dict."""
    role = {"name": name, "node_instances": {}, "types": {}}
    labels_by_instance = {}
    for inst_name, elements in elements_by_instance.items():
        used = set()
        for element in elements:
            used.update(element.connectivity)
        labels_by_instance[inst_name] = np.array(sorted(used), dtype=np.int64)
    # one concatenated node list: instance blocks in sorted-name order
    offset = 0
    coords = []
    blocks = {}
    for inst_name in sorted(labels_by_instance):
        labels = labels_by_instance[inst_name]
        instance = odb.rootAssembly.instances[inst_name]
        table = {}
        for node in instance.nodes:
            table[node.label] = node.coordinates
        xyz = np.array([table[int(l)] for l in labels], dtype=np.float64).reshape(-1, 3)
        coords.append(xyz)
        blocks[inst_name] = (offset, labels)
        offset += len(labels)
    role["coords0"] = np.concatenate(coords, axis=0) if coords else np.zeros((0, 3))
    role["blocks"] = blocks
    order = []
    grouped = {}
    for inst_name in sorted(elements_by_instance):
        off, labels = blocks[inst_name]
        for element in elements_by_instance[inst_name]:
            local = [off + int(np.searchsorted(labels, c)) for c in element.connectivity]
            grouped.setdefault(str(element.type), []).append(local)
            order.append((inst_name, element.label, str(element.type)))
    role["conn"] = dict((t, np.array(c, dtype=np.int32)) for t, c in grouped.items())
    # element order = types sorted by name, elements in insertion order within a type
    ordered = []
    for t in sorted(grouped):
        ordered.extend([o for o in order if o[2] == t])
    role["element_order"] = ordered
    role["pos"] = None
    return role


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("odb")
    parser.add_argument("--output", default="viewer_export.npz")
    parser.add_argument("--step", default="Step-1")
    parser.add_argument("--start-time", type=float, default=0.0)
    parser.add_argument("--end-time", type=float, default=1.0e9)
    parser.add_argument("--frame-count", type=int, default=150)
    args = parser.parse_args()

    odb = openOdb(args.odb, readOnly=True)
    try:
        step = odb.steps[args.step]
        eligible = [i for i, f in enumerate(step.frames)
                    if args.start_time <= f.frameValue <= args.end_time]
        selected = evenly_sample(eligible, args.frame_count)
        times = np.array([step.frames[i].frameValue for i in selected])
        print("frames: %d eligible, %d selected" % (len(eligible), len(selected)))

        root = odb.rootAssembly
        host_by_instance = {}
        for element in flatten_elements(root.elementSets[GHOST_ELSET].elements):
            host_by_instance.setdefault(element.instanceName, []).append(element)
        ball_by_instance = {BALL_INSTANCE: list(root.instances[BALL_INSTANCE].elements)}
        if FIBER_INSTANCE in root.instances.keys():
            fiber_inst = root.instances[FIBER_INSTANCE]
            fiber_seen = {}
            for set_name in FIBER_ELSETS:
                for element in flatten_elements(fiber_inst.elementSets[set_name].elements):
                    fiber_seen[element.label] = element
            fiber_by_instance = {FIBER_INSTANCE: [fiber_seen[k] for k in sorted(fiber_seen)]}
        else:
            # plywise ODB: one Fibers-Ply-k instance per ply, all fibers in its FIBERS element set
            fiber_by_instance = {}
            for inst_name in sorted(root.instances.keys()):
                if inst_name.startswith("FIBERS-PLY-"):
                    elements = flatten_elements(root.instances[inst_name].elementSets["FIBERS"].elements)
                    fiber_by_instance[inst_name] = sorted(elements, key=lambda el: el.label)
            print("plywise ODB: %d fiber instances" % len(fiber_by_instance))

        roles = [
            build_role(odb, "host", host_by_instance),
            build_role(odb, "ball", ball_by_instance),
            build_role(odb, "fiber", fiber_by_instance),
        ]
        for role in roles:
            n = len(role["coords0"])
            role["pos"] = np.zeros((len(selected), n, 3), dtype=np.float32)
            print("role %s: %d nodes, element types %s" % (
                role["name"], n,
                dict((t, len(c)) for t, c in role["conn"].items())))
        host = roles[0]
        host_index = {}
        for i, (inst_name, label, _t) in enumerate(host["element_order"]):
            host_index[(inst_name, label)] = i
        status = np.ones((len(selected), len(host_index)), dtype=np.uint8)

        status_seen = False
        for f_out, frame_index in enumerate(selected):
            frame = step.frames[frame_index]
            for role in roles:
                role["pos"][f_out] = role["coords0"]
            u_blocks = frame.fieldOutputs["U"].bulkDataBlocks
            for block in u_blocks:
                inst_name = block.instance.name
                labels = np.asarray(block.nodeLabels)
                data = np.asarray(block.data)[:, :3]
                for role in roles:
                    if inst_name not in role["blocks"]:
                        continue
                    off, role_labels = role["blocks"][inst_name]
                    idx = np.searchsorted(role_labels, labels)
                    idx[idx >= len(role_labels)] = 0
                    ok = role_labels[idx] == labels
                    rows = off + idx[ok]
                    role["pos"][f_out, rows, :] = (
                        role["coords0"][rows] + data[ok]).astype(np.float32)
            if "STATUS" in frame.fieldOutputs:
                status_seen = True
                frame_status = {}
                for block in frame.fieldOutputs["STATUS"].bulkDataBlocks:
                    inst_name = block.instance.name
                    labels = np.asarray(block.elementLabels)
                    values = np.asarray(block.data).reshape(len(labels), -1).min(axis=1)
                    for label, value in zip(labels, values):
                        key = (inst_name, int(label))
                        frame_status[key] = min(frame_status.get(key, 1.0), float(value))
                for key, value in frame_status.items():
                    if key in host_index:
                        status[f_out, host_index[key]] = 1 if value >= 0.5 else 0
            if f_out % 25 == 0 or f_out + 1 == len(selected):
                print("frame %d/%d (t=%.3e)" % (f_out + 1, len(selected), frame.frameValue))
        if not status_seen:
            print("WARNING: no STATUS field in the selected frames; all host elements stay alive")

        out = {"times": times, "host_status": status,
               "meta": np.array(json.dumps({
                   "odb": args.odb, "step": args.step, "frames": selected,
                   "roles": [r["name"] for r in roles],
                   "types": dict((r["name"], sorted(r["conn"])) for r in roles),
               }))}
        for role in roles:
            out[role["name"] + "_coords0"] = role["coords0"].astype(np.float32)
            out[role["name"] + "_pos"] = role["pos"]
            for t, conn in role["conn"].items():
                out["%s_conn_%s" % (role["name"], t)] = conn
        np.savez_compressed(args.output, **out)
        print("wrote %s" % args.output)
    finally:
        odb.close()


if __name__ == "__main__":
    main()
