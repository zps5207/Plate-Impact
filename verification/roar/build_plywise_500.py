"""Build the two plywise 500 m/s smoke-test decks (flat + concave) from the virgin decks.

Same settings as the solid VUEL+ghost runs in reports/CURVED_VS_FLAT_REPORT.html: ghost scale 1e-4,
ghost ductile failure strain 1e-6, VU1 eps_fail 0.113800332690901, fibers d = 1 mm with 0.2 mm gap,
node-based ball contact, ball -500 m/s, step 1e-4 s, field/history output every 7e-8 s.
Plywise side: 8 plies [0/90]x4, Hazzard 2018 Dyneema cohesive interface (ballistic rate).
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
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


def main(out_root=ROOT / "Meshing" / "plywise-500"):
    for name, deck in DECKS.items():
        out = Path(out_root) / name
        out.mkdir(parents=True, exist_ok=True)
        subprocess.run([sys.executable, "-m", "embmesh.cli", "plywise", str(deck), *COMMON,
                        "--output", str(out / "output.inp")], cwd=ROOT, check=True,
                       stdout=(out / "console.json").open("w"))
        deck_out = out / "output.inp"
        deck_out.write_text(patch_step(deck_out.read_text()))
        print(name, "ok")


if __name__ == "__main__":
    main()
