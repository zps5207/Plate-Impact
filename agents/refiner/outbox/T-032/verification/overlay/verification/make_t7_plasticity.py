"""Generate the T7 (Stage 1: linear-hardening J2 plasticity on VUEL_failure.for)
verification decks into verification/roar/t7/.

Purpose: verify the additive Green-Lagrange J2 return-mapping added to
uel/VUEL_failure.for (docs/VUEL_PLASTIC_FAILURE_STAGE0_PLAN.md) against the
analytic 1-D elastic/linear-hardening bar response, in both tension and
compression, including an unloading leg. See
verification/t7_check_plasticity.py for the analytic comparison itself.

Geometry/BC: single VU1 hex (unit cube), same uniaxial-stress BC pattern
verification/roar/t6/ uses (full back face x=0 pinned in x, one corner
fully pinned and two edges pinned in y/z only enough to remove rigid body
modes -- NOT full-face lateral clamping, so the element is free to develop
whatever lateral (Poisson) contraction/expansion the material model wants,
i.e. a true uniaxial-STRESS state, displacement-controlled axially). A
single linear hex's trilinear shape functions represent this problem's
exact uniform-strain solution exactly, so comparing against the analytic
1-D bar is a tight check, not merely a qualitative one -- confirmed
already for the pure-elastic case in verification/roar/t6/.

EPS_FAIL (props(7)) is set far out of reach (10.0) for every T7 deck: this
stage verifies plasticity in isolation from the failure criterion (that
interaction is Stage 2).
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "verification" / "roar" / "t7"
OUT.mkdir(parents=True, exist_ok=True)

NODES = {
    1: (0.0, 0.0, 0.0), 2: (1.0, 0.0, 0.0), 3: (1.0, 1.0, 0.0), 4: (0.0, 1.0, 0.0),
    5: (0.0, 0.0, 1.0), 6: (1.0, 0.0, 1.0), 7: (1.0, 1.0, 1.0), 8: (0.0, 1.0, 1.0),
}

# Placeholder steel-like properties (user-confirmed for Stage 1, 2026-10-01):
EMOD = 2.0e11      # Pa
ENU = 0.3
DENS = 7800.0      # kg/m^3
BETA_RAYLEIGH = 0.0
# Bulk viscosity OFF (0) for every T7 deck, including compression: Stage 1
# is verifying the PLASTICITY algorithm against an analytic bar response,
# and bulk viscosity is an extra numerical-damping stress contribution
# (active whenever the volumetric strain rate is compressive) that would
# otherwise contaminate the RF1-vs-analytic-S11 comparison in the
# compression deck specifically.
B1_BULK = 0.0
B2_BULK = 0.0
EPS_FAIL = 10.0    # unreachable in this stage -- isolates plasticity
SIGY0 = 2.5e8      # Pa (250 MPa)
HMOD = 2.0e9       # Pa (10% of E)

T = 1.0e-2  # step time per leg, s


def props_lines(iplast):
    """*UEL Property data lines allow at most 8 values per line (confirmed
    against the Abaqus Keywords Reference: "Eight values per line are used
    for both real and integer values in the *UEL PROPERTY keyword data
    lines") -- found the hard way when nprops grew to 10 for Stage 1:
    putting all 10 on one line silently truncates props(9:10) (HMOD,
    IPLAST) to zero with NO error from Abaqus, which looks exactly like a
    disabled plasticity path instead of a deck-formatting mistake. See
    docs/abaqus-explicit-quirks.md and
    docs/VUEL_PLASTIC_FAILURE_STAGE1_REPORT_2026-10-01.md."""
    vals = [EMOD, ENU, DENS, BETA_RAYLEIGH, B1_BULK, B2_BULK, EPS_FAIL,
            SIGY0, HMOD, float(iplast)]
    lines = []
    for i in range(0, len(vals), 8):
        lines.append(", ".join(f"{v:.6g}" for v in vals[i:i + 8]))
    return lines


def build_inp(name, iplast, keyframes):
    """keyframes: list of (time_s, absolute_disp) pairs AFTER an implicit
    (0, 0) start, all within a SINGLE *Dynamic, Explicit step. Multi-step
    *Boundary restart semantics (whether a new step's amplitude ramps from
    0 or from the previous step's held value) is exactly the kind of
    Abaqus behavior the goal says not to guess -- so a tension-then-unload
    leg is built as one continuous SMOOTH STEP amplitude table with
    multiple (time, value) keyframes instead (Abaqus smooths each
    consecutive pair independently, zero slope/curvature at each
    keyframe), referenced by one *Boundary whose magnitude is the peak
    absolute displacement; amplitude values are each keyframe's
    displacement expressed as a fraction of that peak."""
    peak = max(abs(d) for _, d in keyframes)
    L = []
    L += ["*Heading",
          f"** T7: VUEL_failure.for Stage-1 plasticity check -- {name}",
          f"** IPLAST={iplast}, SIGY0={SIGY0:.6g} Pa, HMOD={HMOD:.6g} Pa; "
          "see verification/make_t7_plasticity.py",
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
          *props_lines(iplast)]
    L += ["*End Part"]
    L += ["*Assembly, name=Assembly",
          "*Instance, name=CELL-1, part=CELL",
          "*End Instance"]
    L += ["*Nset, nset=FIXED, instance=CELL-1", "1",
          "*Nset, nset=DRIVEN, instance=CELL-1", "2, 3, 6, 7",
          "*Nset, nset=ALLN, instance=CELL-1", "1, 2, 3, 4, 5, 6, 7, 8"]
    L += ["*End Assembly"]

    total_t = keyframes[-1][0]
    amp_rows = ["0., 0."]
    for t, d in keyframes:
        amp_rows.append(f"{t:.6g}, {d/peak:.6g}")

    L += ["*Amplitude, name=RAMP, definition=SMOOTH STEP"]
    L += amp_rows
    L += ["*Step, name=S1",
          "*Dynamic, Explicit",
          f", {total_t:.6g}",
          "*Boundary",
          "FIXED, 1, 3",
          "CELL-1.4, 1, 1",
          "CELL-1.4, 3, 3",
          "CELL-1.5, 1, 1",
          "CELL-1.5, 2, 2",
          "CELL-1.8, 1, 1",
          "*Boundary, amplitude=RAMP",
          f"DRIVEN, 1, 1, {peak:.6g}",
          "*Output, history, frequency=1000000",
          "*Node Output, nset=ALLN",
          "RF1, RF2, RF3, U1, U2, U3",
          "*Output, field, number interval=20",
          "*Node Output",
          "U, RF",
          "*Output, history, time interval=2e-05",
          "*Energy Output",
          "ALLIE, ALLKE, ALLWK, ALLVD, ALLAE, ALLPD, ETOTAL",
          "*End Step"]
    return "\n".join(L) + "\n"


def main():
    # Peak engineering strain kept modest (a few %) so Green-Lagrange/PK2
    # closely track small-strain engineering stress/strain -- this stage
    # is verifying the PLASTICITY ALGORITHM, not large-strain kinematics.
    decks = {
        # Pure elastic control (IPLAST=0): must reproduce the original
        # St. Venant-Kirchhoff elastic law exactly.
        "t7_elastic_control": (0, [(T, 0.02)]),
        # Monotonic tension well past yield (eps_y = SIGY0/E = 0.00125).
        "t7_tension_plastic": (1, [(T, 0.04)]),
        # Monotonic compression well past yield.
        "t7_compression_plastic": (1, [(T, -0.04)]),
        # Tension past yield, then a SMALL partial unload -- checks the
        # elastic unload slope and permanent (plastic) set. The unload
        # excursion (0.04 -> 0.038, d_eps=0.002) is kept inside the
        # elastic range on unload (2*sigma_y(PEEQ_max)/E ~ 0.0033 here) so
        # the leg stays elastic; a first attempt used too large an
        # excursion (down to 0.02) and the FEM correctly re-yielded in
        # compression (isotropic hardening), which is NOT a bug but does
        # need a reverse-yield-aware analytic model this check script
        # does not implement -- simplest fix is to not cross back into
        # that regime in the first place. Keyframes are ABSOLUTE times.
        "t7_tension_unload": (1, [(T, 0.04), (2 * T, 0.038)]),
    }
    names = []
    # newline='' everywhere below: these files are read by a bash `for`
    # loop on ROAR (Linux), and Path.write_text's default text-mode
    # newline translation turns "\n" into "\r\n" on Windows, which bash
    # then treats as part of the filename (found the hard way -- see
    # docs/abaqus-explicit-quirks.md).
    user_src = (ROOT / "uel" / "VUEL_failure.for").read_text()
    for name, (iplast, keyframes) in decks.items():
        (OUT / f"{name}.inp").write_text(
            build_inp(name, iplast, keyframes), newline='')
        (OUT / f"{name}_user.for").write_text(user_src, newline='')
        names.append(name)
    (OUT / "decks_t7.txt").write_text("\n".join(names) + "\n", newline='')
    print(f"wrote {len(names)} decks to {OUT}")


if __name__ == "__main__":
    main()
