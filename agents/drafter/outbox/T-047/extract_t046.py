"""Extract detailed field and history output from T-046 Abaqus ODB files.

Usage (on ROAR or any machine with Abaqus):
    abaqus python extract_t046.py [results_dir]

Generates:
    - t046_sol1.csv, t046_sol2.csv, t046_sol3.csv, t046_sol4.csv, t046_sol5.csv
    - t046_extracted.json
"""
from __future__ import print_function
import os
import sys
import json
import csv
from pathlib import Path

try:
    from odbAccess import openOdb
except ImportError:
    openOdb = None


def get_scalar(val, comp=0):
    if val is None:
        return 0.0
    d = val.data
    if hasattr(d, "__iter__"):
        try:
            return float(d[comp])
        except (IndexError, TypeError):
            return float(d[0])
    return float(d)


def extract_history_energies(step):
    energies = {}
    for region_name, region in step.historyRegions.items():
        if "ASSEMBLY" in region_name.upper():
            for name in ["ALLKE", "ALLIE", "ALLPD", "ALLDMD", "ETOTAL", "ALLWK", "ALLVD"]:
                if name in region.historyOutputs:
                    energies[name] = [(float(t), float(v)) for t, v in region.historyOutputs[name].data]
    return energies


def find_energy_at_time(series, t, tol=1e-7):
    if not series:
        return 0.0
    for time_pt, val in series:
        if abs(time_pt - t) <= tol or time_pt >= t:
            return val
    return series[-1][1]


def extract_test1(odb_path, out_dir):
    print("Extracting Test 1 from %s ..." % odb_path)
    odb = openOdb(str(odb_path), readOnly=True)
    step = list(odb.steps.values())[0]
    energies = extract_history_energies(step)

    rows = []
    frames_data = []

    for idx, frame in enumerate(step.frames):
        t = float(frame.frameValue)
        fo = frame.fieldOutputs

        # Element outputs
        s11 = None
        le11 = None
        peeq = None
        status = 1.0

        if "STATUS" in fo:
            for v in fo["STATUS"].values:
                if v.elementLabel == 1:
                    status = get_scalar(v)
        if "S" in fo:
            for v in fo["S"].values:
                if v.elementLabel == 1:
                    s11 = get_scalar(v, 0)
        if "LE" in fo:
            for v in fo["LE"].values:
                if v.elementLabel == 1:
                    le11 = get_scalar(v, 0)
        if "PEEQ" in fo:
            for v in fo["PEEQ"].values:
                if v.elementLabel == 1:
                    peeq = get_scalar(v)

        # Node outputs (node 2 is pulled)
        u1 = 0.0
        v1 = 0.0
        rf1 = 0.0
        if "U" in fo:
            for v in fo["U"].values:
                if v.nodeLabel == 2:
                    u1 = get_scalar(v, 0)
        if "V" in fo:
            for v in fo["V"].values:
                if v.nodeLabel == 2:
                    v1 = get_scalar(v, 0)
        if "RF" in fo:
            for v in fo["RF"].values:
                if v.nodeLabel == 2:
                    rf1 = get_scalar(v, 0)

        allke = find_energy_at_time(energies.get("ALLKE", []), t)
        allie = find_energy_at_time(energies.get("ALLIE", []), t)
        allpd = find_energy_at_time(energies.get("ALLPD", []), t)

        frame_dict = {
            "frame": idx,
            "time": t,
            "fiber_status": status,
            "fiber_s11": s11,
            "fiber_le11": le11,
            "fiber_peeq": peeq,
            "node2_u1": u1,
            "node2_v1": v1,
            "node2_rf1": rf1,
            "allke": allke,
            "allie": allie,
            "allpd": allpd,
        }
        frames_data.append(frame_dict)
        rows.append([idx, t, status, s11 if s11 is not None else 0.0,
                     le11 if le11 is not None else 0.0, peeq if peeq is not None else 0.0,
                     u1, v1, rf1, allke, allie, allpd])

    odb.close()

    csv_path = Path(out_dir) / "t046_sol1.csv"
    with open(str(csv_path), "w") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["frame", "time", "fiber_status", "fiber_s11", "fiber_le11",
                         "fiber_peeq", "node2_u1", "node2_v1", "node2_rf1", "allke", "allie", "allpd"])
        writer.writerows(rows)
    print("  Wrote %d frames to %s" % (len(rows), csv_path))
    return frames_data


