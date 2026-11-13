"""Corrected-ball Valerie plywise decks with 3 hex layers through each ply (T-053 mesher option).

Thin wrapper over build_vals_ballfix.py: same ball swap, rigid ball, 1028 m/s, flags, but with the
ball grid doubled (N_CELLS 8, N_RAD 4: half-size elements) and --through-thickness N (3) to the embmesh plywise call. Decks are written as
<out>/{native,vuel}/vrb3_{native,vuel}.inp.
Usage: python verification/roar/build_vals_ballfix_tt3.py [out_dir] (default Meshing/vals-plywise-ballfix-tt3)
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
NT = 3
default_out = HERE.parent.parent / "Meshing" / "vals-plywise-ballfix-tt3"
sys.argv = [sys.argv[0], sys.argv[1] if len(sys.argv) > 1 else str(default_out)]

import build_vals_plywise as bvp  # noqa: E402
_orig = bvp.run_cli
bvp.run_cli = lambda deck, out, extra: _orig(deck, out, [*extra, "--through-thickness", str(NT)])
import build_vals_ballfix as bvf  # noqa: E402
bvf.N_CELLS, bvf.N_RAD = 8, 4   # half the ball element size of the 1-layer decks (4, 2): ~0.6 mm

if __name__ == "__main__":
    bvf.main()
