"""Generate the T9 (Stage 3: Jacobian/collapse failure trigger) verification
decks into verification/roar/t9/.

Purpose: engineering strain is bounded at -1 under compression (zero
volume), so a tension-oriented EPS_FAIL like the goal's suggested ~1.0
structurally cannot catch compression/shear collapse. The Jacobian trigger
(min det(F) over the element's 8 Gauss points, added to
uel/VUEL_failure.for in this stage) exists for that case. Two single-VU1-
hex decks, IPLAST=0 (plasticity deliberately OFF here, same one-new-
mechanism-at-a-time approach as every earlier stage) and EPS_FAIL set
unreachably large (10.0) so the engineering-strain trigger cannot fire
first and mask whether the Jacobian trigger is doing the actual work:

- t9_heavy_compression: the SAME clean uniaxial-stress BC pattern as
  T6/T7/T8 (full back face x=0 pinned in x only; minimal corner/edge pins
  for rigid-body removal), driven to u1=-0.97 (an affine compression
  pushing F11 -> 0.03, comfortably below JAC_FAIL, well before the
  physically-unreachable u1=-1.0 exact singularity). Engineering strain
  here (|eps|=0.97) stays under EPS_FAIL=10 by construction, isolating
  the Jacobian path.
- t9_shear_collapse: back face (x=0, nodes 1,4,5,8) FULLY fixed (all 3
  DOFs -- a cantilever base, not the minimal-pin pattern, since this test
  is not trying to reproduce a clean analytic uniaxial state) and a
  COMBINED large shear (+2.5, several times the unit edge length) and
  compression (-0.6) applied to the driven face (nodes 2,3,6,7) together,
  via one amplitude. This gives a genuinely non-uniform per-Gauss-point
  deformation gradient (unlike the affine compression case), exercising
  the general det(F) computation/trigger path rather than the special
  uniaxial case.

JAC_FAIL = 0.05 (props(11)), the goal's suggested starting value -- a
tunable default, not independently validated here.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "verification" / "roar" / "t9"
OUT.mkdir(parents=True, exist_ok=True)

NODES = {
    1: (0.0, 0.0, 0.0), 2: (1.0, 0.0, 0.0), 3: (1.0, 1.0, 0.0), 4: (0.0, 1.0, 0.0),
    5: (0.0, 0.0, 1.0), 6: (1.0, 0.0, 1.0), 7: (1.0, 1.0, 1.0), 8: (0.0, 1.0, 1.0),
}

EMOD = 2.0e11
ENU = 0.3
DENS = 7800.0
BETA_RAYLEIGH = 0.0
B1_BULK = 0.06
B2_BULK = 1.2
EPS_FAIL = 10.0   # unreachable -- isolates the Jacobian path
SIGY0 = 2.5e8
HMOD = 2.0e9
IPLAST = 0        # plasticity deliberately off for this stage
JAC_FAIL = 0.05
T = 1.0e-2


def props_lines():
    vals = [EMOD, ENU, DENS, BETA_RAYLEIGH, B1_BULK, B2_BULK, EPS_FAIL,
            SIGY0, HMOD, float(IPLAST), JAC_FAIL]
    lines = []
    for i in range(0, len(vals), 8):
        lines.append(", ".join(f"{v:.6g}" for v in vals[i:i + 8]))
    return lines


def common_header(name, desc):
    return ["*Heading",
            f"** T9: VUEL_failure.for Stage-3 Jacobian trigger check -- {desc}",
            f"** JAC_FAIL={JAC_FAIL}, EPS_FAIL={EPS_FAIL} (unreachable); "
            "see verification/make_t9_jacobian_trigger.py",
            "** units: SI (m, kg, s, Pa)",
            "*Preprint, echo=NO, model=YES, history=NO, contact=NO",
            "*Part, name=CELL", "*Node"] + \
        [f"{n}, {c[0]:.6g}, {c[1]:.6g}, {c[2]:.6g}" for n, c in NODES.items()] + \
        ["*User Element, type=VU1, nodes=8, coordinates=3, properties=11, "
         "variables=105",
         "1, 2, 3",
         "*Element, type=VU1, elset=HOSTUEL",
         "1, " + ", ".join(str(n) for n in range(1, 9)),
         "*UEL Property, elset=HOSTUEL",
         *props_lines(),
         "*End Part"]


def build_heavy_compression():
    L = common_header("t9_heavy_compression", "heavy uniaxial compression")
    L += ["*Assembly, name=Assembly",
          "*Instance, name=CELL-1, part=CELL",
          "*End Instance",
          "*Nset, nset=FIXED, instance=CELL-1", "1",
          "*Nset, nset=DRIVEN, instance=CELL-1", "2, 3, 6, 7",
          "*Nset, nset=ALLN, instance=CELL-1", "1, 2, 3, 4, 5, 6, 7, 8",
          "*End Assembly"]
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
          "DRIVEN, 1, 1, -0.97",
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


def build_shear_collapse():
    L = common_header("t9_shear_collapse", "combined shear + compression collapse")
    L += ["*Assembly, name=Assembly",
          "*Instance, name=CELL-1, part=CELL",
          "*End Instance",
          "*Nset, nset=FIXED, instance=CELL-1", "1, 4, 5, 8",
          "*Nset, nset=DRIVEN, instance=CELL-1", "2, 3, 6, 7",
          "*Nset, nset=ALLN, instance=CELL-1", "1, 2, 3, 4, 5, 6, 7, 8",
          "*End Assembly"]
    L += ["*Amplitude, name=RAMP, definition=SMOOTH STEP",
          f"0., 0., {T:.6g}, 1."]
    L += ["*Step, name=S1",
          "*Dynamic, Explicit",
          f", {T:.6g}",
          # Cantilever base: back face fully fixed (not the minimal-pin
          # pattern -- this test does not need a clean uniform-stress
          # comparison, just a genuinely non-affine collapsing shape).
          "*Boundary",
          "FIXED, 1, 3",
          # -0.6/+2.5 (first attempt) only got min(detF) down to 0.091 by
          # the end of the ramp -- above JAC_FAIL=0.05, so the trigger was
          # never actually exercised (confirmed via temporary debug
          # instrumentation, ROAR job 55972119). -0.8/+4.0 pushes further.
          "*Boundary, amplitude=RAMP",
          "DRIVEN, 1, 1, -0.8",
          "DRIVEN, 2, 2, 4.0",
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
    user_src = (ROOT / "uel" / "VUEL_failure.for").read_text()
    decks = {
        "t9_heavy_compression": build_heavy_compression(),
        "t9_shear_collapse": build_shear_collapse(),
    }
    names = []
    for name, text in decks.items():
        (OUT / f"{name}.inp").write_text(text, newline='')
        (OUT / f"{name}_user.for").write_text(user_src, newline='')
        names.append(name)
    (OUT / "decks_t9.txt").write_text("\n".join(names) + "\n", newline='')
    print(f"wrote {len(names)} decks to {OUT}")


if __name__ == "__main__":
    main()
