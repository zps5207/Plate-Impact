"""Extract whole-model Abaqus energy histories to a compact CSV.

Run on a machine with Abaqus, for example:

    abaqus python extract_energy_history.py flat_vg_r4.odb
"""
from __future__ import print_function

import argparse
import csv

from odbAccess import openOdb


REQUIRED_ENERGIES = ("ALLKE", "ALLIE", "ALLWK")
OPTIONAL_ENERGIES = ("ALLVD", "ETOTAL")


def repository_keys(repository):
    return [str(key) for key in repository.keys()]


def require_key(repository, requested, kind):
    keys = repository_keys(repository)
    lookup = dict((key.upper(), key) for key in keys)
    key = lookup.get(requested.upper())
    if key is None:
        raise RuntimeError(
            "{0} {1!r} was not found; available values: {2}".format(
                kind, requested, ", ".join(keys)))
    return key


def energy_region(step):
    """Return the assembly history region containing all required energies."""
    candidates = []
    inspected = []
    for region_key in repository_keys(step.historyRegions):
        region = step.historyRegions[region_key]
        outputs = repository_keys(region.historyOutputs)
        output_names = set(name.upper() for name in outputs)
        inspected.append((region_key, outputs))
        if ("ASSEMBLY" in region_key.upper()
                and all(name in output_names for name in REQUIRED_ENERGIES)):
            candidates.append((region_key, region))

    if not candidates:
        details = "; ".join(
            "{0}: [{1}]".format(key, ", ".join(outputs))
            for key, outputs in inspected)
        raise RuntimeError(
            "no assembly history region contains {0}; regions inspected: {1}".format(
                ", ".join(REQUIRED_ENERGIES), details))
    if len(candidates) > 1:
        raise RuntimeError(
            "multiple assembly history regions contain {0}: {1}".format(
                ", ".join(REQUIRED_ENERGIES),
                ", ".join(key for key, unused in candidates)))
    return candidates[0]


def output_lookup(region):
    keys = repository_keys(region.historyOutputs)
    return dict((key.upper(), key) for key in keys)


def aligned_energy_rows(region):
    """Return selected names and rows after enforcing one shared time grid."""
    lookup = output_lookup(region)
    names = list(REQUIRED_ENERGIES)
    names.extend(name for name in OPTIONAL_ENERGIES if name in lookup)

    series = {}
    for name in names:
        data = list(region.historyOutputs[lookup[name]].data)
        if not data:
            raise RuntimeError("history output {0} contains no samples".format(name))
        series[name] = data

    reference_name = REQUIRED_ENERGIES[0]
    reference = series[reference_name]
    for name in names[1:]:
        data = series[name]
        if len(data) != len(reference):
            raise RuntimeError(
                "history output {0} has {1} samples; {2} has {3}".format(
                    name, len(data), reference_name, len(reference)))
        for index, (reference_pair, pair) in enumerate(zip(reference, data)):
            reference_time = float(reference_pair[0])
            time_value = float(pair[0])
            tolerance = 1.0e-12 * max(1.0, abs(reference_time), abs(time_value))
            if abs(reference_time - time_value) > tolerance:
                raise RuntimeError(
                    "history time-grid mismatch at sample {0}: {1}={2}, {3}={4}".format(
                        index, reference_name, reference_time, name, time_value))

    rows = []
    for index, pair in enumerate(reference):
        row = [float(pair[0])]
        row.extend(float(series[name][index][1]) for name in names)
        rows.append(row)
    return names, rows


def extract(odb_path, step_requested, output_path):
    odb = openOdb(odb_path, readOnly=True)
    try:
        step_key = require_key(odb.steps, step_requested, "step")
        step = odb.steps[step_key]
        region_key, region = energy_region(step)
        names, rows = aligned_energy_rows(region)
        with open(output_path, "w") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(["time"] + names)
            writer.writerows(rows)
    finally:
        odb.close()
    return step_key, region_key, names, len(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Extract whole-model energy histories from an Abaqus ODB")
    parser.add_argument("odb")
    parser.add_argument("--step", default="Step-1")
    parser.add_argument("--output", default="energy_history.csv")
    args = parser.parse_args(argv)

    step, region, names, count = extract(args.odb, args.step, args.output)
    print("wrote {0} samples for {1} from {2}/{3} to {4}".format(
        count, ", ".join(names), step, region, args.output))


if __name__ == "__main__":
    main()
