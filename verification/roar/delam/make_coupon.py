"""Small impact coupon for reproducing interply delamination (SI: m, kg, s, Pa).

NPLY native-host plies (C3D8R, 1.25 mm lateral, 1.27 mm thick) with embedded T3D2 fibers, alternating
x / y by ply, joined by surface-based cohesive contact; a steel block impactor hits the top ply.
Material cards are the vp4 ones (make_test_decks.py). Cohesive variants:
  base   : deck values (K 60 N/mm3, shear strength 1.8 MPa)
  fixed  : Hazzard K for t_SL = 1.27 mm (47.2 N/mm3) and ballistic shear strength 2.6 MPa
Usage: python make_coupon.py
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "agents/drafter/outbox/T-046/tests"))
import make_test_decks as m  # noqa: E402

NPLY, NX, DX, T = 6, 16, 1.25e-3, 1.27e-3
V_IMPACT = -500.0
T_END = 4.0e-5


def chunks(ids, n=12):
    return [", ".join(map(str, ids[s:s + n])) for s in range(0, len(ids), n)]


def cohesive(variant):
    k, s2 = (60.0, 1.8) if variant == "base" else (60.0 / 1.27, 2.6)
    return f"""*Surface Interaction, name=Cohesion
*Cohesive Behavior
 {k*1e9:.6g}, {0.6*k*1e9:.6g}, {0.6*k*1e9:.6g}
*Damage Initiation, criterion=MAXS
 1.2e+06, {s2*1e6:.6g}, {s2*1e6:.6g}
*Damage Evolution, type=ENERGY, mixed mode behavior=POWER LAW, power=1
 544, 1088, 1088
