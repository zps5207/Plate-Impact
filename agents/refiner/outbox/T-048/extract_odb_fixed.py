"""Read-only Abaqus ODB extraction for T-048.

Run with Abaqus Python, e.g.:
    abaqus python extract_odb.py /path/t046_sol1.odb /path/t046_sol1.json

Compatible with Abaqus Python 2.7 or 3.x; uses only the standard library and
odbAccess. The output is JSON so element labels, frames, and field data remain
available for independent review.
"""

from __future__ import print_function

import json
import os
import sys

from odbAccess import openOdb


WANTED_FIELDS = (
    'STATUS', 'S', 'LE', 'PEEQ', 'DUCTCRT', 'DMICRT', 'SDEG',
    'U', 'V', 'A', 'RF', 'MASS',
)


def plain(value):
    if isinstance(value, (list, tuple)):
        return [plain(item) for item in value]
    try:
        return float(value)
    except (TypeError, ValueError):
        return str(value)


def extract_field(field):
    result = []
    for value in field.values:
        item = {'data': plain(value.data)}
        if hasattr(value, 'instance') and value.instance is not None:
            item['instance'] = value.instance.name
        if getattr(value, 'elementLabel', None) is not None:
            item['elementLabel'] = int(value.elementLabel)
        if getattr(value, 'nodeLabel', None) is not None:
            item['nodeLabel'] = int(value.nodeLabel)
        if getattr(value, 'integrationPoint', None) is not None:
            item['integrationPoint'] = int(value.integrationPoint)
        if hasattr(value, 'sectionPoint') and value.sectionPoint is not None:
            item['sectionPoint'] = str(value.sectionPoint)
        result.append(item)
    return result


def main():
    if len(sys.argv) != 3:
        sys.stderr.write('Usage: abaqus python extract_odb.py INPUT.odb OUTPUT.json\n')
        return 2
    odb_path, output_path = sys.argv[1:]
    odb = openOdb(path=odb_path, readOnly=True)
    try:
        result = {
            'source_odb': os.path.basename(odb_path),
            'instances': {},
            'steps': [],
        }
        for name, instance in odb.rootAssembly.instances.items():
            result['instances'][name] = {
                'elements': [
                    {'label': int(element.label), 'type': str(element.type),
                     'connectivity': [int(x) for x in element.connectivity]}
                    for element in instance.elements
                ],
                'nodes': [
                    {'label': int(node.label), 'coordinates': plain(node.coordinates)}
                    for node in instance.nodes
                ],
                'elementSets': dict(
                    (set_name, [int(e.label) for e in element_set.elements])
                    for set_name, element_set in instance.elementSets.items()
                ),
            }
        for step_name, step in odb.steps.items():
            step_data = {
                'name': step_name,
                'frames': [],
                'historyRegions': {},
            }
            for region_name, region in step.historyRegions.items():
                step_data['historyRegions'][region_name] = dict(
                    (key, [[float(time), plain(value)] for time, value in history.data])
                    for key, history in region.historyOutputs.items()
                )
            for index, frame in enumerate(step.frames):
                fields = {}
                for key in WANTED_FIELDS:
                    if key in frame.fieldOutputs:
                        fields[key] = extract_field(frame.fieldOutputs[key])
                step_data['frames'].append({
                    'index': index,
                    'time': float(frame.frameValue),
                    'availableFields': list(frame.fieldOutputs.keys()),
                    'fields': fields,
                })
            result['steps'].append(step_data)
        with open(output_path, 'w') as stream:
            json.dump(result, stream, sort_keys=True, separators=(',', ':'))
        print('Wrote %s: %d step(s)' % (output_path, len(result['steps'])))
    finally:
        odb.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
