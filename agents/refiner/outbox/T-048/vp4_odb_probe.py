"""Read-only, bounded vp4 ODB extraction. Run under Abaqus Python on ROAR.

    abaqus python vp4_odb_probe.py /path/vals_native.odb native

Outputs PREFIX_fiber_status.npz (200 frames aligned to existing viewer export),
PREFIX_early_fields.csv (0-10 us elements near impact), PREFIX_elements.csv,
and PREFIX_odb_inventory.json (field/history keys and warning node sets).
No ODB writes or solver jobs are performed.
"""

from __future__ import print_function

import csv
import json
import sys

import numpy as np
from odbAccess import openOdb


FIELD_KEYS = ('STATUS', 'S', 'LE', 'PEEQ', 'DUCTCRT', 'DMICRT', 'SDEG', 'SDV')
WINDOW_END = 10.0e-6
ROI_XY = (-0.001, 0.011)
ROI_Z = (-0.006, 0.001)


def flatten(container):
    if hasattr(container, 'label'):
        yield container
        return
    for item in container:
        for obj in flatten(item):
            yield obj


def data_list(value):
    try:
        return [float(x) for x in value]
    except TypeError:
        return [float(value)]


def role(name):
    if name.startswith('FIBERS-PLY-'):
        return 'fiber'
    if name.startswith('PLY-'):
        return 'host'
    if name == 'BALL-1':
        return 'ball'
    return None


def build_mesh_index(root):
    selected = set()
    rows = []
    fiber_order = []
    for inst_name in sorted(root.instances.keys()):
        kind = role(inst_name)
        if kind is None:
            continue
        instance = root.instances[inst_name]
        coords = dict((int(n.label), n.coordinates) for n in instance.nodes)
        if kind == 'fiber':
            # Use the exact FIBERS set and ordering rule used by export_odb_viewer.py.
            elements = sorted(flatten(instance.elementSets['FIBERS'].elements),
                              key=lambda e: e.label)
        else:
            elements = sorted(instance.elements, key=lambda e: e.label)
        for element in elements:
            points = np.asarray([coords[int(n)] for n in element.connectivity], dtype=float)
            center = points.mean(axis=0)
            if kind == 'fiber':
                fiber_order.append((inst_name, int(element.label)))
            within_xy = all(ROI_XY[0] <= center[j] <= ROI_XY[1] for j in (0, 1))
            within_z = ROI_Z[0] <= center[2] <= ROI_Z[1]
            if within_xy and (within_z or kind == 'ball'):
                selected.add((inst_name, int(element.label)))
                rows.append((kind, inst_name, int(element.label), str(element.type),
                             float(center[0]), float(center[1]), float(center[2])))
    return selected, rows, fiber_order


def warning_node_sets(root):
    result = {}
    for name, node_set in root.nodeSets.items():
        if not any(x in name.upper() for x in ('PINCH', 'OVER', 'PENET')):
            continue
        nodes = []
        for node in flatten(node_set.nodes):
            instance = getattr(node, 'instanceName', None)
            nodes.append({'instance': str(instance), 'label': int(node.label),
                          'coordinates': data_list(node.coordinates)})
        result[name] = {'count': len(nodes), 'sample': nodes[:30]}
    return result


