"""Build d6_rigid_matched_100us from d5_rigid_100us: material cards matched to the paper table (Table 2).

Changes vs d5: matrix fracture strain 0.1 at 0.01 /s (was 0.01); fiber damage evolution type=ENERGY with 1 J/m^2
(was displacement 0, abrupt). Everything else (rigid non-deformable ball with steel density) is unchanged.

Usage: python verification/roar/ball_tests/build_ball_tests6.py [out_dir]
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3] / "Meshing" / "vals-plywise-balltests3"
SRC = ROOT / "d5_rigid_100us" / "d5_rigid_100us.inp"
NAME = "d6_rigid_matched_100us"
out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / NAME

OLD_FIBER = "*Damage Evolution, type=DISPLACEMENT\n0.\n*Density\n981.,\n"
NEW_FIBER = "*Damage Evolution, type=ENERGY\n1.,\n*Density\n981.,\n"
OLD_MATRIX = "*Material, name=Matrix\n*Damage Initiation, criterion=DUCTILE\n 0.01, 0.333333,     0.01\n"
NEW_MATRIX = "*Material, name=Matrix\n*Damage Initiation, criterion=DUCTILE\n 0.1, 0.333333,     0.01\n"

text = SRC.read_bytes().decode()
for old, new in ((OLD_FIBER, NEW_FIBER), (OLD_MATRIX, NEW_MATRIX)):
    assert text.count(old) == 1, old
    text = text.replace(old, new)
out.mkdir(parents=True, exist_ok=True)
(out / (NAME + ".inp")).write_bytes(text.encode())
print("wrote", out / (NAME + ".inp"))
