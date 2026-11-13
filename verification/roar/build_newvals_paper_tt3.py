r"""NewVals.inp -> two plywise decks (native C3D8R / VUEL with per-element volume correction), 3 hex layers per ply.

Material cards are overwritten with Table 2 of "Valerie's Paper.pdf" (matrix: E 700 MPa, nu 0.45, rho 980, yield 70 MPa,
fracture strain 0.1 @ 0.01/s, Gf 1460 J/m^2; fiber: E 135 GPa, nu 0.45, rho 981, yield 3.5/4.3/4.5 GPa @ 0.01/1/1000 /s,
fracture strain 0.0391/0.0251/0.01167, Gf 1 J/m^2) plus the Table 1 cohesive interface.

Ball: NewVals.inp geometry (quarter, C3D8R + C3D6) made an element-based RIGID body at 1028 m/s (as the paper); the steel
density is scaled so the rigid quarter has the mass of a true 3/8 in steel sphere (see ball_density()).
  native  Matrix as plain C3D8R, embedded fibers, no volume correction
  vuel    VU1 + ghost host, ductile-damage matrix; per-host fiber fraction from the true fiber/hex intersection volume
          over EVERY host element of the ply (a fiber thicker than a hex layer is shared between layers), capped at 1
          (plywise_vuel.convert_plywise_hosts, precise=True)
Usage: python verification/roar/build_newvals_paper_tt3.py [out_dir]  (default Meshing/newvals-paper-tt3)
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "Meshing" / "NewVals.inp"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "Meshing" / "newvals-paper-tt3"
sys.argv = sys.argv[:1]  # build_vals_ballfix reads argv[1] at import
sys.path.insert(0, str(Path(__file__).resolve().parent))
PLIES, FIBER_D = 20, 0.632e-3

COHESIVE = """** cohesive interface, paper Table 1 (Hazzard 2018): Mode I / II strength 1.2 / 1.8 MPa, stiffness 60 / 36 N/mm^3, Gc 0.544 / 1.088 N/mm
*Surface Interaction, name=Cohesion
*Cohesive Behavior
 6e+10, 3.6e+10, 3.6e+10
*Damage Initiation, criterion=MAXS
 1.2e+06, 1.8e+06, 1.8e+06
*Damage Evolution, type=ENERGY, mixed mode behavior=POWER LAW, power=1
 544, 1088, 1088
"""

MATRIX = """*Material, name=Matrix
** paper Table 2: E 700 MPa, nu 0.45, rho 980, yield 70 MPa, fracture strain 0.1 @ 0.01/s, Gf 1460 J/m^2
*Damage Initiation, criterion=DUCTILE
 0.1, 0.333333, 0.01
*Damage Evolution, type=ENERGY
1460.,
*Density
980.,
*Elastic
 7e+08, 0.45
*Plastic, extrapolation=LINEAR
 7e+07,0.
"""

FIBER = """*Material, name=Fiber
** paper Table 2: E 135 GPa, nu 0.45, rho 981, rate-dependent yield and fracture strain, Gf 1 J/m^2
*Damage Initiation, criterion=DUCTILE
  0.0391, 0.333333,     0.01
  0.0251, 0.333333,       1.
 0.01167, 0.333333,    1000.
*Damage Evolution, type=ENERGY
1.,
*Density
981.,
*Elastic
 1.35e+11, 0.45
** Abaqus needs the static (rate-less) curve first: the paper's 0.01 /s curve is used as the static one
*Plastic
 3.5e+09,0.
*Plastic, rate=1.
 4.3e+09,0.
*Plastic, rate=1000.
 4.5e+09,0.