def extract_test2(odb_path, out_dir):
    print("Extracting Test 2 from %s ..." % odb_path)
    odb = openOdb(str(odb_path), readOnly=True)
    step = list(odb.steps.values())[0]
    energies = extract_history_energies(step)

    rows = []
    frames_data = []

    for idx, frame in enumerate(step.frames):
        t = float(frame.frameValue)
        fo = frame.fieldOutputs

        # Elements: 1 is Host, 101 is Fib_emb, 102 is Fib_free
        host_status = 1.0
        fib_emb_status = 1.0
        fib_free_status = 1.0
        host_peeq = 0.0
        fib_emb_s11 = 0.0
        fib_emb_le11 = 0.0
        fib_free_s11 = 0.0
        fib_free_le11 = 0.0

        if "STATUS" in fo:
            for v in fo["STATUS"].values:
                if v.elementLabel == 1:
                    host_status = get_scalar(v)
                elif v.elementLabel == 101:
                    fib_emb_status = get_scalar(v)
                elif v.elementLabel == 102:
                    fib_free_status = get_scalar(v)

        if "PEEQ" in fo:
            for v in fo["PEEQ"].values:
                if v.elementLabel == 1:
                    host_peeq = get_scalar(v)

        if "S" in fo:
            for v in fo["S"].values:
                if v.elementLabel == 101:
                    fib_emb_s11 = get_scalar(v, 0)
                elif v.elementLabel == 102:
                    fib_free_s11 = get_scalar(v, 0)

        if "LE" in fo:
            for v in fo["LE"].values:
                if v.elementLabel == 101:
                    fib_emb_le11 = get_scalar(v, 0)
                elif v.elementLabel == 102:
                    fib_free_le11 = get_scalar(v, 0)

        # Node 103 (pulled fiber tip)
        u1 = 0.0
        rf1 = 0.0
        if "U" in fo:
            for v in fo["U"].values:
                if v.nodeLabel == 103:
                    u1 = get_scalar(v, 0)
        if "RF" in fo:
            for v in fo["RF"].values:
                if v.nodeLabel == 103:
                    rf1 = get_scalar(v, 0)

        allke = find_energy_at_time(energies.get("ALLKE", []), t)
        allie = find_energy_at_time(energies.get("ALLIE", []), t)
        allpd = find_energy_at_time(energies.get("ALLPD", []), t)

        frame_dict = {
            "frame": idx,
            "time": t,
            "host_status": host_status,
            "host_peeq": host_peeq,
            "fib_emb_status": fib_emb_status,
            "fib_free_status": fib_free_status,
            "fib_emb_s11": fib_emb_s11,
            "fib_emb_le11": fib_emb_le11,
            "fib_free_s11": fib_free_s11,
            "fib_free_le11": fib_free_le11,
            "node103_u1": u1,
            "node103_rf1": rf1,
            "allke": allke,
            "allie": allie,
            "allpd": allpd,
        }
        frames_data.append(frame_dict)
        rows.append([idx, t, host_status, host_peeq, fib_emb_status, fib_free_status,
                     fib_emb_s11, fib_emb_le11, fib_free_s11, fib_free_le11,
                     u1, rf1, allke, allie, allpd])

    odb.close()

    csv_path = Path(out_dir) / "t046_sol2.csv"
    with open(str(csv_path), "w") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["frame", "time", "host_status", "host_peeq", "fib_emb_status", "fib_free_status",
                         "fib_emb_s11", "fib_emb_le11", "fib_free_s11", "fib_free_le11",
                         "node103_u1", "node103_rf1", "allke", "allie", "allpd"])
        writer.writerows(rows)
    print("  Wrote %d frames to %s" % (len(rows), csv_path))
    return frames_data


