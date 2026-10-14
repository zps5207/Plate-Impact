"""Generate the T4 (1-element/4-fiber VUEL+VUMAT interaction) smoke-test deck
into verification/roar/t4/.

This does NOT go through embmesh's mesher/CLI: the host here is a *User
Element (uel/VUEL.for), and Abaqus's native `*Embedded Element` embedding
algorithm is documented for standard continuum/shell/etc. hosts, not for a
user element the mesher's writer never targets. Coupling is instead done
the direct way available for a single host element: the 4 fiber elements'
end nodes are literally 4 of the host hex's own 8 corner nodes, so load
transfers through ordinary shared-DOF equilibrium, no embedding scheme
needed. This is deliberately the simplest possible VUEL/VUMAT interaction
check, not a stand-in for the mesher's real multi-element embedding.

Independent of embmesh; own geometry, own units (SI: m, kg, s, Pa) chosen
to match the goal's E=100 GPa / G=50 GPa fiber values directly, distinct
from the mm/tonne/s/MPa convention used by verification/make_t3.py's
mesher-driven decks.

Abaqus links exactly one user-subroutine file per job. VUEL.for defines
SUBROUTINE VUEL (+ its own private helpers) and VUMAT_fibers_combined.for
defines SUBROUTINE VUMAT -- no name collision, so this script concatenates
them into one job-specific file rather than duplicating either source.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "verification" / "roar" / "t4"
OUT.mkdir(parents=True, exist_ok=True)

# ---- geometry: unit cube host hex, Abaqus C3D8 corner order ----
NODES = {
    1: (0.0, 0.0, 0.0), 2: (1.0, 0.0, 0.0), 3: (1.0, 1.0, 0.0), 4: (0.0, 1.0, 0.0),
    5: (0.0, 0.0, 1.0), 6: (1.0, 0.0, 1.0), 7: (1.0, 1.0, 1.0), 8: (0.0, 1.0, 1.0),
}

# Fiber diameter and derived section properties (SI units)
D_FIBER = 0.01  # m
AREA = 3.141592653589793 * D_FIBER ** 2 / 4.0
RADIUS = D_FIBER / 2.0
N1_A = (1.0, 0.0, 0.0)                        # perpendicular to (4->8), axis = +z
N1_B = (0.7071067811865476, 0.7071067811865476, 0.0)  # perpendicular to (2->8)

HOST_PROPS = dict(E=200.0e9, nu=0.3, rho=7800.0, beta_rayleigh=0.0, b1=0.06, b2=1.2)
FIBER_E = 100.0e9
FIBER_G = 50.0e9
FIBER_SFAIL = 2.0e9
FIBER_RHO = 1800.0

T = 1.0e-2  # step time, s -- see report for the (unverified) stable-increment estimate this assumes


def build_inp(host="vuel"):
    """host='vuel' (uel/VUEL.for hex) or 'c3d8' (native, elastic *Solid Section)
    -- the c3d8 variant isolates whether a fiber VUMAT runs on native T3D2/B31
    at all from whether it specifically works with the VUEL host, the same
    split that found BUG-016."""
    L = []
    tag = "VUEL host" if host == "vuel" else "native C3D8 host (isolates the VUEL question out)"
    L += ["*Heading", f"** T4: 1-element ({tag}) / 4-fiber (VUMAT truss+beam) interaction smoke test",
          "** units: SI (m, kg, s, Pa); see verification/make_t4.py for how this was generated",
          "*Preprint, echo=NO, model=YES, history=NO, contact=NO"]
    L += ["*Part, name=CELL", "*Node"]
    L += [f"{n}, {c[0]:.6g}, {c[1]:.6g}, {c[2]:.6g}" for n, c in NODES.items()]
    if host == "vuel":
        # Abaqus/Explicit user-element type keys must start with "VU" (Standard's
        # own convention, "U1", is rejected in Explicit -- see docs/BUGS.md BUG-018).
        L += ["*User Element, type=VU1, nodes=8, coordinates=3, properties=6, variables=48",
              "1, 2, 3",
              "*Element, type=VU1, elset=HOSTUEL",
              "1, " + ", ".join(str(n) for n in range(1, 9)),
              "*UEL Property, elset=HOSTUEL",
              f"{HOST_PROPS['E']:.6g}, {HOST_PROPS['nu']:.6g}, {HOST_PROPS['rho']:.6g}, "
              f"{HOST_PROPS['beta_rayleigh']:.6g}, {HOST_PROPS['b1']:.6g}, {HOST_PROPS['b2']:.6g}"]
    else:
        L += ["*Element, type=C3D8R, elset=HOSTUEL",
              "1, " + ", ".join(str(n) for n in range(1, 9)),
              "*Solid Section, elset=HOSTUEL, material=HOSTMAT",
              ","]
    # 2 truss fibers, sharing existing host corner nodes -- no new nodes.
    L += ["*Element, type=T3D2, elset=TRUSSFIBERS",
          "101, 1, 2",   # bottom edge, along the load direction
          "102, 1, 7",   # space diagonal
          f"*Solid Section, elset=TRUSSFIBERS, material=TRUSSFIBER",
          f"{AREA:.12g}"]
    # 2 beam fibers, each its own elset so each gets a valid (non-parallel) n1.
    # n1 on its OWN data line (2nd), not combined with radius on the 1st --
    # see docs/BUGS.md BUG-018: combining them on one line silently drops n1
    # to Abaqus's own automatic default instead of using the given value.
    L += ["*Element, type=B31, elset=BEAMFIBER_A",
          "201, 4, 8",   # vertical edge, axis = +z
          "*Beam Section, elset=BEAMFIBER_A, material=BEAMFIBER, section=CIRC",
          f"{RADIUS:.12g}",
          f"{N1_A[0]:.12g}, {N1_A[1]:.12g}, {N1_A[2]:.12g}",
          "*Element, type=B31, elset=BEAMFIBER_B",
          "202, 2, 8",   # face/space diagonal
          "*Beam Section, elset=BEAMFIBER_B, material=BEAMFIBER, section=CIRC",
          f"{RADIUS:.12g}",
          f"{N1_B[0]:.12g}, {N1_B[1]:.12g}, {N1_B[2]:.12g}"]
    L += ["*End Part"]
    L += ["*Assembly, name=Assembly", "*Instance, name=CELL-1, part=CELL", "*End Instance",
          "*Nset, nset=FIXED, instance=CELL-1", "1",
          "*Nset, nset=DRIVEN, instance=CELL-1", "2, 3, 6, 7",
          "*Nset, nset=ALLN, instance=CELL-1", "1, 2, 3, 4, 5, 6, 7, 8",
          "*End Assembly"]
    L += ["*Material, name=TRUSSFIBER", "*Density", f"{FIBER_RHO:.6g},",
          "*Depvar, delete=1", "1", "*User Material, constants=2",
          f"{FIBER_E:.6g}, {FIBER_SFAIL:.6g}"]
    L += ["*Material, name=BEAMFIBER", "*Density", f"{FIBER_RHO:.6g},",
          "*Depvar, delete=1", "1", "*User Material, constants=3",
          f"{FIBER_E:.6g}, {FIBER_G:.6g}, {FIBER_SFAIL:.6g}"]
    if host == "c3d8":
        L += ["*Material, name=HOSTMAT", "*Density", f"{HOST_PROPS['rho']:.6g},",
              "*Elastic", f"{HOST_PROPS['E']:.6g}, {HOST_PROPS['nu']:.6g}"]
    L += ["*Amplitude, name=RAMP, definition=SMOOTH STEP", f"0., 0., {T:.6g}, 1."]
    L += ["*Step, name=S1", "*Dynamic, Explicit", f", {T:.6g}"]
    # Minimal smoke-test BCs: node 1 fully fixed; a few single-DOF pins on
    # nodes 4/5/8 to keep the cube from drifting as a rigid body; the
    # x=1 face (DRIVEN) ramped in +x to put both truss fibers, and (via
    # cube shear) both beam fibers, into a nonzero, mixed strain state.
    # NOT tuned for a physically realistic BC set -- see the report for
    # what this smoke test does and does not check.
    L += ["*Boundary", "FIXED, 1, 3", "CELL-1.4, 2, 3", "CELL-1.5, 1, 3", "CELL-1.8, 2, 2",
          "*Boundary, amplitude=RAMP", "DRIVEN, 1, 1, 0.001"]
    L += ["*Output, history, frequency=1000000", "*Node Output, nset=ALLN", "RF1, RF2, RF3, U1, U2, U3"]
    L += ["*Output, field, number interval=5", "*Node Output", "U, RF",
          "*Element Output, directions=YES", "S, E",
          "*Output, history, time interval=%.6g" % (T / 50), "*Energy Output",
          "ALLIE, ALLKE, ALLWK, ALLVD, ALLAE, ETOTAL", "*End Step"]
    return "\n".join(L) + "\n"


def build_combined_user_file():
    vuel = (ROOT / "uel" / "VUEL.for").read_text()
    vumat = (ROOT / "vumat" / "VUMAT_fibers_combined.for").read_text()
    header = ("C     Job-specific concatenation of uel/VUEL.for (SUBROUTINE VUEL, host\n"
              "C     element) and vumat/VUMAT_fibers_combined.for (SUBROUTINE VUMAT, fiber\n"
              "C     materials) for the T4 smoke test, generated by verification/make_t4.py.\n"
              "C     Not a third source file to maintain by hand -- edit the two originals\n"
              "C     and regenerate this one.\n")
    return header + vuel + "\n" + vumat


def main():
    made = []

    inp_path = OUT / "vuel_fiber_smoke.inp"
    inp_path.write_text(build_inp(host="vuel"))
    user_path = OUT / "vuel_fiber_smoke_user.for"
    user_path.write_text(build_combined_user_file())
    made.append("vuel_fiber_smoke")
    print("wrote", inp_path); print("wrote", user_path)

    inp_path2 = OUT / "c3d8_fiber_smoke.inp"
    inp_path2.write_text(build_inp(host="c3d8"))
    user_path2 = OUT / "c3d8_fiber_smoke_user.for"
    user_path2.write_text((ROOT / "vumat" / "VUMAT_fibers_combined.for").read_text())
    made.append("c3d8_fiber_smoke")
    print("wrote", inp_path2); print("wrote", user_path2)

    (OUT / "decks_t4.txt").write_text("\n".join(made) + "\n")


if __name__ == "__main__":
    sys.exit(main())