def extract(odb_path, prefix):
    odb = openOdb(path=odb_path, readOnly=True)
    try:
        step = odb.steps['Step-1']
        selected, mesh_rows, fiber_order = build_mesh_index(odb.rootAssembly)
        print('selected ROI elements:', len(selected), 'total fibers:', len(fiber_order))
        with open(prefix + '_elements.csv', 'w', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(('role', 'instance', 'element_label', 'type', 'x_m', 'y_m', 'z_m'))
            writer.writerows(mesh_rows)

        nframes = len(step.frames)
        sample_indices = sorted(set(int(round(x)) for x in np.linspace(0, nframes - 1, 200)))
        sample_lookup = dict((index, i) for i, index in enumerate(sample_indices))
        fiber_status = np.ones((len(sample_indices), len(fiber_order)), dtype=np.uint8)
        fiber_time = np.zeros(len(sample_indices), dtype=float)
        fiber_by_instance = {}
        for col, (inst_name, label) in enumerate(fiber_order):
            fiber_by_instance.setdefault(inst_name, {})[label] = col
        has_fiber_status = False

        inventory = {
            'odb': odb_path, 'step': step.name, 'total_frames': nframes,
            'roi': {'xy_m': ROI_XY, 'z_m': ROI_Z, 'end_time_s': WINDOW_END},
            'roi_element_counts': {}, 'field_keys': {}, 'history_keys': {},
            'warning_node_sets': warning_node_sets(odb.rootAssembly),
        }
        for kind, _, _, _, _, _, _ in mesh_rows:
            inventory['roi_element_counts'][kind] = inventory['roi_element_counts'].get(kind, 0) + 1
        for region_name, region in step.historyRegions.items():
            inventory['history_keys'][region_name] = list(region.historyOutputs.keys())
            if 'ASSEMBLY' in region_name.upper():
                inventory.setdefault('assembly_histories', {})[region_name] = dict(
                    (key, [[float(t), float(v)] for t, v in output.data])
                    for key, output in region.historyOutputs.items()
                )

        with open(prefix + '_early_fields.csv', 'w', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(('frame', 'time_us', 'field', 'role', 'instance',
                             'element_label', 'position', 'integration_point', 'data'))
            for frame_index, frame in enumerate(step.frames):
                early = frame.frameValue <= WINDOW_END
                sampled = frame_index in sample_lookup
                if not early and not sampled:
                    continue
                inventory['field_keys'][str(frame_index)] = list(frame.fieldOutputs.keys())

                if sampled:
                    out_index = sample_lookup[frame_index]
                    fiber_time[out_index] = float(frame.frameValue)
                    if out_index:
                        fiber_status[out_index] = fiber_status[out_index - 1]
                    if 'STATUS' in frame.fieldOutputs:
                        for block in frame.fieldOutputs['STATUS'].bulkDataBlocks:
                            inst_name = block.instance.name
                            labels_to_col = fiber_by_instance.get(inst_name)
                            if not labels_to_col:
                                continue
                            has_fiber_status = True
                            labels = np.asarray(block.elementLabels, dtype=np.int64)
                            values = np.asarray(block.data).reshape(len(labels), -1).min(axis=1)
                            for label, value in zip(labels, values):
                                col = labels_to_col.get(int(label))
                                if col is not None:
                                    if value < 0.5:
                                        fiber_status[out_index, col] = 0

                if early:
                    for key in FIELD_KEYS:
                        if key not in frame.fieldOutputs:
                            continue
                        field = frame.fieldOutputs[key]
                        for value in field.values:
                            if not hasattr(value, 'elementLabel'):
                                continue
                            inst_name = value.instance.name
                            label = int(value.elementLabel)
                            if (inst_name, label) not in selected:
                                continue
                            writer.writerow((frame_index, float(frame.frameValue) * 1e6,
                                             key, role(inst_name), inst_name, label,
                                             str(value.position),
                                             getattr(value, 'integrationPoint', ''),
                                             json.dumps(data_list(value.data))))
                if frame_index % 100 == 0:
                    print('frame', frame_index, '/', nframes - 1)

        inventory['fiber_status_field_present'] = has_fiber_status
        inventory['sampled_frame_indices'] = sample_indices
        with open(prefix + '_odb_inventory.json', 'w') as stream:
            json.dump(inventory, stream, sort_keys=True, indent=2)
        np.savez_compressed(prefix + '_fiber_status.npz',
                            fiber_status=fiber_status, times=fiber_time,
                            status_field_present=np.asarray(has_fiber_status),
                            frame_indices=np.asarray(sample_indices),
                            fiber_order=np.asarray(fiber_order))
        print('wrote', prefix, 'fiber status present:', has_fiber_status)
    finally:
        odb.close()


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('Usage: abaqus python vp4_odb_probe.py INPUT.odb OUTPUT_PREFIX')
    extract(sys.argv[1], sys.argv[2])
