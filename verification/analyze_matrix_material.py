"""Compare VUEL vs native single-element curves from dump_matrix_curves.py CSVs.

Usage: python analyze_matrix_material.py <results dir> [rate tag ...]
Engineering stress = F / SIZE^2, strain = u / SIZE, energies per unit volume.
Prints peak/plateau stress, strain at 50% and 99% stress loss after the peak,
the energy balance, and the max relative stress difference up to the common
onset window. Exit code 1 if any hard criterion fails.
"""
import csv
import sys
from pathlib import Path

SIZE = 1.0e-3
VOL = SIZE ** 3
AREA = SIZE ** 2
TOL_STRESS = 0.03      # max relative stress difference before softening
TOL_ENERGY = 0.03      # relative energy-balance residual
TOL_DISSIP = 0.05      # VUEL vs native total dissipation (ALLPD + ALLDMD)


def read(path):
    with open(path) as f:
        return list(csv.DictReader(f))


def curve(name, d):
    rows = read(d / (name + "_curve.csv"))
    return ([abs(float(r["u1"])) / SIZE for r in rows],
            [abs(float(r["F"])) / AREA / 1e6 for r in rows])


def energy(name, d):
    rows = read(d / (name + "_energy.csv"))
    last = {k: float(v) for k, v in rows[-1].items()}
    return {k: v / VOL for k, v in last.items() if k != "t"}


def interp(x, xs, ys):
    if x <= xs[0]:
        return ys[0]
    for i in range(1, len(xs)):
        if x <= xs[i]:
            t = (x - xs[i - 1]) / (xs[i] - xs[i - 1]) if xs[i] > xs[i - 1] else 0.0
            return ys[i - 1] + t * (ys[i] - ys[i - 1])
    return ys[-1]


def landmarks(xs, ys):
    pk = max(ys)
    ip = ys.index(pk)
    half = next((xs[i] for i in range(ip, len(ys)) if ys[i] < 0.5 * pk), None)
    zero = next((xs[i] for i in range(ip, len(ys)) if ys[i] < 0.01 * pk), None)
    return pk, xs[ip], half, zero


def main():
    d = Path(sys.argv[1])
    tags = sys.argv[2:] or ["r0p01", "r1", "r1000"]
    ok = True
    for mode in ("tension", "compression", "shear"):
        for tag in tags:
            v, n = "vuel_%s_%s" % (mode, tag), "native_%s_%s" % (mode, tag)
            if not (d / (v + "_curve.csv")).exists() or not (d / (n + "_curve.csv")).exists():
                print("%-22s MISSING" % ("%s %s" % (mode, tag)))
                ok = False
                continue
            vx, vy = curve(v, d)
            nx, ny = curve(n, d)
            vl, nl = landmarks(vx, vy), landmarks(nx, ny)
            # stress difference up to 90% of the earlier softening strain
            lim = 0.9 * min(x for x in (vl[2], nl[2]) if x is not None) if (vl[2] and nl[2]) else 0.0
            diffs = [abs(vy[i] - interp(vx[i], nx, ny)) / max(nl[0], 1e-9) for i in range(len(vx)) if vx[i] <= lim]
            dmax = max(diffs) if diffs else float("nan")
            ev, en = energy(v, d), energy(n, d)
            # VUEL ALLIE is elastic only; native ALLIE includes ALLPD and ALLDMD
            ev_diss = ev["ALLPD"] + ev["ALLDMD"]
            en_diss = en["ALLPD"] + en["ALLDMD"]
            bal_v = abs(ev["ALLWK"] - (ev["ALLIE"] + ev_diss + ev["ALLKE"])) / max(abs(ev["ALLWK"]), 1.0)
            bal_n = abs(en["ALLWK"] - (en["ALLIE"] + en["ALLKE"])) / max(abs(en["ALLWK"]), 1.0)
            ddiss = abs(ev_diss - en_diss) / max(en_diss, 1.0)
            good = dmax < TOL_STRESS and bal_v < TOL_ENERGY and ddiss < TOL_DISSIP
            ok = ok and good
            print("%-22s %s" % ("%s %s" % (mode, tag), "PASS" if good else "FAIL"))
            print("   peak MPa     vuel %7.2f @%.3f   native %7.2f @%.3f" % (vl[0], vl[1], nl[0], nl[1]))
            print("   50%% loss at  vuel %s   native %s     99%% loss  vuel %s   native %s" % tuple(
                "%.3f" % x if x is not None else "none" for x in (vl[2], nl[2], vl[3], nl[3])))
            print("   max stress diff (pre-softening) %.2f%%" % (100 * dmax))
            print("   diss J/m3    vuel PD %.3e + DMD %.3e   native PD %.3e + DMD %.3e   diff %.2f%%" % (
                ev["ALLPD"], ev["ALLDMD"], en["ALLPD"], en["ALLDMD"], 100 * ddiss))
            print("   energy balance residual  vuel %.2f%%   native %.2f%%   KE/WK vuel %.2f%%" % (
                100 * bal_v, 100 * bal_n, 100 * ev["ALLKE"] / max(ev["ALLWK"], 1.0)))
    print("OVERALL", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
