"""Abaqus-Python extraction script for T-049 ball isolation tests.

Extracts key ball performance and integrity metrics from one or more ODBs:
  - Ball min element volume ratio (EVOL(t) / EVOL(t0)): measures element flattening/inversion
  - Peak ball Mises stress (Pa / GPa)
  - Peak ball equivalent plastic strain (PEEQ)
  - Ball deleted element count (STATUS < 0.5)
  - Energy conservation: ALLKE peak vs start, ETOTAL end vs start
  - Peak contact pressure on ball (CPRESS, Pa / GPa)

Usage on ROAR:
  abaqus python check_ball_tests.py [odb_file_or_directory] [--json summary.json] [--csv summary.csv]

Usage locally (report mode):
  python check_ball_tests.py --report summary.json
"""

from __future__ import print_function, division
import os
import sys
import json
import csv
from pathlib import Path


def extract_single_odb(odb_path):
    """Extract ball and energy metrics from a single Abaqus ODB file."""
    import numpy as np
    from odbAccess import openOdb

    print(f"Reading ODB: {odb_path}...")
    odb = openOdb(str(odb_path), readOnly=True)
    step = list(odb.steps.values())[0]
    nframes = len(step.frames)
    t_end = float(step.frames[-1].frameValue) if nframes > 0 else 0.0

    root = odb.rootAssembly

    # Locate Ball region: in flat deck, sets are on rootAssembly; in instanced, on instance
    ball_elset = None
    if "BALL_ELEMS" in root.elementSets:
        ball_elset = root.elementSets["BALL_ELEMS"]
    else:
        for inst_name, inst in root.instances.items():
            if "BALL" in inst_name.upper():
                if "BALL_ELEMS" in inst.elementSets:
                    ball_elset = inst.elementSets["BALL_ELEMS"]
                    break
                elif "BALL" in inst.elementSets:
                    ball_elset = inst.elementSets["BALL"]
                    break

    # Energy history extraction
    allke_data, etotal_data, allie_data, allpd_data, allvd_data = [], [], [], [], []
    for hname, hreg in step.historyRegions.items():
        if "ASSEMBLY" in hname.upper():
            ho = hreg.historyOutputs
            if "ALLKE" in ho:
                allke_data = [pt[1] for pt in ho["ALLKE"].data]
            if "ETOTAL" in ho:
                etotal_data = [pt[1] for pt in ho["ETOTAL"].data]
            if "ALLIE" in ho:
                allie_data = [pt[1] for pt in ho["ALLIE"].data]
            if "ALLPD" in ho:
                allpd_data = [pt[1] for pt in ho["ALLPD"].data]
            if "ALLVD" in ho:
                allvd_data = [pt[1] for pt in ho["ALLVD"].data]

    allke_start = allke_data[0] if allke_data else 0.0
    allke_peak = max(allke_data) if allke_data else 0.0
    allke_end = allke_data[-1] if allke_data else 0.0
    allke_ratio = (allke_peak / allke_start) if allke_start > 0 else 0.0

    etotal_start = etotal_data[0] if etotal_data else 0.0
    etotal_end = etotal_data[-1] if etotal_data else 0.0
    etotal_ratio = (etotal_end / etotal_start) if etotal_start > 0 else 0.0

    allie_end = allie_data[-1] if allie_data else 0.0
    allpd_end = allpd_data[-1] if allpd_data else 0.0
    allvd_end = allvd_data[-1] if allvd_data else 0.0

    # Field output extraction
    peak_mises = 0.0
    peak_peeq = 0.0
    max_deleted = 0
    final_deleted = 0
    min_vol_ratio = 1.0
    peak_cpress = 0.0

    # Baseline element volumes at frame 0 for volume ratio calculation
    initial_evol = {}
    if nframes > 0 and ball_elset is not None:
        f0 = step.frames[0]
        if "EVOL" in f0.fieldOutputs:
            sub = f0.fieldOutputs["EVOL"].getSubset(region=ball_elset)
            for b in sub.bulkDataBlocks:
                for lab, v in zip(b.elementLabels, b.data.flatten()):
                    initial_evol[int(lab)] = float(v)

    # Frame sampling: inspect up to 50 frames uniformly spaced
    sample_indices = sorted(set(list(range(0, nframes, max(1, nframes // 50))) + [nframes - 1]))

    for idx in sample_indices:
        f = step.frames[idx]
        t = float(f.frameValue)

        # Mises stress
        if "S" in f.fieldOutputs and ball_elset is not None:
            sub = f.fieldOutputs["S"].getSubset(region=ball_elset)
            for b in sub.bulkDataBlocks:
                if b.mises is not None and len(b.mises) > 0:
                    peak_mises = max(peak_mises, float(np.nanmax(b.mises)))

        # PEEQ
        if "PEEQ" in f.fieldOutputs and ball_elset is not None:
            sub = f.fieldOutputs["PEEQ"].getSubset(region=ball_elset)
            for b in sub.bulkDataBlocks:
                if len(b.data) > 0:
                    peak_peeq = max(peak_peeq, float(np.nanmax(b.data)))

        # Element STATUS & Deletion count
        if "STATUS" in f.fieldOutputs and ball_elset is not None:
            sub = f.fieldOutputs["STATUS"].getSubset(region=ball_elset)
            cur_del = 0
            for b in sub.bulkDataBlocks:
                cur_del += int((b.data.flatten() < 0.5).sum())
            max_deleted = max(max_deleted, cur_del)
            if idx == sample_indices[-1]:
                final_deleted = cur_del

        # Element Volume Ratio: EVOL(t) / EVOL(t0)
        if "EVOL" in f.fieldOutputs and ball_elset is not None and initial_evol:
            sub = f.fieldOutputs["EVOL"].getSubset(region=ball_elset)
            for b in sub.bulkDataBlocks:
                for lab, v in zip(b.elementLabels, b.data.flatten()):
                    v0 = initial_evol.get(int(lab), 0.0)
                    if v0 > 0.0 and v > 0.0:
                        ratio = float(v) / v0
                        if ratio < min_vol_ratio:
                            min_vol_ratio = ratio

        # Contact pressure
        if "CPRESS" in f.fieldOutputs:
            for b in f.fieldOutputs["CPRESS"].bulkDataBlocks:
                if len(b.data) > 0:
                    peak_cpress = max(peak_cpress, float(np.nanmax(b.data)))

    odb.close()

    return {
        "odb_name": Path(odb_path).name,
        "nframes": nframes,
        "t_end_us": t_end * 1e6,
        "allke_start_J": allke_start,
        "allke_peak_J": allke_peak,
        "allke_peak_ratio": allke_ratio,
        "etotal_start_J": etotal_start,
        "etotal_end_J": etotal_end,
        "etotal_end_ratio": etotal_ratio,
        "allie_end_J": allie_end,
        "allpd_end_J": allpd_end,
        "allvd_end_J": allvd_end,
        "peak_mises_GPa": peak_mises / 1e9,
        "peak_peeq": peak_peeq,
        "ball_deleted_max": max_deleted,
        "ball_deleted_final": final_deleted,
        "ball_min_vol_ratio": min_vol_ratio,
        "peak_cpress_GPa": peak_cpress / 1e9,
    }


def print_markdown_table(results):
    """Print formatted Markdown comparison table of extracted test results."""
    headers = [
        "Test Deck", "Frames", "t_end (us)", "Min Vol Ratio",
        "Peak Mises (GPa)", "Peak PEEQ", "Deleted", "ALLKE Peak %", "ETOTAL End %", "Peak CP (GPa)"
    ]
    rows = []
    for r in results:
        allke_pct = f"+{(r['allke_peak_ratio'] - 1.0) * 100:.1f}%" if r["allke_peak_ratio"] >= 1.0 else f"{(r['allke_peak_ratio'] - 1.0) * 100:.1f}%"
        etotal_pct = f"+{(r['etotal_end_ratio'] - 1.0) * 100:.1f}%" if r["etotal_end_ratio"] >= 1.0 else f"{(r['etotal_end_ratio'] - 1.0) * 100:.1f}%"
        rows.append([
            r["odb_name"].replace(".odb", ""),
            str(r["nframes"]),
            f"{r['t_end_us']:.2f}",
            f"{r['ball_min_vol_ratio']:.4f}",
            f"{r['peak_mises_GPa']:.2f}",
            f"{r['peak_peeq']:.3f}",
            f"{r['ball_deleted_final']}",
            allke_pct,
            etotal_pct,
            f"{r['peak_cpress_GPa']:.1f}",
        ])

    col_widths = [max(len(h), max(len(row[i]) for row in rows)) for i, h in enumerate(headers)]
    header_str = " | ".join(h.ljust(w) for h, w in zip(headers, col_widths))
    sep_str = "-|-".join("-" * w for w in col_widths)

    print("\n" + header_str)
    print(sep_str)
    for row in rows:
        print(" | ".join(val.ljust(w) for val, w in zip(row, col_widths)))
    print("")


def main():
    target = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "."
    target_path = Path(target)

    # Collect ODB files
    if target_path.is_file() and target_path.suffix == ".odb":
        odb_files = [target_path]
    elif target_path.is_dir():
        odb_files = sorted(target_path.glob("t049_*.odb"))
        if not odb_files:
            odb_files = sorted(target_path.glob("*.odb"))
    else:
        print(f"Target path not found: {target}")
        sys.exit(1)

    if not odb_files:
        print(f"No ODB files found in {target}")
        sys.exit(0)

    print(f"Found {len(odb_files)} ODB file(s) to process.")
    results = []
    for odb_file in odb_files:
        try:
            res = extract_single_odb(odb_file)
            results.append(res)
        except Exception as e:
            print(f"Error extracting {odb_file.name}: {e}")

    # Output options
    json_path = "ball_tests_summary.json"
    csv_path = "ball_tests_summary.csv"
    if "--json" in sys.argv:
        idx = sys.argv.index("--json")
        if idx + 1 < len(sys.argv):
            json_path = sys.argv[idx + 1]
    if "--csv" in sys.argv:
        idx = sys.argv.index("--csv")
        if idx + 1 < len(sys.argv):
            csv_path = sys.argv[idx + 1]

    # Save JSON
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"Saved extraction summary JSON: {json_path}")

    # Save CSV
    if results:
        fieldnames = list(results[0].keys())
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        print(f"Saved extraction summary CSV: {csv_path}")

    # Print summary table
    if results:
        print_markdown_table(results)


if __name__ == "__main__":
    main()