def extract_test3(odb_path, out_dir):
    print("Extracting Test 3 from %s ..." % odb_path)
    odb = openOdb(str(odb_path), readOnly=True)
    step = list(odb.steps.values())[0]
    energies = extract_history_energies(step)

    rows = []
    frames_data = []

    for idx, frame in enumerate(step.frames):
        t = float(frame.frameValue)
        fo = frame.fieldOutputs

        # Elements: 1 is Ghost Host, 101 is Fib_emb, 102 is Fib_free
        ghost_status = 1.0
        fib_emb_status = 1.0
        fib_free_status = 1.0
        ghost_peeq = 0.0
        fib_emb_s11 = 0.0
        fib_emb_le11 = 0.0

        if "STATUS" in fo:
            for v in fo["STATUS"].values:
                if v.elementLabel == 1:
                    ghost_status = get_scalar(v)
                elif v.elementLabel == 101:
                    fib_emb_status = get_scalar(v)
                elif v.elementLabel == 102:
                    fib_free_status = get_scalar(v)

        if "PEEQ" in fo:
            for v in fo["PEEQ"].values:
                if v.elementLabel == 1:
                    ghost_peeq = get_scalar(v)

        if "S" in fo:
            for v in fo["S"].values:
                if v.elementLabel == 101:
                    fib_emb_s11 = get_scalar(v, 0)

        if "LE" in fo:
            for v in fo["LE"].values:
                if v.elementLabel == 101:
                    fib_emb_le11 = get_scalar(v, 0)

        # Node 103 (pulled fiber tip)
        u1 = 0.0
        rf1 = 0.0
        if "U" in fo:
            for v in fo["U"].values:
                if v.nodeLabel == 103:
                    u1 = get_scalar(v, 0)
        if "RF" in fo:
            for v in fo["RF"].values:
                if v.nodeLabel == 103:
                    rf1 = get_scalar(v, 0)

        allke = find_energy_at_time(energies.get("ALLKE", []), t)
        allie = find_energy_at_time(energies.get("ALLIE", []), t)
        allpd = find_energy_at_time(energies.get("ALLPD", []), t)

        frame_dict = {
            "frame": idx,
            "time": t,
            "ghost_status": ghost_status,
            "ghost_peeq": ghost_peeq,
            "fib_emb_status": fib_emb_status,
            "fib_free_status": fib_free_status,
            "fib_emb_s11": fib_emb_s11,
            "fib_emb_le11": fib_emb_le11,
            "node103_u1": u1,
            "node103_rf1": rf1,
            "allke": allke,
            "allie": allie,
            "allpd": allpd,
        }
        frames_data.append(frame_dict)
        rows.append([idx, t, ghost_status, ghost_peeq, fib_emb_status, fib_free_status,
                     fib_emb_s11, fib_emb_le11, u1, rf1, allke, allie, allpd])

    odb.close()

    csv_path = Path(out_dir) / "t046_sol3.csv"
    with open(str(csv_path), "w") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["frame", "time", "ghost_status", "ghost_peeq", "fib_emb_status", "fib_free_status",
                         "fib_emb_s11", "fib_emb_le11", "node103_u1", "node103_rf1", "allke", "allie", "allpd"])
        writer.writerows(rows)
    print("  Wrote %d frames to %s" % (len(rows), csv_path))
    return frames_data


def extract_test4(odb_path, out_dir):
    print("Extracting Test 4 from %s ..." % odb_path)
    odb = openOdb(str(odb_path), readOnly=True)
    step = list(odb.steps.values())[0]
    energies = extract_history_energies(step)

    rows = []
    frames_data = []

    for idx, frame in enumerate(step.frames):
        t = float(frame.frameValue)
        fo = frame.fieldOutputs

        # Elements: 1..9 Host, 101..104 Fiber
        host_status = {i: 1.0 for i in range(1, 10)}
        fib_status = {i: 1.0 for i in range(101, 105)}

        if "STATUS" in fo:
            for v in fo["STATUS"].values:
                if v.elementLabel in host_status:
                    host_status[v.elementLabel] = get_scalar(v)
                elif v.elementLabel in fib_status:
                    fib_status[v.elementLabel] = get_scalar(v)

        # Node 105 (pulled node)
        u1 = 0.0
        rf1 = 0.0
        if "U" in fo:
            for v in fo["U"].values:
                if v.nodeLabel == 105:
                    u1 = get_scalar(v, 0)
        if "RF" in fo:
            for v in fo["RF"].values:
                if v.nodeLabel == 105:
                    rf1 = get_scalar(v, 0)

        allke = find_energy_at_time(energies.get("ALLKE", []), t)
        allie = find_energy_at_time(energies.get("ALLIE", []), t)
        allpd = find_energy_at_time(energies.get("ALLPD", []), t)

        frame_dict = {
            "frame": idx,
            "time": t,
            "host_status": host_status,
            "fib_status": fib_status,
            "node105_u1": u1,
            "node105_rf1": rf1,
            "allke": allke,
            "allie": allie,
            "allpd": allpd,
        }
        frames_data.append(frame_dict)

        row = [idx, t]
        row.extend(host_status[i] for i in range(1, 10))
        row.extend(fib_status[i] for i in range(101, 105))
        row.extend([u1, rf1, allke, allie, allpd])
        rows.append(row)

    odb.close()

    csv_path = Path(out_dir) / "t046_sol4.csv"
    with open(str(csv_path), "w") as f:
        writer = csv.writer(f, lineterminator="\n")
        header = ["frame", "time"] + ["host%d_status" % i for i in range(1, 10)] + \
                 ["fib%d_status" % i for i in range(101, 105)] + ["node105_u1", "node105_rf1", "allke", "allie", "allpd"]
        writer.writerow(header)
        writer.writerows(rows)
    print("  Wrote %d frames to %s" % (len(rows), csv_path))
    return frames_data


