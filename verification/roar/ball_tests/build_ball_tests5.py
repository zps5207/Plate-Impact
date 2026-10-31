"""Build d5_rigid_100us from the d3_elastic_100us deck: the ball is an element-based rigid body that keeps the steel
density (mass and inertia come from the element densities), so it cannot deform or be deleted.

The reference node sits on the impact axis at the ball centre, translating along z only (the quarter-model symmetry
planes are enforced on it instead of on the ball nodes). Initial velocity moves from the ball nodes to the reference node.

Usage: python verification/roar/ball_tests/build_ball_tests5.py [out_dir]
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3] / "Meshing" / "vals-plywise-balltests3"
SRC = ROOT / "d3_elastic_100us" / "d3_elastic_100us.inp"
NAME = "d5_rigid_100us"
out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / NAME

text = SRC.read_bytes().decode()

BALL_SEC = '*Solid Section, elset=_PickedSet2, material="Mild Steel", controls=EMBMESH_DELETE_ALL\n'
assert text.count(BALL_SEC) == 1
text = text.replace(BALL_SEC, '*Solid Section, elset=_PickedSet2, material="Mild Steel"\n')

# symmetry BCs act on the reference node, so drop the ball nodes from the X / Y symmetry node sets
for nset in ("X", "Y"):
    pat = re.compile(r"\*Nset, nset=%s, instance=Ball-1[^\n]*\n(?:[^*][^\n]*\n)*" % nset)
    assert len(pat.findall(text)) == 1, nset
    text = pat.sub("", text)

ASSEMBLY_END = "*End Assembly\n"
assert text.count(ASSEMBLY_END) == 1
text = text.replace(ASSEMBLY_END,
                    "** rigid ball reference point, on the impact axis at the ball centre\n"
                    "*Node, nset=BALL_RP\n1, 0., 0., 0.011\n"
                    "** rigid ball: mass and inertia from the steel density of its elements\n"
                    "*Rigid Body, ref node=BALL_RP, elset=ball\n" + ASSEMBLY_END)

VEL = "*Initial Conditions, type=VELOCITY\n_PickedSet13, 3, -1000.\n"
assert text.count(VEL) == 1
text = text.replace(VEL, "*Boundary\nBALL_RP, 1, 2\nBALL_RP, 4, 6\n"
                    "*Initial Conditions, type=VELOCITY\nBALL_RP, 3, -1000.\n")

END = "*Output, history, variable=PRESELECT, time interval=7e-08\n*End Step"
assert text.count(END) == 1
text = text.replace(END, "*Output, history, variable=PRESELECT, time interval=7e-08\n"
                    "*Node Output, nset=BALL_RP\nU3, V3, A3\n*End Step")

out.mkdir(parents=True, exist_ok=True)
(out / (NAME + ".inp")).write_bytes(text.encode())
print("wrote", out / (NAME + ".inp"))
