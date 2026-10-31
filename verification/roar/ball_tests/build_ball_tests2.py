"""bt2 decks (all vp5 ball, 12 us): beam fibers / truss fibers with the JC damage D4 = +0.002, and a lower max degradation.

  c1_beam_d4        beam fibers (B31, element fiber surface) + D4 = +0.002, max degradation 1 (as vp5)
  c2_truss_d4_md80  T3D2 fibers + D4 = +0.002, *Section Controls max degradation = 0.8
  c3_beam_d4_md80   beam fibers + D4 = +0.002, max degradation = 0.8
(b4_d4fix from bt1 is the truss + D4 + max degradation 1 reference.)
Usage: python verification/roar/ball_tests/build_ball_tests2.py [out_dir] [impact_speed_m_s, default 1000; deck names get a _v<speed> suffix when not 1000]
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
out = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "Meshing" / "vals-plywise-balltests2")
speed = sys.argv[2] if len(sys.argv) > 2 else "1000"
sys.argv = [sys.argv[0], out]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_ball_tests as bt

MD = "0.8"
CTRL = "*Section Controls, name=EMBMESH_DELETE_ALL, element deletion=YES"


def with_max_degradation(lines, md):
    text = "\n".join(lines)
    assert text.count(CTRL + "\n") == 1
    return text.replace(CTRL + "\n", CTRL + ", max degradation=" + md + "\n").split("\n")


lines = bt.SRC.read_text().split("\n")
if speed != "1000":
    old = "_PickedSet13, 3, -1000."
    text = "\n".join(lines)
    assert text.count(old) == 1
    lines = text.replace(old, "_PickedSet13, 3, -%s." % speed).split("\n")
base = bt.with_step(lines)
d4 = bt.with_steel(base, d4="0.002")
beam = bt.with_beam_fibers(d4)
decks = {"c1_beam_d4": beam,
         "c2_truss_d4_md80": with_max_degradation(d4, MD),
         "c3_beam_d4_md80": with_max_degradation(beam, MD)}
bt.OUT.mkdir(parents=True, exist_ok=True)
sfx = "" if speed == "1000" else "_v" + speed
for name, ls in decks.items():
    name += sfx
    d = bt.OUT / name
    d.mkdir(exist_ok=True)
    (d / (name + ".inp")).write_text("\n".join(ls), newline="\n")
    print(name, len(ls), "lines")
