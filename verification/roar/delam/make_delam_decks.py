"""Two-ply cohesive-interface calibration decks (SI: m, kg, s, Pa).

Same cohesive card as verification/roar/build_vals_plywise.py (Hazzard et al. 2018 numbers).
Two 4x4x1 C3D8R plies (1.25 mm lateral, 1.27 mm thick) joined by surface-based cohesive contact.
  delam_modeI.inp   top ply pulled away in z      (expect peak force ~ T * A = 1.2 MPa * 25 mm2 = 30 N)
  delam_modeII.inp  top ply pulled in x           (expect peak force ~ S * A = 1.8 MPa * 25 mm2 = 45 N)
Plies are linear elastic so the interface is the only thing that can fail.
"""
from pathlib import Path

OUT = Path(__file__).resolve().parent
N, DX, T = 4, 1.25e-3, 1.27e-3
AREA = (N * DX) ** 2

COHESIVE = """*Surface Interaction, name=Cohesion
*Cohesive Behavior
 6e+10, 3.6e+10, 3.6e+10
*Damage Initiation, criterion=MAXS
 1.2e+06, 1.8e+06, 1.8e+06
*Damage Evolution, type=ENERGY, mixed mode behavior=POWER LAW, power=1
 544, 1088, 1088
"""


def mesh(base, z0):
    nodes, elems, ids = [], [], {}
    nid = base
    for k in range(2):
        for j in range(N + 1):
            for i in range(N + 1):
                ids[(i, j, k)] = nid
                nodes.append(f"{nid}, {i*DX:.6e}, {j*DX:.6e}, {z0 + k*T:.6e}")
                nid += 1
    eid = base
    for j in range(N):
        for i in range(N):
            c = [(i, j, 0), (i+1, j, 0), (i+1, j+1, 0), (i, j+1, 0),
                 (i, j, 1), (i+1, j, 1), (i+1, j+1, 1), (i, j+1, 1)]
            elems.append(f"{eid}, " + ", ".join(str(ids[p]) for p in c))
            eid += 1
    bottom = [ids[(i, j, 0)] for j in range(N + 1) for i in range(N + 1)]
    top = [ids[(i, j, 1)] for j in range(N + 1) for i in range(N + 1)]
    return nodes, elems, bottom, top, list(range(base, eid))


def nset(name, ids):
    lines = [f"*Nset, nset={name}"]
    for s in range(0, len(ids), 12):
        lines.append(", ".join(map(str, ids[s:s+12])))
    return lines


def elset(name, ids):
    lines = [f"*Elset, elset={name}"]
    for s in range(0, len(ids), 12):
        lines.append(", ".join(map(str, ids[s:s+12])))
    return lines


def deck(mode, scale=1):
    n1, e1, b1, t1, el1 = mesh(1, 0.0)
    n2, e2, b2, t2, el2 = mesh(1001, T)
    L = ["*Heading", f"** two-ply cohesive calibration, mode {mode}", "*Node", *n1, *n2,
         "*Element, type=C3D8R", *e1, *e2,
         *elset("PLY1", el1), *elset("PLY2", el2),
         *nset("P1_BOT", b1), *nset("P2_TOP", t2),
         "*Surface, type=ELEMENT, name=PLY1_TOP", "PLY1, S2",
         "*Surface, type=ELEMENT, name=PLY2_BOTTOM", "PLY2, S1",
         "*Solid Section, elset=PLY1, material=Ply", "*Solid Section, elset=PLY2, material=Ply",
         "*Material, name=Ply", "*Density", " 980.,", "*Elastic", " 7e+08, 0.45",
         COHESIVE.rstrip(),
         "*Surface Interaction, name=General", "*Surface Behavior, pressure-overclosure=HARD",
         "*Amplitude, name=RAMP, definition=SMOOTH STEP", "0., 0., %g, 1." % (1.5e-4 * scale),
         "*Boundary", "P1_BOT, 1, 3, 0."]
    if mode == "I":
        L += ["*Boundary", "P2_TOP, 1, 2, 0."]
        move, dof, dist = "P2_TOP", 3, 1.5e-3
    else:
        L += ["*Boundary", "P2_TOP, 2, 3, 0."]
        move, dof, dist = "P2_TOP", 1, 1.5e-3
    L += ["*Step, name=Pull, nlgeom=YES", "*Dynamic, Explicit", ", %g" % (1.5e-4 * scale), "*Bulk Viscosity", "0.06, 1.2",
          "*Contact", "*Contact Inclusions", "PLY1_TOP, PLY2_BOTTOM",
          "*Contact Property Assignment", " , , General", "PLY1_TOP, PLY2_BOTTOM, Cohesion",
          "*Boundary, type=DISPLACEMENT, amplitude=RAMP", f"{move}, {dof}, {dof}, {dist}",
          "*Output, field, time interval=%g" % (2e-6 * scale), "*Node Output", "U, V, RF",
          "*Contact Output", "CSDMG, CSMAXSCRT, CSTRESS, CDISP",
          "*Output, history, time interval=%g" % (1e-6 * scale),
          "*Node Output, nset=P2_TOP", "RF1, RF3, U1, U3",
          "*Energy Output", "ALLKE, ALLIE, ALLDMD, ALLFD, ETOTAL",
          "*End Step"]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    for m, f in (("I", "delam_modeI.inp"), ("II", "delam_modeII.inp")):
        (OUT / f).write_text(deck(m), newline="")
        print("wrote", f)
        g = f.replace(".inp", "_x100.inp")
        (OUT / g).write_text(deck(m, 100), newline="")
        print("wrote", g)
    print("expected peak force: mode I %.1f N, mode II %.1f N" % (1.2e6 * AREA, 1.8e6 * AREA))
