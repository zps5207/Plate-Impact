"""Build the two plywise 500 m/s smoke-test decks (flat + concave) from the virgin decks.

Same settings as the solid VUEL+ghost runs in reports/CURVED_VS_FLAT_REPORT.html: ghost scale 1e-4,
ghost ductile failure strain 1e-6, VU1 eps_fail 0.113800332690901, fibers d = 1 mm with 0.2 mm gap,
node-based ball contact, ball -500 m/s, step 1e-4 s, field/history output every 7e-8 s.
Plywise side: 8 plies [0/90]x4, Hazzard 2018 Dyneema cohesive interface (ballistic rate).
"""
import re
import sys
from pathlib import Path
from contextlib import redirect_stdout

outbox_root = Path(__file__).resolve().parent
repo_root = Path(__file__).resolve().parents[4]

if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

import embmesh
outbox_embmesh = str(outbox_root / 'embmesh')
if outbox_embmesh not in embmesh.__path__:
    embmesh.__path__.insert(0, outbox_embmesh)

if str(outbox_root) not in sys.path:
    sys.path.insert(0, str(outbox_root))

from embmesh.cli import main as cli_main

ROOT = repo_root
DECKS = {"flat": ROOT / "Meshing" / "Flatv2.inp",
         "concave": ROOT / "Meshing" / "Flat-concave-roar" / "concave_hostonly.inp"}
COMMON = ["--instance", "Plate-1", "--collapse-layers", "--plies", "8",
          "--layup", "0,90,0,90,0,90,0,90", "--fiber-diameter", "0.001", "--fiber-gap", "0.0002",
          "--host-mode", "vuel-ghost", "--vuel-eps-fail", "0.113800332690901",
          "--ghost-ductile-failure-strain", "1e-6", "--cohesive-material", "dyneema-hb26",
          "--cohesive-rate", "ballistic", "--cohesive-name", "Cohesion", "--cohesive-overwrite",
          "--plate-node-contact", "--fiber-node-contact", "--ball-instance", "Ball-1", "--preview"]


def patch_step(text):
    text = re.sub(r"(Ball-1\.Ball, 3, )-1000\.", r"\1-500.", text)
    text = text.replace("\n, 7e-05\n", "\n, 1e-04\n")
    text = text.replace("*Output, field, variable=PRESELECT, number interval=1000",
                        "*Output, field, variable=PRESELECT, time interval=7e-08")
    text = text.replace("*Output, field, number interval=1000", "*Output, field, time interval=7e-08")
    return text


def main(out_root=outbox_root / "plywise-500"):
    for name, deck in DECKS.items():
        out = Path(out_root) / name
        out.mkdir(parents=True, exist_ok=True)
        with (out / "console.json").open("w") as f:
            with redirect_stdout(f):
                rc = cli_main(["plywise", str(deck), *COMMON, "--output", str(out / "output.inp")])
                if rc != 0:
                    raise RuntimeError(f"CLI failed with exit code {rc}")
        deck_out = out / "output.inp"
        deck_out.write_text(patch_step(deck_out.read_text()))
        print(name, "ok")


if __name__ == "__main__":
    main()
