"""Build d4_weldox_100us from the d3_elastic_100us deck: ball steel = Weldox 460E JC plasticity + JC damage with
energy-based evolution (Iqbal et al. 2015, as given by the user), ball-only section controls with max degradation 0.5.

Usage: python verification/roar/ball_tests/build_ball_tests4.py [out_dir]
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3] / "Meshing" / "vals-plywise-balltests3"
SRC = ROOT / "d3_elastic_100us" / "d3_elastic_100us.inp"
NAME = "d4_weldox_100us"
out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / NAME

OLD_MAT = '*Material, name="Mild Steel"\n*Density\n7850.,\n*Elastic\n 2.03e+11, 0.33\n'
NEW_MAT = ('*Material, name="Mild Steel"\n'
           '*Damage Initiation, criterion=JOHNSON COOK\n'
           ' 0.1152,   1.0116,  -1.7684, -0.05279,   0.5262,    1800.,     293.,   0.0001\n'
           '*Damage Evolution, type=ENERGY\n'
           '54.9,\n'
           '*Density\n7850.,\n*Elastic\n 2.03e+11, 0.33\n'
           '*Plastic, hardening=JOHNSON COOK\n'
           ' 3.04330e+08, 4.22007e+08,       0.345,        0.87,       1800.,        293.\n')
BALL_SEC = '*Solid Section, elset=_PickedSet2, material="Mild Steel", controls=EMBMESH_DELETE_ALL'
MARKER = '*Section Controls, name=EMBMESH_DELETE_ALL, element deletion=YES, max degradation=0.8\n'

text = SRC.read_bytes().decode()
for s in (OLD_MAT, BALL_SEC, MARKER):
    assert text.count(s) == 1, s
text = text.replace(OLD_MAT, NEW_MAT)
text = text.replace(BALL_SEC, BALL_SEC.replace("EMBMESH_DELETE_ALL", "EMBMESH_BALL_CTRL"))
text = text.replace(MARKER, MARKER + '*Section Controls, name=EMBMESH_BALL_CTRL, element deletion=YES, max degradation=0.5\n')
out.mkdir(parents=True, exist_ok=True)
(out / (NAME + ".inp")).write_bytes(text.encode())
print("wrote", out / (NAME + ".inp"))
