"""Extract and check Stage 5 VUEL degradation results with Abaqus Python.

Usage:
    abaqus python t11_check_degradation.py /path/to/slurm-submit-directory

The script prints one JSON document. It exits nonzero when a strict
constitutive check fails; the three-element cascade outcome is observational
and is always reported without being forced to cascade.
"""
import json
import math
import os
import re
import sys

from odbAccess import openOdb


DECKS = (
    "t11_instant_chain",
    "t11_ramp_chain",
    "t11_ramp_tension",
    "t11_zero_cycle",
    "t11_residual_cycle",
)
BACK_NODES = (1, 4, 5, 8)
FAIL_RE = re.compile(
    r"\*\*\* VUEL_FAILURE \(([^)]+)\): elem =\s*(\d+)\s+"
    r"time =\s*([-+0-9.DEde]+)")
DONE_RE = re.compile(
    r"\*\*\* VUEL_DEGRADATION_COMPLETE: elem =\s*(\d+)\s+"
    r"time =\s*([-+0-9.DEde]+)")


def fortran_float(text):
    return float(text.replace("D", "E").replace("d", "e"))


def events(stdout_path):
    text = open(stdout_path, "r").read()
    failures = [
        {"criterion": m.group(1), "element": int(m.group(2)),
         "time": fortran_float(m.group(3))}
        for m in FAIL_RE.finditer(text)
    ]
    completions = [
        {"element": int(m.group(1)), "time": fortran_float(m.group(2))}
        for m in DONE_RE.finditer(text)
    ]
    return failures, completions


def frame_history(odb_path, probe_node=2):
    odb = openOdb(odb_path, readOnly=True)
    step_name = list(odb.steps.keys())[0]
    rows = []
    for frame in odb.steps[step_name].frames:
        u1 = None
        v1 = None
        rf_sum = 0.0
        rf_seen = set()
        for value in frame.fieldOutputs["U"].values:
            if value.nodeLabel == probe_node:
                u1 = float(value.data[0])
        for value in frame.fieldOutputs["V"].values:
            if value.nodeLabel == probe_node:
                v1 = float(value.data[0])
        for value in frame.fieldOutputs["RF"].values:
            if value.nodeLabel in BACK_NODES:
                rf_sum += float(value.data[0])
                rf_seen.add(value.nodeLabel)
        rows.append({
            "time": float(frame.frameValue),
            "u1": u1,
            "v1": v1,
            "rf1_back_sum": rf_sum if len(rf_seen) == 4 else None,
        })
    odb.close()
    return rows


def first_after(rows, time_value):
    for row in rows:
        if row["time"] > time_value:
            return row
    return None


def max_abs_rf(rows, start_time):
    values = [abs(r["rf1_back_sum"]) for r in rows
              if r["time"] > start_time and r["rf1_back_sum"] is not None]
    return max(values) if values else None


def window_max_abs_rf(rows, start_time, end_time):
    values = [abs(r["rf1_back_sum"]) for r in rows
              if start_time <= r["time"] <= end_time
              and r["rf1_back_sum"] is not None]
    return max(values) if values else None


def chain_summary(rows, failures):
    if not failures:
        return {"failed_elements": [], "first_failure_time": None,
                "node2_v1_min_after_first_failure": None,
                "node2_v1_max_after_first_failure": None,
                "node2_v1_final": rows[-1]["v1"]}
    first_time = min(item["time"] for item in failures)
    velocities = [r["v1"] for r in rows
                  if r["time"] > first_time and r["v1"] is not None]
    return {
        "failed_elements": [item["element"] for item in failures],
        "failure_times": [item["time"] for item in failures],
        "first_failure_time": first_time,
        "node2_v1_min_after_first_failure": min(velocities),
        "node2_v1_max_after_first_failure": max(velocities),
        "node2_v1_final": rows[-1]["v1"],
    }


def finite(value):
    return value is not None and math.isfinite(value)