"""

R_BALL, CENTRE_Z, SPEED = 0.0047625, 0.005762, 1028.0
NL = "\n"


def replace_block(text, name, new):
    start = text.index("*Material, name=%s" % name + NL)
    end = text.index("*Material, name=", start + 1)
    return text[:start] + new + text[end:]


def ball_density(path):
    """7850 x (true quarter-sphere volume / meshed volume of the NewVals ball: hexes 2x2x2 Gauss, wedges as 3 tets)."""
    import build_vals_ballfix as bvf
    nodes, hexes, wedges, cur, mode = {}, [], [], None, None
    for ln in path.read_text().replace("\r", "").split(NL):
        s = ln.strip()
        if s.startswith("*Part"):
            cur, mode = s.split("name=")[1].strip(), None
        elif s.startswith("*End Part"):
            cur = mode = None
        elif cur == "Ball" and s.startswith("*Node"):
            mode = "n"
        elif cur == "Ball" and s.startswith("*Element"):
            mode = re.search(r"type=(\w+)", s).group(1)
        elif s.startswith("*"):
            mode = None
        elif cur == "Ball" and mode == "n":
            v = s.split(",")
            nodes[int(v[0])] = [float(x) for x in v[1:4]]
        elif cur == "Ball" and mode in ("C3D8R", "C3D6"):
            (hexes if mode == "C3D8R" else wedges).append([int(x) for x in s.strip(",").split(",")][1:])
    ids = sorted(nodes)
    ix = {n: i for i, n in enumerate(ids)}
    pts = np.array([nodes[n] for n in ids])
    vh = bvf.gauss_volume(pts, np.array([[ix[n] for n in e] for e in hexes]))
    vw = 0.0
    for e in wedges:
        p = pts[[ix[n] for n in e]]
        for t in ((0, 1, 2, 3), (1, 2, 3, 4), (2, 3, 4, 5)):
            vw += abs(np.linalg.det(p[list(t[1:])] - p[t[0]])) / 6.0
    exact = np.pi * R_BALL ** 3 / 3.0
    return dict(hexes=len(hexes), wedges=len(wedges), volume_mesh=vh + vw, volume_exact=exact,
                max_radius=float(np.linalg.norm(pts, axis=1).max()), density=7850.0 * exact / (vh + vw))


def main():
    import build_vals_ballfix as bvf
    OUT.mkdir(parents=True, exist_ok=True)
    text = SRC.read_text().replace("\r\n", NL)
    text = replace_block(text, "Fiber", FIBER)
    text = replace_block(text, "Matrix", MATRIX)
    marker = "*Surface Behavior, pressure-overclosure=HARD" + NL
    assert text.count(marker) == 1
    text = text.replace(marker, marker + "** " + NL + COHESIVE, 1)
    assert text.count("_PickedSet13, 3, -1000.") == 1
    text = text.replace("_PickedSet13, 3, -1000.", "_PickedSet13, 3, -%d." % SPEED, 1)
    src = OUT / "NewVals_paper.inp"
    src.write_text(text)
    info = ball_density(src)
    print("ball:", info)
    bvf.CENTRE_Z, bvf.SPEED = CENTRE_Z, SPEED
    log = {"ball": info, "centre_z_m": CENTRE_Z, "speed": SPEED}
    for kind, extra in (("native", ["--host-mode", "native", "--preview"]),
                        ("vuel", ["--host-mode", "vuel-ghost", "--matrix-model", "ductile-damage",
                                  "--vuel-eps-fail", "0.1"])):
        out = OUT / kind
        out.mkdir(parents=True, exist_ok=True)
        cmd = [sys.executable, "-m", "embmesh.cli", "plywise", str(src), "--instance", "Plate-1",
               "--collapse-layers", "--plies", str(PLIES), "--layup", ",".join(["0", "90"] * (PLIES // 2)),
               "--fiber-diameter", str(FIBER_D), "--fiber-gap", "0", "--cohesion", "Cohesion",
               "--plate-node-contact", "--fiber-node-contact", "--ball-instance", "Ball-1",
               "--ball-interaction", "General", "--through-thickness", "3",
               "--output", str(out / "output.inp"), *extra]
        with (out / "console.json").open("w") as f:
            subprocess.run(cmd, cwd=ROOT, check=True, stdout=f)
        deck = (out / "output.inp").read_text().replace("\r\n", NL)
        final = out / ("nv_" + kind + ".inp")
        final.write_text(bvf.rigid_ball(deck, info["density"]))
        log[kind] = str(final.relative_to(ROOT))
        print("wrote", final)
    (OUT / "build_log.json").write_text(json.dumps(log, indent=2))


if __name__ == "__main__":
    main()
