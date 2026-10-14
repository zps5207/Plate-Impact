"""Generate Stage 7 single-VUEL volume-fraction verification decks.

The two Stage 7 cases differ only in SVAR107 (Vf=0 and Vf=0.5).  A
third Vf=0 deck is emitted for the frozen pre-Stage-7 source so ROAR can
perform the requested regression comparison against the old code. Tenfold
slower Vf=0/Vf=0.5 cases test convergence away from dynamic transients.
"""
from pathlib import Path
import shutil

BUNDLE = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent / "roar" / "t_stage7_vf"
EMOD = 2.0e11
ENU = 0.3
DENS = 7800.0
SIGY0 = 2.5e8
HMOD = 2.0e9


def initial_solution(vf):
    values = [0.0] * 106 + [vf]
    lines = ["*Initial Conditions, type=SOLUTION"]
    lines.append(", ".join(["CELL-1.1"] + ["%.12g" % x for x in values[:7]]))
    for start in range(7, 107, 8):
        lines.append(", ".join("%.12g" % x for x in values[start:start + 8]))
    return lines


def deck(name, vf, displacement, duration):
    lines = [
        "*Heading",
        "** Stage 7 host-volume correction: %s, Vf=%.6g" % (name, vf),
        "*Preprint, echo=NO, model=YES, history=NO, contact=NO",
        "*Part, name=CELL",
        "*Node",
        "1, 0, 0, 0", "2, 1, 0, 0", "3, 1, 1, 0", "4, 0, 1, 0",
        "5, 0, 0, 1", "6, 1, 0, 1", "7, 1, 1, 1", "8, 0, 1, 1",
        "*User Element, type=VU1, nodes=8, coordinates=3, properties=13, variables=107",
        "1, 2, 3",
        "*Element, type=VU1, elset=HOSTUEL",
        "1, 1, 2, 3, 4, 5, 6, 7, 8",
        "*UEL Property, elset=HOSTUEL",
        "2e11, 0.3, 7800, 0, 0, 0, 10, 2.5e8",
        "2e9, 1, 0.01, 0.1, 0",
        "*End Part",
        "*Assembly, name=Assembly",
        "*Instance, name=CELL-1, part=CELL",
        "*End Instance",
        "*Nset, nset=FIXED, instance=CELL-1", "1",
        "*Nset, nset=DRIVEN, instance=CELL-1", "2, 3, 6, 7",
        "*Nset, nset=ALLN, instance=CELL-1", "1, 2, 3, 4, 5, 6, 7, 8",
        "*End Assembly",
    ]
    lines.extend(initial_solution(vf))
    lines.extend([
        "*Amplitude, name=RAMP, definition=SMOOTH STEP",
        "0., 0.", "%.12g, 1" % duration,
        "*Step, name=S1", "*Dynamic, Explicit", ", %.12g" % duration,
        "*Boundary",
        "FIXED, 1, 3", "CELL-1.4, 1, 1", "CELL-1.4, 3, 3",
        "CELL-1.5, 1, 1", "CELL-1.5, 2, 2", "CELL-1.8, 1, 1",
        "*Boundary, amplitude=RAMP",
        "DRIVEN, 1, 1, %.12g" % displacement,
        "*Output, field, number interval=100",
        "*Node Output", "U, RF",
        "*Output, history, time interval=2e-05",
        "*Energy Output", "ALLIE, ALLKE, ALLWK, ALLVD, ALLAE, ALLPD, ETOTAL",
        "*End Step",
    ])
    return "\n".join(lines) + "\n"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    cases = []
    for mode, displacement in (("tension", 0.04),
                               ("compression", -0.04)):
        cases.extend((("stage7_%s_vf0" % mode, 0.0, displacement,
                       0.01, False),
                      ("stage7_%s_vf05" % mode, 0.5, displacement,
                       0.01, False),
                      ("stage7_%s_vf0_baseline" % mode, 0.0,
                       displacement, 0.01, True),
                      ("stage7_slow_%s_vf0" % mode, 0.0, displacement,
                       0.1, False),
                      ("stage7_slow_%s_vf05" % mode, 0.5, displacement,
                       0.1, False)))
    for name, vf, displacement, duration, baseline in cases:
        (OUT / (name + ".inp")).write_text(
            deck(name, vf, displacement, duration), newline="")
        source = (OUT / "VUEL_failure_pre_stage7.for" if baseline else
                  BUNDLE / "uel" / "VUEL_failure.for")
        shutil.copyfile(source, OUT / (name + "_user.for"))
    (OUT / "decks_stage7_vf.txt").write_text(
        "\n".join(case[0] for case in cases) + "\n", newline="")


if __name__ == "__main__":
    main()
