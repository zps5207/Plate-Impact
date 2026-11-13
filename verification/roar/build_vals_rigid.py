"""Build the Valerie plywise decks (vp3: native embedded C3D8R and VUEL Stage 8) with a rigid, non-deformable ball.

Source decks are Meshing/vals-plywise/{native,vuel}/output.inp, i.e. Meshing/Vals.inp split into 20 plies by
build_vals_plywise.py (static fiber curve fix, Hazzard-style cohesive, node-based ball contact, no element deletion).
The ONLY physics change is the ball: it becomes an element-based rigid body that keeps the steel density (mass comes
from the element densities), driven by a reference node on the impact axis, same -1000 m/s. Same mesh, same materials,
same contact, same step (7e-5 s) in both decks; they differ only in the matrix element (native C3D8R vs VU1).
Output-only additions (no effect on the solution): ball RP history (U3, V3, A3) and *Contact Output for CSDMG so the
cohesive delamination can be extracted.

Usage: python verification/roar/build_vals_rigid.py [out_dir]   (default Meshing/vals-plywise-rigid)
Writes <out_dir>/{native,vuel}/vr_{native,vuel}.inp and a build log (rigid_build_log.json).
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "Meshing" / "vals-plywise"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "Meshing" / "vals-plywise-rigid"
CRLF = b"\r\n"


def once(text, old, new, label):
    assert text.count(old) == 1, "%s: expected 1 match, found %d" % (label, text.count(old))
    return text.replace(old, new)


def rigid_ball(text):
    for nset in ("X", "Y"):  # symmetry acts on the reference node instead of the ball nodes
        pat = re.compile(r"\*Nset, nset=%s, instance=Ball-1[^\n]*\n(?:[^*][^\n]*\n)*" % nset)
        assert len(pat.findall(text)) == 1, nset
        text = pat.sub("", text)
    text = once(text, "*End Assembly\n",
                "** rigid ball reference point, on the impact axis at the ball centre\n"
                "*Node, nset=BALL_RP\n1, 0., 0., 0.011\n"
                "** rigid ball: mass and inertia from the steel density of its elements\n"
                "*Rigid Body, ref node=BALL_RP, elset=ball\n*End Assembly\n", "rigid body")
    text = once(text, "*Initial Conditions, type=VELOCITY\n_PickedSet13, 3, -1000.\n",
                "*Boundary\nBALL_RP, 1, 2\nBALL_RP, 4, 6\n"
                "*Initial Conditions, type=VELOCITY\nBALL_RP, 3, -1000.\n", "velocity")
    text = once(text, "*Output, history, variable=PRESELECT, time interval=7e-08\n",
                "*Output, history, variable=PRESELECT, time interval=7e-08\n*Node Output, nset=BALL_RP\nU3, V3, A3\n",
                "ball history")
    text = once(text, "*Output, field, variable=PRESELECT, number interval=1000\n",
                "*Output, field, variable=PRESELECT, number interval=1000\n"
                "*Contact Output\nCSDMG, CSMAXSCRT, CSTRESS, CDISP\n", "contact output")
    return text


log = {}
for kind in ("native", "vuel"):
    src = SRC / kind / "output.inp"
    raw = src.read_bytes()
    crlf = CRLF in raw[:2000]
    text = rigid_ball(raw.decode().replace("\r\n", "\n"))  # decks use CRLF; edit on LF, restore on write
    if crlf:
        text = text.replace("\n", "\r\n")
    name = "vr_" + kind
    dst = OUT / kind / (name + ".inp")
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(text.encode())
    log[kind] = {"source": str(src.relative_to(ROOT)), "source_sha256": hashlib.sha256(raw).hexdigest(),
                 "deck": str(dst.relative_to(ROOT)), "deck_sha256": hashlib.sha256(text.encode()).hexdigest()}
    print("wrote", dst)
(OUT / "rigid_build_log.json").write_text(json.dumps(log, indent=2))
