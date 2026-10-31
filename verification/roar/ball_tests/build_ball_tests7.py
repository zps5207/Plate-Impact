"""Build d7_brittle_fiber_100us from d6_rigid_matched_100us: fibers are elastic-brittle.

Changes vs d6: fiber ductile damage initiates at 1e-4 equivalent plastic strain at every rate (i.e. right after the
rate-dependent yield of 3.5 / 4.3 / 4.5 GPa) and the damage evolution is abrupt (displacement 0, as in d5).
Everything else (rigid ball, matrix card, cohesive interface) is unchanged.

Usage: python verification/roar/ball_tests/build_ball_tests7.py [out_dir]
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3] / "Meshing" / "vals-plywise-balltests3"
SRC = ROOT / "d6_rigid_matched_100us" / "d6_rigid_matched_100us.inp"
NAME = "d7_brittle_fiber_100us"
out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / NAME

OLD = ("*Material, name=Fiber\n*Damage Initiation, criterion=DUCTILE\n  0.0391, 0.333333,     0.01\n"
       "  0.0251, 0.333333,       1.\n 0.01167, 0.333333,    1000.\n*Damage Evolution, type=ENERGY\n1.,\n")
NEW = ("*Material, name=Fiber\n*Damage Initiation, criterion=DUCTILE\n  1e-04, 0.333333,     0.01\n"
       "  1e-04, 0.333333,       1.\n  1e-04, 0.333333,    1000.\n*Damage Evolution, type=DISPLACEMENT\n0.,\n")
text = SRC.read_bytes().decode()
assert text.count(OLD) == 1
text = text.replace(OLD, NEW)
out.mkdir(parents=True, exist_ok=True)
(out / (NAME + ".inp")).write_bytes(text.encode())
print("wrote", out / (NAME + ".inp"))
