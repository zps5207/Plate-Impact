"""bt3 decks: the 20-ply Vals deck at 1000 m/s, 12 us, built on the bt2 c2 reference (T3D2 fibers, JC D4 = +0.002, matrix max degradation 0.8).

  d1_fullfix   the combined fixes from the T-052 coupon deck 10: uniform O-grid ball, enhanced hourglass + distortion control on the
               ball section, fiber node-contact THICKNESS 0.05 mm
  d2_elastic   the c2 reference with only the ball steel changed to a purely elastic card (E = 203 GPa, no plasticity, no damage)
               to see how the plate deforms under an unbreakable ball

Usage: python verification/roar/ball_tests/build_ball_tests3.py [out_dir]
"""
import sys
from pathlib import Path

out = sys.argv[1] if len(sys.argv) > 1 else None
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.argv = [sys.argv[0]] + ([out] if out else [str(Path(__file__).resolve().parents[3] / "Meshing" / "vals-plywise-balltests3")])
import build_ball_tests as bt

CTRL = "*Section Controls, name=EMBMESH_DELETE_ALL, element deletion=YES"
MD = "0.8"
THIN = "0.00005"
THICK = "EMBMESH_FIBER_NODES, 0.000617973861320424"
BALL_SEC = '*Solid Section, elset=_PickedSet2, material="Mild Steel", controls=EMBMESH_DELETE_ALL'
ELASTIC = """*Material, name="Mild Steel"
*Density
7850.,
*Elastic
 2.03e+11, 0.33"""


def with_max_degradation(lines):
    text = "\n".join(lines)
    assert text.count(CTRL + "\n") == 1
    return text.replace(CTRL + "\n", CTRL + ", max degradation=" + MD + "\n").split("\n")


def with_ball_controls(lines):
    """Own section controls for the ball: enhanced hourglass, distortion control (length ratio 0.1), element deletion, max degradation."""
    text = "\n".join(lines)
    ball_ctrl = ("*Section Controls, name=EMBMESH_BALL_CTRL, element deletion=YES, max degradation=" + MD
                 + ", hourglass=ENHANCED, distortion control=YES, length ratio=0.1")
    assert text.count(BALL_SEC) == 1
    text = text.replace(BALL_SEC, BALL_SEC.replace("EMBMESH_DELETE_ALL", "EMBMESH_BALL_CTRL"))
    marker = CTRL + ", max degradation=" + MD + "\n"
    assert text.count(marker) == 1
    return text.replace(marker, marker + ball_ctrl + "\n").split("\n")


def with_thin_fiber_contact(lines):
    text = "\n".join(lines)
    assert text.count(THICK + "\n") == 1
    return text.replace(THICK + "\n", "EMBMESH_FIBER_NODES, " + THIN + "\n").split("\n")


def main():
    lines = bt.SRC.read_text().split("\n")
    vol = bt.old_ball_volume(lines)
    pts, hexes, info = bt.new_ball(vol)
    print({k: (round(v, 6) if isinstance(v, float) else v) for k, v in info.items()})
    c2 = with_max_degradation(bt.with_steel(bt.with_step(lines), d4="0.002"))
    decks = {"d1_fullfix": with_thin_fiber_contact(with_ball_controls(bt.with_new_ball(c2, pts, hexes))),
             "d2_elastic": bt.with_steel(c2, card=ELASTIC)}
    bt.OUT.mkdir(parents=True, exist_ok=True)
    for name, ls in decks.items():
        d = bt.OUT / name
        d.mkdir(exist_ok=True)
        (d / (name + ".inp")).write_text("\n".join(ls), newline="\n")
        print(name, len(ls), "lines")


if __name__ == "__main__":
    main()

# d3_elastic_100us was made from d2_elastic by two text edits (kept here for the record):
#   "*Dynamic, Explicit\n, 1.2e-05"  ->  ", 1e-04"   (100 us)
#   "*Output, field, number interval=100" -> "number interval=200"  (0.5 us frame spacing)
