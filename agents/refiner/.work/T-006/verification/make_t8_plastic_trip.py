"""Generate the T8 (Stage 2: engineering-strain failure trigger ON TOP OF
the Stage-1 plastic element) verification deck into verification/roar/t8/.

Purpose: Stage 1 (verification/make_t7_plasticity.py) verified the J2
linear-hardening plasticity in isolation (EPS_FAIL set unreachably large).
This stage re-enables the engineering-strain failure trigger
(uel/VUEL_failure.for's original behavior, unchanged by Stage 1 -- the
failure check still only looks at max|eng_i| from the Green-Lagrange
normal strains, independent of the plastic state) and confirms it still
works correctly with plasticity active: the element should flow plastically
well before it fails, then trip cleanly and go to exactly zero
stress/force, same as the purely-elastic check in verification/roar/t6/.

Same single-VU1-hex, uniaxial-stress BC pattern, unit cube, as T6/T7
(verification/make_t7_plasticity.py has the derivation/citation for why
this BC gives a clean, exact uniform-strain comparison). Same placeholder
material (E=200 GPa, nu=0.3, SIGY0=250 MPa, HMOD=2 GPa) as T7.

Props line must stay <=8 values per *UEL Property data line (Abaqus
silently truncates beyond that -- see docs/abaqus-explicit-quirks.md and
the Stage 1 report; this generator reproduces T7's props_lines() helper
rather than importing it, to keep each verification/make_tN_*.py script
self-contained per this project's existing convention).
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "verification" / "roar" / "t8"
OUT.mkdir(parents=True, exist_ok=True)

NODES = {
    1: (0.0, 0.0, 0.0), 2: (1.0, 0.0, 0.0), 3: (1.0, 1.0, 0.0), 4: (0.0, 1.0, 0.0),
    5: (0.0, 0.0, 1.0), 6: (1.0, 0.0, 1.0), 7: (1.0, 1.0, 1.0), 8: (0.0, 1.0, 1.0),
}

EMOD = 2.0e11
ENU = 0.3
DENS = 7800.0
BETA_RAYLEIGH = 0.0  # off, same reasoning as T7: isolate the trip from damping noise
B1_BULK = 0.0
B2_BULK = 0.0
SIGY0 = 2.5e8
HMOD = 2.0e9
IPLAST = 1

# EPS_FAIL chosen comfortably past yield (eps_y = SIGY0/EMOD = 0.00125) so
# the element plastically flows for a long stretch before tripping, and
# comfortably before the deck's peak applied strain (0.04) so the trip is
# actually exercised, not just approached.
EPS_FAIL = 0.02
PEAK_DISP = 0.04
T = 1.0e-2


def props_lines():
    vals = [EMOD, ENU, DENS, BETA_RAYLEIGH, B1_BULK, B2_BULK, EPS_FAIL,
            SIGY0, HMOD, float(IPLAST)]
    lines = []
    for i in range(0, len(vals), 8):
        lines.append(", ".join(f"{v:.6g}" for v in vals[i:i + 8]))
    return lines


def build_inp():
    L = []
    L += ["*Heading",
          "** T8: VUEL_failure.for Stage-2 check -- engineering-strain "
          "failure trigger on a plastic element",
          f"** EPS_FAIL={EPS_FAIL}, SIGY0={SIGY0:.6g} Pa, HMOD={HMOD:.6g} "
          "Pa, IPLAST=1; see verification/make_t8_plastic_trip.py",
          "** units: SI (m, kg, s, Pa)",
          "*Preprint, echo=NO, model=YES, history=NO, contact=NO"]
    L += ["*Part, name=CELL", "*Node"]
    L += [f"{n}, {c[0]:.6g}, {c[1]:.6g}, {c[2]:.6g}" for n, c in NODES.items()]
    L += ["*User Element, type=VU1, nodes=8, coordinates=3, properties=10, "
          "variables=105",
          "1, 2, 3",
          "*Element, type=VU1, elset=HOSTUEL",
          "1, " + ", ".join(str(n) for n in range(1, 9)),
          "*UEL Property, elset=HOSTUEL",
          *props_lines()]
    L += ["*End Part"]
    L += ["*Assembly, name=Assembly",
          "*Instance, name=CELL-1, part=CELL",
          "*End Instance"]
    L += ["*Nset, nset=FIXED, instance=CELL-1", "1",
          "*Nset, nset=DRIVEN, instance=CELL-1", "2, 3, 6, 7",
          "*Nset, nset=ALLN, instance=CELL-1", "1, 2, 3, 4, 5, 6, 7, 8"]
    L += ["*End Assembly"]
    L += ["*Amplitude, name=RAMP, definition=SMOOTH STEP",
          f"0., 0., {T:.6g}, 1."]
    L += ["*Step, name=S1",
          "*Dynamic, Explicit",
          f", {T:.6g}",
          "*Boundary",
          "FIXED, 1, 3",
          "CELL-1.4, 1, 1",
          "CELL-1.4, 3, 3",
          "CELL-1.5, 1, 1",
          "CELL-1.5, 2, 2",
          "CELL-1.8, 1, 1",
          "*Boundary, amplitude=RAMP",
          f"DRIVEN, 1, 1, {PEAK_DISP:.6g}",
          "*Output, history, frequency=1000000",
          "*Node Output, nset=ALLN",
          "RF1, RF2, RF3, U1, U2, U3",
          "*Output, field, number interval=40",
          "*Node Output",
          "U, RF",
          "*Output, history, time interval=2e-05",
          "*Energy Output",
          "ALLIE, ALLKE, ALLWK, ALLVD, ALLAE, ALLPD, ETOTAL",
          "*End Step"]
    return "\n".join(L) + "\n"


def main():
    name = "t8_tension_trip"
    (OUT / f"{name}.inp").write_text(build_inp(), newline='')
    user_src = (ROOT / "uel" / "VUEL_failure.for").read_text()
    (OUT / f"{name}_user.for").write_text(user_src, newline='')
    (OUT / "decks_t8.txt").write_text(name + "\n", newline='')
    print(f"wrote 1 deck to {OUT}")


if __name__ == "__main__":
    main()