"""


def deck(variant, gap=1e-6, thick=(0.0006349999925, 0.000617973861320424), t_end=T_END, contact="nodes", host_ctrl="delete"):
    nodes, elems, fnodes, felems = [], [], [], []
    ply_el = {p: [] for p in range(NPLY)}
    ply_bot_faces, edge = {}, set()
    nid = eid = 1
    ids = {}
    for p in range(NPLY):
        for k in range(2):
            for j in range(NX + 1):
                for i in range(NX + 1):
                    ids[(p, i, j, k)] = nid
                    nodes.append(f"{nid}, {i*DX:.6e}, {j*DX:.6e}, {(p+k)*T:.6e}")
                    if i in (0, NX) or j in (0, NX):
                        edge.add(nid)
                    nid += 1
        for j in range(NX):
            for i in range(NX):
                c = [(i, j, 0), (i+1, j, 0), (i+1, j+1, 0), (i, j+1, 0),
                     (i, j, 1), (i+1, j, 1), (i+1, j+1, 1), (i, j+1, 1)]
                elems.append(f"{eid}, " + ", ".join(str(ids[(p,) + q]) for q in c))
                ply_el[p].append(eid)
                eid += 1
    # fibers: one per element row, at mid-ply, along x (even plies) or y (odd plies)
    fn, fe = 100001, 100001
    for p in range(NPLY):
        zc = (p + 0.5) * T
        for r in range(NX):
            yc = (r + 0.5) * DX
            row = []
            for q in range(NX + 1):
                x, y = (q * DX, yc) if p % 2 == 0 else (yc, q * DX)
                fnodes.append(f"{fn}, {x:.6e}, {y:.6e}, {zc:.6e}")
                row.append(fn)
                fn += 1
            for a, b in zip(row[:-1], row[1:]):
                felems.append(f"{fe}, {a}, {b}")
                fe += 1
    # impactor block: 4x4x2 elements, 5 mm square, 2.5 mm tall, just above the plate
    zt = NPLY * T
    bn, be, bid = [], [], {}
    n0 = 200001
    cx = NX * DX / 2 - 2.5e-3
    for k in range(3):
        for j in range(5):
            for i in range(5):
                bid[(i, j, k)] = n0
                bn.append(f"{n0}, {cx + i*DX:.6e}, {cx + j*DX:.6e}, {zt + gap + k*1.25e-3:.6e}")
                n0 += 1
    e0 = 200001
    for k in range(2):
        for j in range(4):
            for i in range(4):
                c = [(i, j, k), (i+1, j, k), (i+1, j+1, k), (i, j+1, k),
                     (i, j, k+1), (i+1, j, k+1), (i+1, j+1, k+1), (i, j+1, k+1)]
                be.append(f"{e0}, " + ", ".join(str(bid[q]) for q in c))
                e0 += 1
    L = ["*Heading", f"** delamination coupon, cohesive variant {variant}",
         "*Node", *nodes, *fnodes, *bn,
         "*Element, type=C3D8R", *elems,
         "*Element, type=T3D2, elset=FIBERS", *felems,
         "*Element, type=C3D8R, elset=BALL", *be,
         "*Elset, elset=HOST"] + chunks([e for p in ply_el for e in ply_el[p]])
    for p in range(NPLY):
        L += [f"*Elset, elset=PLY{p}"] + chunks(ply_el[p])
        L += [f"*Surface, type=ELEMENT, name=PLY{p}_TOP", f"PLY{p}, S2",
              f"*Surface, type=ELEMENT, name=PLY{p}_BOT", f"PLY{p}, S1"]
    L += ["*Surface, type=ELEMENT, name=BALL_SURF", "BALL, S1", "*Surface, type=ELEMENT, name=PLATE_TOP", f"PLY{NPLY-1}, S2",
          "*Nset, nset=EDGE"] + chunks(sorted(edge))
    hostn = sorted(set(ids.values()))
    fibn = list(range(100001, fn))
    L += ["*Nset, nset=HOSTN"] + chunks(hostn) + ["*Nset, nset=FIBN"] + chunks(fibn)
    L += ["*Surface, type=NODE, name=PLATE_NODES", "HOSTN", "*Surface, type=ELEMENT, name=HOST_SURF", "HOST", "*Surface, type=NODE, name=FIBER_NODES", "FIBN"]
    L += ["*Nset, nset=BALLN, elset=BALL",
          f"*Solid Section, elset=HOST, material=Matrix, controls={'EMBMESH_DELETE_ALL' if host_ctrl == 'delete' else 'EMBMESH_HOST_KEEP'}",
          "*Section Controls, name=EMBMESH_HOST_KEEP, element deletion=NO, max degradation=0.99",
          "*Solid Section, elset=FIBERS, material=Fiber, controls=EMBMESH_DELETE_ALL", f"{m.FIBER_AREA}",
          "*Solid Section, elset=BALL, material=Steel",
          "*Material, name=Steel", "*Density", " 7850.,", "*Elastic", " 2e+11, 0.3",
          "*Embedded Element, host elset=HOST", "FIBERS",
          m.fiber_material_block().rstrip(), m.matrix_material_block().rstrip(),
          cohesive(variant).rstrip(),
          "*Surface Interaction, name=General", "*Friction", " 0.01,", "*Surface Behavior, pressure-overclosure=HARD",
          "*Boundary", "EDGE, 1, 3, 0.",
          "*Initial Conditions, type=VELOCITY", f"BALLN, 3, {V_IMPACT}",
          "*Step, name=Impact, nlgeom=YES", f"*Dynamic, Explicit", f", {t_end:g}", "*Bulk Viscosity", "0.06, 1.2",
          "*Contact", "*Contact Inclusions"]
    pairs = [(f"PLY{p}_TOP", f"PLY{p+1}_BOT") for p in range(NPLY - 1)]
    L += [f"{a}, {b}" for a, b in pairs] + [("PLATE_NODES, BALL_SURF" if contact == "nodes" else "HOST_SURF, BALL_SURF"), "FIBER_NODES, BALL_SURF",
                                            "*Contact Property Assignment", " , , General"]
    L += [f"{a}, {b}, Cohesion" for a, b in pairs]
    # node-based ball contact on every host node and fiber node, contact thickness as in the vp4 deck
    if contact == "nodes":
        L += ["*Surface Property Assignment, property=THICKNESS", f"PLATE_NODES, {thick[0]:.12g}"]
    L += ["*Surface Property Assignment, property=THICKNESS", f"FIBER_NODES, {thick[1]:.12g}"]
    L += ["*Output, field, time interval=1e-6", "*Node Output", "U, V", "*Element Output, elset=HOST", "STATUS, S, PEEQ",
          "*Element Output, elset=FIBERS", "STATUS, S",
          "*Contact Output", "CSDMG, CSMAXSCRT, CSTRESS, CDISP",
          "*Output, history, time interval=5e-7", "*Energy Output", "ALLKE, ALLIE, ALLSE, ALLPD, ALLDMD, ALLFD, ALLVD, ALLAE, ALLWK, ETOTAL", "*End Step"]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    # energy-diagnosis variants on the fixed cohesive card (full energy set in all)
    for name, kw in (("e0", {}),                                        # reference
                     ("gap", {"gap": 1.0e-3, "t_end": 4.2e-5}),         # ball starts 1 mm above: no initial overlap
                     ("thin", {"thick": (1.0e-4, 1.0e-4)}),
                     ("erode", {"contact": "erode"}),                    # host: eroding element-based surface, no floating host nodes
                     ("keep", {"host_ctrl": "keep"})):                   # host degrades to 1% stiffness, never deleted             # node contact thickness 0.1 mm
        (HERE / f"coupon_x{name}.inp").write_text(deck("fixed", **kw), newline="")
        print("wrote", f"coupon_x{name}.inp")
    for v in ("base", "fixed"):
        (HERE / f"coupon_n{v}.inp").write_text(deck(v), newline="")
        print("wrote", f"coupon_n{v}.inp")
