#!/usr/bin/env python3
"""Analysis script for T-008: Auditing island history, stress states, and criterion mismatches.

Processes:
- inbox/T-008/island_history_v2.json
- inbox/T-010/evidence/el_elements.csv (or inbox/T-008/evidence if present)
- inbox/T-008/evidence/flat_v2_output.inp
"""

from __future__ import annotations
import csv
import json
from pathlib import Path


def main():
    root = Path(__file__).resolve().parent
    inbox = root.parents[1] / "inbox" / "T-008"
    inbox_t10 = root.parents[1] / "inbox" / "T-010"

    history_file = inbox / "island_history_v2.json"
    el_csv = inbox_t10 / "evidence" / "el_elements.csv"

    print("=" * 60)
    print("T-008 MECHANICS AND KINEMATICS AUDIT")
    print("=" * 60)

    # 1. Audit island_history_v2.json
    if history_file.exists():
        with open(history_file) as f:
            data = json.load(f)
        islands = data["islands"]
        hist = data["hist"]
        print(f"Total Islands in history: {len(islands)}")

        mises_max_all = []
        p_max_all = []
        uz_max_all = []
        vz_max_all = []
        peeq_max_all = []

        for isl in islands:
            h = hist[str(isl)]
            mises_max_all.append(max(h["mises"]))
            p_max_all.append(max(abs(x) for x in h["p"]))
            uz_max_all.append(min(h["uz"]))
            vz_max_all.append(min(h["vz"]))
            peeq_max_all.append(max(h["peeq"]))

        print(f"Island PEEQ max: {max(peeq_max_all):.6f}")
        print(f"Island Mises max: {max(mises_max_all):.2f} Pa (Yield threshold = 61.1 Pa)")
        print(f"Island Mises median: {sorted(mises_max_all)[len(mises_max_all)//2]:.2f} Pa")
        print(f"Island Mises min: {min(mises_max_all):.2f} Pa")
        print(f"Island Peak |uz|: max={abs(min(uz_max_all))*1e3:.4f} mm, median={abs(sorted(uz_max_all)[len(uz_max_all)//2])*1e3:.4f} mm")
        print(f"Island Peak |vz|: max={abs(min(vz_max_all)):.2f} m/s, median={abs(sorted(vz_max_all)[len(vz_max_all)//2]):.2f} m/s")

    # 2. Audit el_elements.csv
    if el_csv.exists():
        with open(el_csv) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        near_axis = [r for r in rows if float(r["r"]) <= 0.010]
        alive_near = [r for r in near_axis if float(r["alive_end"]) == 1]
        dead_near = [r for r in near_axis if float(r["alive_end"]) == 0]

        vu1_failed_alive = [
            r for r in alive_near
            if float(r["first_eng_frame"]) > 0 or float(r["first_jac_frame"]) > 0
        ]
        vu1_intact_alive = [
            r for r in alive_near
            if float(r["first_eng_frame"]) < 0 and float(r["first_jac_frame"]) < 0
        ]

        print("\nNear-Axis Host Classification (r <= 10 mm):")
        print(f"  Total: {len(near_axis)}")
        print(f"  Ghost Deleted: {len(dead_near)}")
        print(f"  Ghost Alive: {len(alive_near)}")
        print(f"    - Alive & VU1 Intact: {len(vu1_intact_alive)} (No criterion mismatch; unreached by load)")
        print(f"    - Alive & VU1 Failed: {len(vu1_failed_alive)} (True criterion mismatch)")

        print("\nDetails of the 11 Criterion Mismatch Hosts:")
        for r in vu1_failed_alive:
            print(
                f"  Host {int(float(r['label']))}: z={float(r['z'])*1e3:.2f} mm, r={float(r['r'])*1e3:.2f} mm, "
                f"meas_max={float(r['meas_max']):.4f} (EPS_FAIL=0.1138), "
                f"mises_max={float(r['mises_max_alive']):.2f} Pa (sigy=61.1 Pa), peeq={float(r['peeq_max']):.2e}"
            )

        # Far-field elements
        far_field = [r for r in rows if float(r["r"]) > 0.025]
        ghost_dead_vu1_alive = [
            r for r in far_field
            if float(r["alive_end"]) == 0 and float(r["first_eng_frame"]) < 0 and float(r["first_jac_frame"]) < 0
        ]
        print(f"\nFar-Field (r > 25 mm):")
        print(f"  Total hosts: {len(far_field)}")
        print(f"  Ghost deleted but VU1 alive (fiber shear pull): {len(ghost_dead_vu1_alive)}")


if __name__ == "__main__":
    main()
