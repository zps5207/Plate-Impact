"""Generate ROAR verification cases for the T-006 two-volume VUEL."""
from pathlib import Path
import shutil


BUNDLE = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent / "roar" / "t_t006_volcorr"


def solution_record(instance, element, vf):
    values = [0.0] * 106 + [vf]
    rows = [", ".join([f"{instance}.{element}"] +
                       [f"{value:.12g}" for value in values[:7]])]
    for start in range(7, 107, 8):
        rows.append(", ".join(f"{value:.12g}"
                              for value in values[start:start + 8]))
    return rows


def single_deck(name, vf, displacement, duration, b1=0.0, b2=0.0):
    lines = [
        "*Heading", f"** T-006 {name}; Vf={vf:.6g}",
        "*Preprint, echo=NO, model=YES, history=NO, contact=NO",
        "*Part, name=CELL", "*Node",
        "1, 0,0,0", "2, 1,0,0", "3, 1,1,0", "4, 0,1,0",
        "5, 0,0,1", "6, 1,0,1", "7, 1,1,1", "8, 0,1,1",
        "*User Element, type=VU1, nodes=8, coordinates=3, properties=13, variables=107",
        "1, 2, 3", "*Element, type=VU1, elset=HOSTUEL",
        "1, 1,2,3,4,5,6,7,8", "*UEL Property, elset=HOSTUEL",
        f"2e11, 0.3, 7800, 0, {b1:.12g}, {b2:.12g}, 10, 2.5e8",
        "2e9, 1, 0.01, 0.1, 0", "*End Part",
        "*Assembly, name=Assembly", "*Instance, name=CELL-1, part=CELL",
        "*End Instance", "*Nset, nset=FIXED, instance=CELL-1", "1,4,5,8",
        "*Nset, nset=DRIVEN, instance=CELL-1", "2,3,6,7",
        "*End Assembly", "*Initial Conditions, type=SOLUTION",
    ]
    lines.extend(solution_record("CELL-1", 1, vf))
    lines.extend([
        "*Amplitude, name=RAMP, definition=SMOOTH STEP", "0., 0.",
        f"{duration:.12g}, 1", "*Step, name=S1", "*Dynamic, Explicit",
        f", {duration:.12g}", "*Boundary", "FIXED, 1, 3",
        "*Boundary, amplitude=RAMP", f"DRIVEN, 1, 1, {displacement:.12g}",
        "*Output, field, number interval=200", "*Node Output", "U, RF",
        "*Output, history, time interval=1e-06", "*Energy Output",
        "ALLIE, ALLKE, ALLWK, ALLVD, ALLAE, ALLPD, ETOTAL", "*End Step",
    ])
    return "\n".join(lines) + "\n"


def mixed_deck():
    coords = []
    for offset in (0.0, 2.0):
        coords.extend(((0, offset, 0), (1, offset, 0),
                       (1, offset + 1, 0), (0, offset + 1, 0),
                       (0, offset, 1), (1, offset, 1),
                       (1, offset + 1, 1), (0, offset + 1, 1)))
    lines = ["*Heading", "** T-006 mixed Vf=.3/.6 in one VUEL block",
             "*Preprint, echo=NO, model=YES, history=NO, contact=NO",
             "*Part, name=CELL", "*Node"]
    lines.extend(f"{i}, {x}, {y}, {z}" for i, (x, y, z)
                 in enumerate(coords, 1))
    lines.extend([
        "*User Element, type=VU1, nodes=8, coordinates=3, properties=13, variables=107",
        "1, 2, 3", "*Element, type=VU1, elset=HOSTUEL",
        "1, 1,2,3,4,5,6,7,8", "2, 9,10,11,12,13,14,15,16",
        "*UEL Property, elset=HOSTUEL", "2e11, 0.3, 7800, 0, 0, 0, 10, 2.5e8",
        "2e9, 0, 0.01, 0.1, 0", "*End Part", "*Assembly, name=Assembly",
        "*Instance, name=CELL-1, part=CELL", "*End Instance",
        "*Nset, nset=FIXED_A, instance=CELL-1", "1,4,5,8",
        "*Nset, nset=DRIVEN_A, instance=CELL-1", "2,3,6,7",
        "*Nset, nset=FIXED_B, instance=CELL-1", "9,12,13,16",
        "*Nset, nset=DRIVEN_B, instance=CELL-1", "10,11,14,15",
        "*End Assembly", "*Initial Conditions, type=SOLUTION",
    ])
    lines.extend(solution_record("CELL-1", 1, 0.3))
    lines.extend(solution_record("CELL-1", 2, 0.6))
    lines.extend([
        "*Amplitude, name=RAMP, definition=SMOOTH STEP", "0.,0.", "0.1,1.",
        "*Step, name=S1", "*Dynamic, Explicit", ", 0.1", "*Boundary",
        "FIXED_A, 1, 3", "FIXED_B, 1, 3", "*Boundary, amplitude=RAMP",
        "DRIVEN_A, 1, 1, 0.001", "DRIVEN_B, 1, 1, 0.001",
        "*Output, field, number interval=100", "*Node Output", "U, RF",
        "*End Step",
    ])
    return "\n".join(lines) + "\n"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    cases = []
    for mode, displacement in (("tension", 0.04), ("compression", -0.04)):
        for suffix, vf, baseline in (("vf0", 0.0, False),
                                     ("vf05", 0.5, False),
                                     ("vf0_baseline", 0.0, True)):
            name = f"t006_slow_{mode}_{suffix}"
            (OUT / f"{name}.inp").write_text(
                single_deck(name, vf, displacement, 0.1), newline="")
            cases.append((name, baseline))
    for suffix, vf, b1, b2 in (("vf0", 0.0, 10.0, 10.0),
                               ("vf05", 0.5, 10.0, 10.0),
                               ("physical_vf0", 0.0, 0.0, 0.0),
                               ("physical_vf05", 0.5, 0.0, 0.0)):
        name = f"t006_bulk_{suffix}"
        (OUT / f"{name}.inp").write_text(
            single_deck(name, vf, -0.01, 1.0e-5, b1, b2), newline="")
        cases.append((name, False))
    name = "t006_mixed_vf"
    (OUT / f"{name}.inp").write_text(mixed_deck(), newline="")
    cases.append((name, False))

    for name, baseline in cases:
        source = (OUT / "VUEL_failure_pre_t006.for" if baseline else
                  BUNDLE / "uel" / "VUEL_failure.for")
        shutil.copyfile(source, OUT / f"{name}_user.for")
    (OUT / "cases_t006.txt").write_text(
        "\n".join(name for name, _ in cases) + "\n", newline="")


if __name__ == "__main__":
    main()
