"""Generate the T6 (VUEL engineering-strain failure criterion) verification
decks into verification/roar/t6/.

Purpose (see docs/TODO.md / project goal 2026-10-01): uel/VUEL_failure.for
is a branch of uel/VUEL.for (NOT the production VUEL) that adds a simple
max-abs-normal-engineering-strain failure criterion (props(7) = EPS_FAIL).
Once tripped, the element is made numerically inert (zero stress/force)
from the next increment on. These decks exist to find out empirically
whether Abaqus/Explicit's native element-deletion / conversion-to-particles
machinery honors that state -- i.e. whether the element visually/formally
disappears from the mesh (status field, "number of elements deleted" in
the .sta file, odb element removal) -- or whether it merely goes inert
while still occupying its nodes, since that native machinery is documented
around a material STATUS variable on NATIVE elements, and BUG-020 already
found native *Embedded Element itself does not recognize a VUEL host.

Physical note on "compression test" + engineering strain threshold: a
1-D engineering (nominal) strain cannot reach -1.0 under compression
(that limit corresponds to the material being crushed to zero volume);
it asymptotically approaches -1 but never reaches an arbitrary trip value
like 1.0 in magnitude from the compressive side within a stable analysis.
So two decks are generated:
  - t6_compress_nofail: compress by 60% (eng strain -0.6) with
    EPS_FAIL=1.0 (the goal's suggested value) -- documents that bound by
    construction: this element is NOT expected to fail.
  - t6_compress_trip: the SAME compression loading, but EPS_FAIL=0.3, so
    the element passes through the threshold partway through the step and
    we can observe what Abaqus actually does once svars(.,49) is set.

Geometry/BC pattern follows verification/make_t4.py's single-VU1-hex cell
(no embedded fibers here -- this test isolates host-element failure
behavior from the fiber-embedding question BUG-020 is about).
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "verification" / "roar" / "t6"
OUT.mkdir(parents=True, exist_ok=True)

NODES = {
    1: (0.0, 0.0, 0.0), 2: (1.0, 0.0, 0.0), 3: (1.0, 1.0, 0.0), 4: (0.0, 1.0, 0.0),
    5: (0.0, 0.0, 1.0), 6: (1.0, 0.0, 1.0), 7: (1.0, 1.0, 1.0), 8: (0.0, 1.0, 1.0),
}

HOST_PROPS = dict(E=2.0e11, nu=0.3, rho=7800.0, beta_rayleigh=0.0, b1=0.06, b2=1.2)
T = 1.0e-2  # step time, s -- same order as verification/make_t4.py's T4 decks

COMPRESS_FRAC = 0.6  # engineering strain magnitude reached at end of step (-0.6)


def build_inp(eps_fail):
    """Single-VU1-hex cell, compressed 60% along x, with failure threshold
    `eps_fail` (props(7))."""
    props_line = (f"{HOST_PROPS['E']:.6g}, {HOST_PROPS['nu']:.6g}, "
                  f"{HOST_PROPS['rho']:.6g}, {HOST_PROPS['beta_rayleigh']:.6g}, "
                  f"{HOST_PROPS['b1']:.6g}, {HOST_PROPS['b2']:.6g}, {eps_fail:.6g}")
    L = []
    L += ["*Heading",
          "** T6: VUEL_failure.for engineering-strain failure criterion, "
          "single-element compression test",
          f"** EPS_FAIL (props(7)) = {eps_fail:.6g}; "
          "see verification/make_t6_failure.py",
          "** units: SI (m, kg, s, Pa)",
          "*Preprint, echo=NO, model=YES, history=NO, contact=NO"]
    L += ["*Part, name=CELL", "*Node"]
    L += [f"{n}, {c[0]:.6g}, {c[1]:.6g}, {c[2]:.6g}" for n, c in NODES.items()]
    L += ["*User Element, type=VU1, nodes=8, coordinates=3, properties=7, "
          "variables=49",
          "1, 2, 3",
          "*Element, type=VU1, elset=HOSTUEL",
          "1, " + ", ".join(str(n) for n in range(1, 9)),
          "*UEL Property, elset=HOSTUEL",
          props_line]
    L += ["*End Part"]
    L += ["*Assembly, name=Assembly",
          "*Instance, name=CELL-1, part=CELL",
          "*End Instance"]
    L += ["*Nset, nset=FIXED, instance=CELL-1", "1",
          "*Nset, nset=DRIVEN, instance=CELL-1", "2, 3, 6, 7",
          "*Nset, nset=ALLN, instance=CELL-1", "1, 2, 3, 4, 5, 6, 7, 8"]
    L += ["*End Assembly"]
    # Same minimal rigid-body-removal BC pattern as verification/make_t4.py:
    # pin node1 fully, constrain node4/node5/node8 to remove rotation/shear
    # modes, then drive the x=1 face in -x (compression, negative sign vs.
    # T4's tension test).
    L += ["*Amplitude, name=RAMP, definition=SMOOTH STEP",
          f"0., 0., {T:.6g}, 1."]
    L += ["*Step, name=S1",
          "*Dynamic, Explicit",
          f", {T:.6g}",
          # Full back face (x=0: nodes 1,4,5,8) pinned in x, so the
          # driven front face (x=1) produces a clean uniaxial
          # compression rather than the partial/skewed constraint set
          # verification/make_t4.py uses for its tension smoke test --
          # that pattern was found (on real Abaqus, this branch) to let
          # the element deform non-uniformly enough that engineering
          # strain plateaus just under a 0.3 threshold even once the
          # driven face has moved -0.6.
          "*Boundary",
          "FIXED, 1, 3",
          "CELL-1.4, 1, 1",
          "CELL-1.4, 3, 3",
          "CELL-1.5, 1, 1",
          "CELL-1.5, 2, 2",
          "CELL-1.8, 1, 1",
          "*Boundary, amplitude=RAMP",
          f"DRIVEN, 1, 1, {-COMPRESS_FRAC:.6g}",
          "*Output, history, frequency=1000000",
          "*Node Output, nset=ALLN",
          "RF1, RF2, RF3, U1, U2, U3",
          "*Output, field, number interval=20",
          "*Node Output",
          "U, RF",
          # No field/.dat request for the UEL's SVARS (the failure flag):
          # *Element Output rejects SVARS as an identifier for a *User
          # Element on this Abaqus/Explicit version, and *El Print is a
          # Standard-only keyword (Explicit rejects it outright) --
          # confirmed on real Abaqus here, both findings now in the
          # verification report. The subroutine's own WRITE(*,*) message
          # and the RF/energy history below are the evidence channel.
          "*Output, history, time interval=2e-05",
          "*Energy Output",
          "ALLIE, ALLKE, ALLWK, ALLVD, ALLAE, ETOTAL",
          "*End Step"]
    return "\n".join(L) + "\n"


def main():
    decks = {
        "t6_compress_nofail": 1.0,
        "t6_compress_trip": 0.3,
    }
    names = []
    user_src = (ROOT / "uel" / "VUEL_failure.for").read_text()
    for name, eps_fail in decks.items():
        (OUT / f"{name}.inp").write_text(build_inp(eps_fail), newline='')
        (OUT / f"{name}_user.for").write_text(user_src, newline='')
        names.append(name)
    (OUT / "decks_t6.txt").write_text("\n".join(names) + "\n", newline='')
    print(f"wrote {len(names)} decks to {OUT}")


if __name__ == "__main__":
    main()
