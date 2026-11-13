r"""NewVals 3-layer VUEL deck with the through-thickness SMEARED volume correction and a 100 us step.

Same inputs as build_newvals_paper_tt3.py (paper materials, rigid ball 1028 m/s, cohesive card), VUEL host only,
plus --vuel-smear-through-thickness (every hex of a column gets the column-mean fiber fraction) and the step time
set to 1e-4 s (the first tt3 decks inherited 70 us from NewVals.inp by mistake).
Usage: python verification/roar/build_newvals_smear_tt3.py [out_dir]  (default Meshing/newvals-smear-tt3)
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "Meshing" / "newvals-smear-tt3"
sys.argv = sys.argv[:1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_newvals_paper_tt3 as bn  # noqa: E402
import build_vals_ballfix as bvf  # noqa: E402

NL = "\n"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    text = bn.SRC.read_text().replace("\r\n", NL)
    text = bn.replace_block(text, "Fiber", bn.FIBER)
    text = bn.replace_block(text, "Matrix", bn.MATRIX)
    marker = "*Surface Behavior, pressure-overclosure=HARD" + NL
    assert text.count(marker) == 1
    text = text.replace(marker, marker + "** " + NL + bn.COHESIVE, 1)
    assert text.count("_PickedSet13, 3, -1000.") == 1
    text = text.replace("_PickedSet13, 3, -1000.", "_PickedSet13, 3, -%d." % bn.SPEED, 1)
    step = "*Dynamic, Explicit" + NL + ", 7e-05" + NL
    assert text.count(step) == 1
    text = text.replace(step, "*Dynamic, Explicit" + NL + ", 1e-04" + NL, 1)
    src = OUT / "NewVals_smear.inp"
    src.write_text(text)
    info = bn.ball_density(src)
    bvf.CENTRE_Z, bvf.SPEED = bn.CENTRE_Z, bn.SPEED
    out = OUT / "vuel"
    out.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-m", "embmesh.cli", "plywise", str(src), "--instance", "Plate-1",
           "--collapse-layers", "--plies", str(bn.PLIES), "--layup", ",".join(["0", "90"] * (bn.PLIES // 2)),
           "--fiber-diameter", str(bn.FIBER_D), "--fiber-gap", "0", "--cohesion", "Cohesion",
           "--plate-node-contact", "--fiber-node-contact", "--ball-instance", "Ball-1",
           "--ball-interaction", "General", "--through-thickness", "3",
           "--host-mode", "vuel-ghost", "--matrix-model", "ductile-damage", "--vuel-eps-fail", "0.1",
           "--vuel-smear-through-thickness", "--output", str(out / "output.inp")]
    with (out / "console.json").open("w") as f:
        subprocess.run(cmd, cwd=ROOT, check=True, stdout=f)
    deck = (out / "output.inp").read_text().replace("\r\n", NL)
    final = out / "nv_vuel_smear.inp"
    final.write_text(bvf.rigid_ball(deck, info["density"]))
    (OUT / "build_log.json").write_text(json.dumps({"ball": info, "vuel": str(final.relative_to(ROOT)),
                                                    "smear": True, "step": 1e-4}, indent=2))
    print("wrote", final)


if __name__ == "__main__":
    main()