def main():
    base = os.path.abspath(sys.argv[1])
    data = {}
    for name in DECKS:
        run_dir = os.path.join(base, "run_" + name)
        failures, completions = events(os.path.join(run_dir, name + ".stdout"))
        rows = frame_history(os.path.join(run_dir, name + ".odb"))
        data[name] = {"failures": failures, "completions": completions,
                      "rows": rows}

    instant = chain_summary(data["t11_instant_chain"]["rows"],
                            data["t11_instant_chain"]["failures"])
    ramp_chain = chain_summary(data["t11_ramp_chain"]["rows"],
                               data["t11_ramp_chain"]["failures"])

    ramp = data["t11_ramp_tension"]
    ramp_fail = ramp["failures"][0]["time"] if ramp["failures"] else None
    ramp_done = (ramp["completions"][0]["time"]
                 if ramp["completions"] else None)
    ramp_first = first_after(ramp["rows"], ramp_fail) if ramp_fail else None
    ramp_post_max = max_abs_rf(ramp["rows"], ramp_done) if ramp_done else None
    ramp_duration = ramp_done - ramp_fail if ramp_done and ramp_fail else None
    ramp_check = {
        "failure_time": ramp_fail,
        "completion_time": ramp_done,
        "measured_degradation_duration": ramp_duration,
        "first_post_failure_frame": ramp_first,
        "max_abs_rf_after_completion": ramp_post_max,
        "pass_force_persists_during_ramp": bool(
            ramp_first and abs(ramp_first["rf1_back_sum"]) > 1.0e5),
        "pass_force_zero_after_ramp": bool(
            finite(ramp_post_max) and ramp_post_max < 1.0e-6),
        "pass_duration": bool(
            # Completion is detected at an explicit increment boundary;
            # allow one conservative cube increment (~1.36e-4 s).
            finite(ramp_duration) and abs(ramp_duration - 0.002) < 2.0e-4),
    }

    zero = data["t11_zero_cycle"]
    residual = data["t11_residual_cycle"]
    zero_plateau = window_max_abs_rf(zero["rows"], 0.0045, 0.0055)
    residual_plateau = window_max_abs_rf(
        residual["rows"], 0.0045, 0.0055)
    zero_final = zero["rows"][-1]
    residual_final = residual["rows"][-1]

    # Fully constrained cycle: F=diag(lambda,1,1), E11=(lambda^2-1)/2,
    # S11=r*K*E11 and nominal reaction magnitude is |P11|=|F11*S11|.
    u_final = residual_final["u1"]
    stretch = 1.0 + u_final
    green_e11 = 0.5 * (stretch * stretch - 1.0)
    bulk_modulus = 2.0e11 / (3.0 * (1.0 - 2.0 * 0.3))
    expected_rf = abs(stretch * 0.1 * bulk_modulus * min(green_e11, 0.0))
    measured_rf = abs(residual_final["rf1_back_sum"])
    residual_rel_error = ((measured_rf - expected_rf) / expected_rf
                          if expected_rf > 0.0 else None)
    cycle_check = {
        "zero_cycle_failure_events": zero["failures"],
        "residual_cycle_failure_events": residual["failures"],
        "zero_cycle_max_abs_rf_tension_plateau": zero_plateau,
        "residual_cycle_max_abs_rf_tension_plateau": residual_plateau,
        "zero_cycle_final": zero_final,
        "residual_cycle_final": residual_final,
        "residual_expected_final_abs_rf": expected_rf,
        "residual_measured_final_abs_rf": measured_rf,
        "residual_final_rel_error": residual_rel_error,
        "pass_zero_control": bool(abs(zero_final["rf1_back_sum"]) < 1.0e-6),
        "pass_no_residual_tension": bool(
            finite(residual_plateau) and residual_plateau < 1.0e-6),
        "pass_compression_residual": bool(
            finite(residual_rel_error) and abs(residual_rel_error) < 1.0e-5),
    }

    strict = {
        "instant_chain_reproduces_stage4": instant["failed_elements"] == [1],
        "ramp_tension": all(ramp_check[key] for key in (
            "pass_force_persists_during_ramp", "pass_force_zero_after_ramp",
            "pass_duration")),
        "compression_only_residual": all(cycle_check[key] for key in (
            "pass_zero_control", "pass_no_residual_tension",
            "pass_compression_residual")),
    }
    result = {
        "strict_checks": strict,
        "pass": all(strict.values()),
        "instant_chain": instant,
        "ramp_chain": ramp_chain,
        "ramp_tension": ramp_check,
        "cycles": cycle_check,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    if not result["pass"]:
        sys.exit(2)


if __name__ == "__main__":
    main()
