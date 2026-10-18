"""Generate the T10 (Stage 4: dead-state hygiene) verification decks into
verification/roar/t10/.

Three decks, each isolating one part of Stage 4's checklist:

- t10_damping_hygiene: single VU1 hex, same uniaxial-stress BC as T6/T7/T8,
  but with NONZERO Rayleigh damping and bulk viscosity (unlike every
  earlier stage's decks, which zeroed both to keep comparisons clean --
  here the whole point is to have real damping active so its dissipation
  bookkeeping can be checked). Driven well past EPS_FAIL. Checks: whole-
  model ALLVD (viscous dissipation) stops growing the increment after the
  element fails (confirms the Stage 4 fix: DAMP_DISSIP/BV_DISSIP
  accumulation is now skipped once ELEM_ALREADY_FAILED, same guard ELIE/
  PLASTIC_DISSIP already had), ALLIE drops to ~0 at the same increment
  (the element's stored elastic energy is not preserved or redirected
  anywhere once it dies -- a deliberate, documented simplification, not a
  bug), and dtimeStable implicitly: the run should not need abnormally
  small increments to stay stable after the element dies (checked via the
  .sta file's own reported stable increment column).

- t10_two_element: two IDENTICAL VU1 hexes in series along x (sharing a
  4-node face), SAME EPS_FAIL, driven in tension from the far end with
  the near end fixed. Two equal-stiffness segments in series split an
  imposed end-to-end displacement equally, so both segments reach the
  failure threshold at essentially the same increment -- this is deliberate
  (not an attempt at staggered failure, see t10_three_chain for that): it
  cleanly demonstrates a node (the shared interface) becoming FULLY
  orphaned (every element touching it has failed) in a single step, so its
  subsequent free-flight (zero net force -> constant velocity) behavior
  can be checked directly against its own velocity history.

- t10_three_chain: three IDENTICAL-material VU1 hexes in series, but with
  STAGGERED EPS_FAIL (elem1 lowest, elem3 highest) so they are forced to
  fail in sequence as the far end is driven further -- genuine cascading
  failure, observational per the goal ("Report what happens to nodes
  whose elements have all failed"), not a strict pass/fail check.

Plasticity off (IPLAST=0) in every T10 deck -- Stage 4 is about dead-state
bookkeeping, not plasticity; keeping it out avoids conflating the two.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "verification" / "roar" / "t10"
OUT.mkdir(parents=True, exist_ok=True)

EMOD = 2.0e11
ENU = 0.3
DENS = 7800.0
SIGY0 = 2.5e8
HMOD = 2.0e9
IPLAST = 0
JAC_FAIL = 0.05
T = 1.0e-2


def props_lines(eps_fail, beta=0.0, b1=0.0, b2=0.0):
    vals = [EMOD, ENU, DENS, beta, b1, b2, eps_fail, SIGY0, HMOD,
            float(IPLAST), JAC_FAIL]
    lines = []
    for i in range(0, len(vals), 8):
        lines.append(", ".join(f"{v:.6g}" for v in vals[i:i + 8]))
    return lines


UEL_DEF = ("*User Element, type=VU1, nodes=8, coordinates=3, "
           "properties=11, variables=105\n1, 2, 3")


def build_damping_hygiene():
    L = ["*Heading",
         "** T10: dead-state hygiene -- nonzero damping, check ALLVD/ALLIE "
         "stop changing after the trip",
         "** see verification/make_t10_dead_state.py",
         "** units: SI (m, kg, s, Pa)",
         "*Preprint, echo=NO, model=YES, history=NO, contact=NO",
         "*Part, name=CELL", "*Node",
         "1, 0, 0, 0", "2, 1, 0, 0", "3, 1, 1, 0", "4, 0, 1, 0",
         "5, 0, 0, 1", "6, 1, 0, 1", "7, 1, 1, 1", "8, 0, 1, 1",
         UEL_DEF,
         "*Element, type=VU1, elset=HOSTUEL",
         "1, 1, 2, 3, 4, 5, 6, 7, 8",
         "*UEL Property, elset=HOSTUEL",
         *props_lines(eps_fail=0.02, beta=1.0e-6, b1=0.06, b2=1.2),
         "*End Part",
         "*Assembly, name=Assembly",
         "*Instance, name=CELL-1, part=CELL",
         "*End Instance",
         "*Nset, nset=FIXED, instance=CELL-1", "1",
         "*Nset, nset=DRIVEN, instance=CELL-1", "2, 3, 6, 7",
         "*Nset, nset=ALLN, instance=CELL-1", "1, 2, 3, 4, 5, 6, 7, 8",
         "*End Assembly",
         "*Amplitude, name=RAMP, definition=SMOOTH STEP",
         f"0., 0., {T:.6g}, 1.",
         "*Step, name=S1",
         "*Dynamic, Explicit",
         f", {T:.6g}",
         "*Boundary",
         "FIXED, 1, 3",
         "CELL-1.4, 1, 1", "CELL-1.4, 3, 3",
         "CELL-1.5, 1, 1", "CELL-1.5, 2, 2",
         "CELL-1.8, 1, 1",
         "*Boundary, amplitude=RAMP",
         "DRIVEN, 1, 1, 0.04",
         "*Output, history, frequency=1000000",
         "*Node Output, nset=ALLN",
         "RF1, RF2, RF3, U1, U2, U3",
         "*Output, field, number interval=40",
         "*Node Output",
         "U, RF, V",
         "*Output, history, time interval=2e-05",
         "*Energy Output",
         "ALLIE, ALLKE, ALLWK, ALLVD, ALLAE, ALLPD, ETOTAL",
         "*End Step"]
    return "\n".join(L) + "\n"


def build_two_element():
    L = ["*Heading",
         "** T10: two-element chain, same EPS_FAIL -- simultaneous "
         "failure, orphaned interface node free-flight check",
         "** see verification/make_t10_dead_state.py",
         "** units: SI (m, kg, s, Pa)",
         "*Preprint, echo=NO, model=YES, history=NO, contact=NO",
         "*Part, name=CELL", "*Node",
         "1, 0, 0, 0", "2, 1, 0, 0", "3, 1, 1, 0", "4, 0, 1, 0",
         "5, 0, 0, 1", "6, 1, 0, 1", "7, 1, 1, 1", "8, 0, 1, 1",
         "9, 2, 0, 0", "10, 2, 1, 0", "11, 2, 0, 1", "12, 2, 1, 1",
         UEL_DEF,
         "*Element, type=VU1, elset=ELEM1",
         "1, 1, 2, 3, 4, 5, 6, 7, 8",
         "*Element, type=VU1, elset=ELEM2",
         "2, 2, 9, 10, 3, 6, 11, 12, 7",
         "*UEL Property, elset=ELEM1",
         *props_lines(eps_fail=0.02),
         "*UEL Property, elset=ELEM2",
         *props_lines(eps_fail=0.02),
         "*End Part",
         "*Assembly, name=Assembly",
         "*Instance, name=CELL-1, part=CELL",
         "*End Instance",
         "*Nset, nset=FIXED, instance=CELL-1", "1",
         "*Nset, nset=DRIVEN, instance=CELL-1", "9, 10, 11, 12",
         "*Nset, nset=INTERFACE, instance=CELL-1", "2, 3, 6, 7",
         "*Nset, nset=ALLN, instance=CELL-1",
         "1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12",
         "*End Assembly",
         "*Amplitude, name=RAMP, definition=SMOOTH STEP",
         f"0., 0., {T:.6g}, 1.",
         "*Step, name=S1",
         "*Dynamic, Explicit",
         f", {T:.6g}",
         "*Boundary",
         "FIXED, 1, 3",
         "CELL-1.4, 1, 1", "CELL-1.4, 3, 3",
         "CELL-1.5, 1, 1", "CELL-1.5, 2, 2",
         "CELL-1.8, 1, 1",
         "*Boundary, amplitude=RAMP",
         # total end-to-end displacement 0.1 over length 2 -- two equal
         # segments split it evenly, each reaching ~0.05 engineering
         # strain, comfortably past EPS_FAIL=0.02 for both.
         "DRIVEN, 1, 1, 0.1",
         "*Output, history, frequency=1000000",
         "*Node Output, nset=ALLN",
         "RF1, RF2, RF3, U1, U2, U3, V1, V2, V3",
         "*Output, field, number interval=60",
         "*Node Output",
         "U, RF, V",
         "*Output, history, time interval=2e-05",
         "*Energy Output",
         "ALLIE, ALLKE, ALLWK, ALLVD, ALLAE, ALLPD, ETOTAL",
         "*End Step"]
    return "\n".join(L) + "\n"


def build_three_chain():
    L = ["*Heading",
         "** T10: three-element chain, staggered EPS_FAIL -- cascading "
         "failure observation",
         "** see verification/make_t10_dead_state.py",
         "** units: SI (m, kg, s, Pa)",
         "*Preprint, echo=NO, model=YES, history=NO, contact=NO",
         "*Part, name=CELL", "*Node",
         "1, 0, 0, 0", "2, 1, 0, 0", "3, 1, 1, 0", "4, 0, 1, 0",
         "5, 0, 0, 1", "6, 1, 0, 1", "7, 1, 1, 1", "8, 0, 1, 1",
         "9, 2, 0, 0", "10, 2, 1, 0", "11, 2, 0, 1", "12, 2, 1, 1",
         "13, 3, 0, 0", "14, 3, 1, 0", "15, 3, 0, 1", "16, 3, 1, 1",
         UEL_DEF,
         "*Element, type=VU1, elset=ELEM1",
         "1, 1, 2, 3, 4, 5, 6, 7, 8",
         "*Element, type=VU1, elset=ELEM2",
         "2, 2, 9, 10, 3, 6, 11, 12, 7",
         "*Element, type=VU1, elset=ELEM3",
         "3, 9, 13, 14, 10, 11, 15, 16, 12",
         "*UEL Property, elset=ELEM1",
         *props_lines(eps_fail=0.015),
         "*UEL Property, elset=ELEM2",
         *props_lines(eps_fail=0.025),
         "*UEL Property, elset=ELEM3",
         *props_lines(eps_fail=0.04),
         "*End Part",
         "*Assembly, name=Assembly",
         "*Instance, name=CELL-1, part=CELL",
         "*End Instance",
         "*Nset, nset=FIXED, instance=CELL-1", "1",
         "*Nset, nset=DRIVEN, instance=CELL-1", "13, 14, 15, 16",
         "*Nset, nset=IFACE_A, instance=CELL-1", "2, 3, 6, 7",
         "*Nset, nset=IFACE_B, instance=CELL-1", "9, 10, 11, 12",
         "*Nset, nset=ALLN, instance=CELL-1",
         "1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16",
         "*End Assembly",
         "*Amplitude, name=RAMP, definition=SMOOTH STEP",
         f"0., 0., {T:.6g}, 1.",
         "*Step, name=S1",
         "*Dynamic, Explicit",
         f", {T:.6g}",
         "*Boundary",
         "FIXED, 1, 3",
         "CELL-1.4, 1, 1", "CELL-1.4, 3, 3",
         "CELL-1.5, 1, 1", "CELL-1.5, 2, 2",
         "CELL-1.8, 1, 1",
         "*Boundary, amplitude=RAMP",
         # total displacement 0.3 over length 3 (~0.1 avg strain/segment
         # if split evenly while all elastic) comfortably exceeds even
         # ELEM3's 0.04 threshold, forcing all three to eventually trip.
         "DRIVEN, 1, 1, 0.3",
         "*Output, history, frequency=1000000",
         "*Node Output, nset=ALLN",
         "RF1, RF2, RF3, U1, U2, U3, V1, V2, V3",
         "*Output, field, number interval=60",
         "*Node Output",
         "U, RF, V",
         "*Output, history, time interval=2e-05",
         "*Energy Output",
         "ALLIE, ALLKE, ALLWK, ALLVD, ALLAE, ALLPD, ETOTAL",
         "*End Step"]
    return "\n".join(L) + "\n"


def main():
    user_src = (ROOT / "uel" / "VUEL_failure.for").read_text()
    decks = {
        "t10_damping_hygiene": build_damping_hygiene(),
        "t10_two_element": build_two_element(),
        "t10_three_chain": build_three_chain(),
    }
    names = []
    for name, text in decks.items():
        (OUT / f"{name}.inp").write_text(text, newline='')
        (OUT / f"{name}_user.for").write_text(user_src, newline='')
        names.append(name)
    (OUT / "decks_t10.txt").write_text("\n".join(names) + "\n", newline='')
    print(f"wrote {len(names)} decks to {OUT}")


if __name__ == "__main__":
    main()
