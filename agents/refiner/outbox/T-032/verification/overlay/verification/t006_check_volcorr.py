"""Abaqus-Python checker for the T-006 ROAR verification bundle."""
from __future__ import print_function
import json
from pathlib import Path
import re
import sys

from odbAccess import openOdb
from t006_vf_metrics import rel


PINNED = (1, 4, 5, 8)


def curve(path, pinned=PINNED, displacement_node=2):
    odb = openOdb(str(path))
    frames = list(odb.steps.values())[0].frames
    rows = []
    for frame in frames:
        displacement = None
        reaction = 0.0
        seen = set()
        for value in frame.fieldOutputs["U"].values:
            if value.nodeLabel == displacement_node:
                displacement = float(value.data[0])
        for value in frame.fieldOutputs["RF"].values:
            if value.nodeLabel in pinned:
                reaction += float(value.data[0])
                seen.add(value.nodeLabel)
        if displacement is not None and len(seen) == len(pinned):
            rows.append((float(frame.frameValue), displacement, -reaction))
    odb.close()
    return rows


def nearest(rows, displacement):
    return min(rows, key=lambda row: abs(row[1] - displacement))


def paired_errors(full, scaled, factor, samples):
    errors = []
    evidence = []
    sign = 1.0 if full[-1][1] >= 0.0 else -1.0
    for magnitude in samples:
        row0 = nearest(full, sign * magnitude)
        row1 = nearest(scaled, sign * magnitude)
        error = rel(abs(row1[2]), factor * abs(row0[2]))
        errors.append(error)
        evidence.append({"target_displacement": sign * magnitude,
                         "vf0": row0, "scaled": row1,
                         "relative_error": error})
    return max(errors), evidence


def regression(new, baseline):
    errors = []
    exact = True
    for new_row, old_row in zip(new, baseline):
        exact = exact and new_row == old_row
        errors.extend((rel(new_row[0], old_row[0]),
                       rel(new_row[1], old_row[1]),
                       rel(new_row[2], old_row[2])))
    return {"same_frame_count": len(new) == len(baseline),
            "bitwise_equal_rows": exact and len(new) == len(baseline),
            "max_relative_error": max(errors) if errors else None}


def job_text(root, name):
    run = root / ("run_" + name)
    chunks = []
    for suffix in ("stdout", "msg", "dat", "sta"):
        path = run / (name + "." + suffix)
        if path.exists():
            chunks.append(path.read_text(errors="replace"))
    return "\n".join(chunks)


def tagged_rows(text, tag):
    # A Fortran list-directed WRITE(*,*) wraps a long record across physical
    # lines; a continuation line carries no label, only numbers/whitespace.
    # So once a tagged line is found, keep absorbing purely-numeric follow-on
    # lines into the same logical record before parsing it.
    numeric_line = re.compile(r"^[\s0-9.+\-DEde]*$")
    number = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[DEde][-+]?\d+)?"
    lines = text.splitlines()
    rows = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if tag not in line:
            i += 1
            continue
        record = line.split(tag, 1)[1]
        j = i + 1
        while j < len(lines) and lines[j].strip() and numeric_line.match(lines[j]):
            record += " " + lines[j]
            j += 1
        values = [float(value.replace("D", "E").replace("d", "e"))
                  for value in re.findall(number, record)]
        rows.append(values)
        i = j
    return rows


def first_dt(root, name):
    rows = tagged_rows(job_text(root, name), "T006_DT")
    if not rows:
        return None
    return rows[0][2]  # elem, eta, dt, geom


def main(root):
    root = Path(root)
    odb = lambda name: root / ("run_" + name) / (name + ".odb")
    report = {"regression": {}, "slow_half_force": {}}
    for mode in ("tension", "compression"):
        prefix = "t006_slow_" + mode + "_"
        vf0 = curve(odb(prefix + "vf0"))
        vf05 = curve(odb(prefix + "vf05"))
        baseline = curve(odb(prefix + "vf0_baseline"))
        report["regression"][mode] = regression(vf0, baseline)
        error, evidence = paired_errors(
            vf0, vf05, 0.5, (0.0005, 0.0009, 0.01, 0.02, 0.035))
        report["slow_half_force"][mode] = {
            "max_relative_error": error, "samples": evidence}

    dt0 = first_dt(root, "t006_slow_tension_vf0")
    dt05 = first_dt(root, "t006_slow_tension_vf05")
    report["stable_timestep"] = {
        "vf0_s": dt0, "vf05_s": dt05,
        "relative_error": rel(dt05, dt0) if dt0 is not None and dt05 is not None else None,
    }

    def force(name, displacement=-0.005):
        return abs(nearest(curve(odb(name)), displacement)[2])

    bulk0 = force("t006_bulk_vf0")
    bulk05 = force("t006_bulk_vf05")
    physical0 = force("t006_bulk_physical_vf0")
    physical05 = force("t006_bulk_physical_vf05")
    stabilization0 = bulk0 - physical0
    stabilization05 = bulk05 - physical05
    report["bulk_isolation"] = {
        "total_force": {"vf0": bulk0, "vf05": bulk05},
        "physical_only_force": {"vf0": physical0, "vf05": physical05},
        "isolated_stabilization_force": {"vf0": stabilization0,
                                          "vf05": stabilization05},
        "physical_half_relative_error": rel(physical05, 0.5 * physical0),
        "stabilization_unscaled_relative_error": rel(stabilization05,
                                                       stabilization0),
    }

    mixed_name = "t006_mixed_vf"
    mixed = job_text(root, mixed_name)
    eta_rows = tagged_rows(mixed, "T006_ETA")
    mass_rows = tagged_rows(mixed, "T006_MASS")
    mixed_a = curve(odb(mixed_name), (1, 4, 5, 8), 2)
    mixed_b = curve(odb(mixed_name), (9, 12, 13, 16), 10)
    force_a = abs(nearest(mixed_a, 0.0005)[2])
    force_b = abs(nearest(mixed_b, 0.0005)[2])
    report["mixed_vf_one_block"] = {
        "eta_diagnostics": eta_rows, "mass_diagnostics": mass_rows,
        "reaction": {"vf0p3_eta0p7": force_a, "vf0p6_eta0p4": force_b},
        "reaction_ratio": force_b / force_a,
        "expected_ratio": 0.4 / 0.7,
        "ratio_relative_error": rel(force_b / force_a, 0.4 / 0.7),
        "same_nblock_proved": (len(eta_rows) >= 2 and
                               eta_rows[0][3] >= 2 and eta_rows[1][3] >= 2),
    }

    checks = {
        "vf0_exact": all(item["max_relative_error"] == 0.0
                         for item in report["regression"].values()),
        "slow_half_force_lt_3pct": all(item["max_relative_error"] < 0.03
                                       for item in report["slow_half_force"].values()),
        "stable_dt_matches_lt_1e12": report["stable_timestep"]["relative_error"] is not None
                                     and report["stable_timestep"]["relative_error"] < 1.0e-12,
        "bulk_stabilization_unscaled_lt_3pct":
            report["bulk_isolation"]["stabilization_unscaled_relative_error"] < 0.03,
        "mixed_same_block": report["mixed_vf_one_block"]["same_nblock_proved"],
        "mixed_force_ratio_lt_3pct":
            report["mixed_vf_one_block"]["ratio_relative_error"] < 0.03,
    }
    report["checks"] = checks
    report["pass"] = all(checks.values())
    print(json.dumps(report, indent=2, sort_keys=True))
    if not report["pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: abaqus python t006_check_volcorr.py RUN_ROOT")
    main(sys.argv[1])
