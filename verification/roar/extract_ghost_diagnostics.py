"""Extract compact per-frame diagnostics from the instrumented ghost elset.

Run on a machine with Abaqus, for example:
    abaqus python extract_ghost_diagnostics.py flat_vg_r4.odb
"""
from __future__ import print_function

import argparse

from odbAccess import openOdb


ELSET = "EMBMESH_GHOST_DIAGNOSTICS"
FIELDS = ("S", "LE", "PEEQ", "SDEG", "STATUS")


def scalar_max(field, region):
    values = field.getSubset(region=region).values
    data = [float(value.data) for value in values]
    return max(data) if data else float("nan")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("odb")
    parser.add_argument("--step", default="Step-1")
    parser.add_argument("--output", default="ghost_diagnostics.csv")
    args = parser.parse_args()

    odb = openOdb(args.odb, readOnly=True)
    try:
        step = odb.steps[args.step]
        region = odb.rootAssembly.elementSets[ELSET]
        with open(args.output, "w") as handle:
            handle.write(
                "frame,time,max_mises,max_abs_le_principal,max_peeq,"
                "max_sdeg,min_status,deleted_elements\n")
            for index, frame in enumerate(step.frames):
                missing = [name for name in FIELDS if name not in frame.fieldOutputs]
                if missing:
                    raise RuntimeError(
                        "frame {0} is missing requested fields: {1}".format(
                            index, ", ".join(missing)))

                stress = frame.fieldOutputs["S"].getSubset(region=region).values
                strain = frame.fieldOutputs["LE"].getSubset(region=region).values
                status = frame.fieldOutputs["STATUS"].getSubset(region=region).values
                mises_values = [float(value.mises) for value in stress]
                max_mises = max(mises_values) if mises_values else float("nan")
                le_values = [
                    max(abs(float(value.maxPrincipal)),
                        abs(float(value.minPrincipal)))
                    for value in strain]
                max_abs_le = max(le_values) if le_values else float("nan")
                status_values = [float(value.data) for value in status]
                deleted = set(
                    value.elementLabel for value in status
                    if float(value.data) < 0.5)
                row = (
                    index,
                    frame.frameValue,
                    max_mises,
                    max_abs_le,
                    scalar_max(frame.fieldOutputs["PEEQ"], region),
                    scalar_max(frame.fieldOutputs["SDEG"], region),
                    min(status_values) if status_values else float("nan"),
                    len(deleted),
                )
                handle.write(",".join(str(value) for value in row) + "\n")
    finally:
        odb.close()
    print("wrote {0}".format(args.output))


if __name__ == "__main__":
    main()