def extract_test5(odb_path, out_dir):
    print("Extracting Test 5 from %s ..." % odb_path)
    odb = openOdb(str(odb_path), readOnly=True)
    step = list(odb.steps.values())[0]
    energies = extract_history_energies(step)

    rows = []
    frames_data = []

    for idx, frame in enumerate(step.frames):
        t = float(frame.frameValue)
        fo = frame.fieldOutputs

        # Element 1 is Host
        host_status = 1.0
        host_peeq = 0.0

        if "STATUS" in fo:
            for v in fo["STATUS"].values:
                if v.elementLabel == 1:
                    host_status = get_scalar(v)

        if "PEEQ" in fo:
            for v in fo["PEEQ"].values:
                if v.elementLabel == 1:
                    host_peeq = get_scalar(v)

        # Pulled nodes: 2, 3, 6, 7
        pull_nodes = [2, 3, 6, 7]
        u1_sum = 0.0
        v1_sum = 0.0
        a1_sum = 0.0
        rf1_sum = 0.0

        if "U" in fo:
            for v in fo["U"].values:
                if v.nodeLabel in pull_nodes:
                    u1_sum += get_scalar(v, 0)
        if "V" in fo:
            for v in fo["V"].values:
                if v.nodeLabel in pull_nodes:
                    v1_sum += get_scalar(v, 0)
        if "A" in fo:
            for v in fo["A"].values:
                if v.nodeLabel in pull_nodes:
                    a1_sum += get_scalar(v, 0)
        if "RF" in fo:
            for v in fo["RF"].values:
                if v.nodeLabel in pull_nodes:
                    rf1_sum += get_scalar(v, 0)

        u1_avg = u1_sum / len(pull_nodes)
        v1_avg = v1_sum / len(pull_nodes)
        a1_avg = a1_sum / len(pull_nodes)

        # Apparent mass M = RF_total / a_avg (if a_avg is non-zero)
        apparent_mass = None
        if abs(a1_avg) > 1e-3:
            apparent_mass = rf1_sum / a1_avg

        allke = find_energy_at_time(energies.get("ALLKE", []), t)
        allie = find_energy_at_time(energies.get("ALLIE", []), t)
        allpd = find_energy_at_time(energies.get("ALLPD", []), t)

        frame_dict = {
            "frame": idx,
            "time": t,
            "host_status": host_status,
            "host_peeq": host_peeq,
            "pull_u1_avg": u1_avg,
            "pull_v1_avg": v1_avg,
            "pull_a1_avg": a1_avg,
            "pull_rf1_sum": rf1_sum,
            "apparent_mass": apparent_mass,
            "allke": allke,
            "allie": allie,
            "allpd": allpd,
        }
        frames_data.append(frame_dict)
        rows.append([idx, t, host_status, host_peeq, u1_avg, v1_avg, a1_avg, rf1_sum,
                     apparent_mass if apparent_mass is not None else "", allke, allie, allpd])

    odb.close()

    csv_path = Path(out_dir) / "t046_sol5.csv"
    with open(str(csv_path), "w") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["frame", "time", "host_status", "host_peeq", "pull_u1_avg",
                         "pull_v1_avg", "pull_a1_avg", "pull_rf1_sum", "apparent_mass", "allke", "allie", "allpd"])
        writer.writerows(rows)
    print("  Wrote %d frames to %s" % (len(rows), csv_path))
    return frames_data


def main():
    if openOdb is None:
        sys.exit("Error: odbAccess not available. Must be run with `abaqus python extract_t046.py`.")

    results_dir = Path(".").resolve()
    if len(sys.argv) > 1:
        results_dir = Path(sys.argv[1]).resolve()

    print("Running T-046 ODB extraction in %s" % results_dir)

    all_data = {}

    f1 = results_dir / "t046_sol1.odb"
    if f1.exists():
        all_data["test1"] = extract_test1(f1, results_dir)
    else:
        print("Test 1 ODB not found: %s" % f1)

    f2 = results_dir / "t046_sol2.odb"
    if f2.exists():
        all_data["test2"] = extract_test2(f2, results_dir)
    else:
        print("Test 2 ODB not found: %s" % f2)

    f3 = results_dir / "t046_sol3.odb"
    if f3.exists():
        all_data["test3"] = extract_test3(f3, results_dir)
    else:
        print("Test 3 ODB not found: %s" % f3)

    f4 = results_dir / "t046_sol4.odb"
    if f4.exists():
        all_data["test4"] = extract_test4(f4, results_dir)
    else:
        print("Test 4 ODB not found: %s" % f4)

    f5 = results_dir / "t046_sol5.odb"
    if f5.exists():
        all_data["test5"] = extract_test5(f5, results_dir)
    else:
        print("Test 5 ODB not found: %s" % f5)

    json_path = results_dir / "t046_extracted.json"
    with open(str(json_path), "w") as f:
        json.dump(all_data, f, indent=2)
    print("Saved combined summary to %s" % json_path)


if __name__ == "__main__":
    main()
