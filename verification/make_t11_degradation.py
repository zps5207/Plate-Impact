"""Generate Stage 5 post-failure degradation verification decks.

The five cases separate constitutive checks from the intentionally
observational three-element cascade comparison:

* t11_instant_chain: Stage 4 t10_three_chain repeated with the new interface
  but DEGRADE_TIME=0 and residual=0 (exact instant-zero baseline).
* t11_ramp_chain: identical chain with a 2 ms linear degradation ramp.
* t11_ramp_tension: single hex proving force persists during the ramp and is
  exactly zero after the ramp completes.
* t11_zero_cycle: tension-failure then compression cycle with the Stage 4
  zero-RHS post-failure behavior.
* t11_residual_cycle: identical cycle with 10% compression-only residual bulk
  stiffness, proving zero tensile force and nonzero compressive force.

All writes use newline='' because CRLF deck-list files break the ROAR shell
loop (docs/abaqus-explicit-quirks.md).
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "verification" / "roar" / "t11"
OUT.mkdir(parents=True, exist_ok=True)

EMOD = 2.0e11
ENU = 0.3
DENS = 7800.0
SIGY0 = 2.5e8
HMOD = 2.0e9
IPLAST = 0.0
JAC_FAIL = 0.05

UEL_DEF = ("*User Element, type=VU1, nodes=8, coordinates=3, "
           "properties=13, variables=106\n1, 2, 3")


def props_lines(eps_fail, degrade_time=0.0, residual=0.0):
    values = [EMOD, ENU, DENS, 0.0, 0.0, 0.0, eps_fail, SIGY0,
              HMOD, IPLAST, JAC_FAIL, degrade_time, residual]
    return [", ".join(f"{v:.9g}" for v in values[i:i + 8])
            for i in range(0, len(values), 8)]


def output_block(intervals=80):
    return ["*Output, history, frequency=1000000",
            "*Node Output, nset=ALLN",
            "RF1, RF2, RF3, U1, U2, U3, V1, V2, V3",
            f"*Output, field, number interval={intervals}",
            "*Node Output", "U, RF, V",
            "*Output, history, time interval=2e-05",
            "*Energy Output",
            "ALLIE, ALLKE, ALLWK, ALLVD, ALLAE, ALLPD, ETOTAL"]


def build_chain(degrade_time):
    label = "instant" if degrade_time <= 0.0 else "2 ms ramp"
    t_end = 1.0e-2
    lines = [
        "*Heading",
        f"** T11 Stage 5 three-element chain: {label}",
        "** Same geometry, thresholds, loading, and zero damping as T10",
        "*Preprint, echo=NO, model=YES, history=NO, contact=NO",
        "*Part, name=CELL", "*Node",
        "1, 0, 0, 0", "2, 1, 0, 0", "3, 1, 1, 0", "4, 0, 1, 0",
        "5, 0, 0, 1", "6, 1, 0, 1", "7, 1, 1, 1", "8, 0, 1, 1",
        "9, 2, 0, 0", "10, 2, 1, 0", "11, 2, 0, 1", "12, 2, 1, 1",
        "13, 3, 0, 0", "14, 3, 1, 0", "15, 3, 0, 1", "16, 3, 1, 1",
        UEL_DEF,
        "*Element, type=VU1, elset=ELEM1",
        "1, 1, 2, 3, 4, 5, 6, 7, 8",
        "*Element, type=VU1, elset=ELEM2",
        "2, 2, 9, 10, 3, 6, 11, 12, 7",
        "*Element, type=VU1, elset=ELEM3",
        "3, 9, 13, 14, 10, 11, 15, 16, 12",
        "*UEL Property, elset=ELEM1",
        *props_lines(0.015, degrade_time),
        "*UEL Property, elset=ELEM2",
        *props_lines(0.025, degrade_time),
        "*UEL Property, elset=ELEM3",
        *props_lines(0.04, degrade_time),
        "*End Part",
        "*Assembly, name=Assembly",
        "*Instance, name=CELL-1, part=CELL", "*End Instance",
        "*Nset, nset=FIXED, instance=CELL-1", "1",
        "*Nset, nset=DRIVEN, instance=CELL-1", "13, 14, 15, 16",
        "*Nset, nset=IFACE_A, instance=CELL-1", "2, 3, 6, 7",
        "*Nset, nset=IFACE_B, instance=CELL-1", "9, 10, 11, 12",
        "*Nset, nset=ALLN, instance=CELL-1",
        "1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16",
        "*End Assembly",
        "*Amplitude, name=RAMP, definition=SMOOTH STEP",
        f"0., 0., {t_end:.9g}, 1.",
        "*Step, name=S1", "*Dynamic, Explicit", f", {t_end:.9g}",
        "*Boundary", "FIXED, 1, 3",
        "CELL-1.4, 1, 1", "CELL-1.4, 3, 3",
        "CELL-1.5, 1, 1", "CELL-1.5, 2, 2", "CELL-1.8, 1, 1",
        "*Boundary, amplitude=RAMP", "DRIVEN, 1, 1, 0.3",
        *output_block(60), "*End Step"]
    return "\n".join(lines) + "\n"


def single_hex_prefix(title, eps_fail, degrade_time, residual):
    return [
        "*Heading", f"** {title}",
        "*Preprint, echo=NO, model=YES, history=NO, contact=NO",
        "*Part, name=CELL", "*Node",
        "1, 0, 0, 0", "2, 1, 0, 0", "3, 1, 1, 0", "4, 0, 1, 0",
        "5, 0, 0, 1", "6, 1, 0, 1", "7, 1, 1, 1", "8, 0, 1, 1",
        UEL_DEF,
        "*Element, type=VU1, elset=HOSTUEL",
        "1, 1, 2, 3, 4, 5, 6, 7, 8",
        "*UEL Property, elset=HOSTUEL",
        *props_lines(eps_fail, degrade_time, residual),
        "*End Part", "*Assembly, name=Assembly",
        "*Instance, name=CELL-1, part=CELL", "*End Instance",
        "*Nset, nset=BACK, instance=CELL-1", "1, 4, 5, 8",
        "*Nset, nset=DRIVEN, instance=CELL-1", "2, 3, 6, 7",
        "*Nset, nset=ALLN, instance=CELL-1", "1, 2, 3, 4, 5, 6, 7, 8",
        "*End Assembly"]


def build_ramp_tension():
    t_end = 1.2e-2
    lines = single_hex_prefix(
        "T11 Stage 5 single-hex 2 ms degradation ramp", 0.02, 0.002, 0.0)
    lines += [
        "*Amplitude, name=RAMP, definition=SMOOTH STEP",
        f"0., 0., {t_end:.9g}, 1.",
        "*Step, name=S1", "*Dynamic, Explicit", f", {t_end:.9g}",
        "*Boundary", "CELL-1.1, 1, 3", "CELL-1.4, 1, 1",
        "CELL-1.4, 3, 3", "CELL-1.5, 1, 2", "CELL-1.8, 1, 1",
        "*Boundary, amplitude=RAMP", "DRIVEN, 1, 1, 0.04",
        *output_block(120), "*End Step"]
    return "\n".join(lines) + "\n"


def build_cycle(residual):
    t_end = 1.2e-2
    label = "10 percent compression residual" if residual else "zero RHS"
    lines = single_hex_prefix(
        f"T11 Stage 5 failed tension-to-compression cycle: {label}",
        0.02, 0.0, residual)
    lines += [
        "*Amplitude, name=CYCLE, definition=SMOOTH STEP",
        "0., 0., 0.004, 1., 0.006, 1., 0.012, -2.",
        "*Step, name=S1", "*Dynamic, Explicit", f", {t_end:.9g}",
        "*Boundary", "BACK, 1, 1", "ALLN, 2, 3",
        "*Boundary, amplitude=CYCLE", "DRIVEN, 1, 1, 0.04",
        *output_block(160), "*End Step"]
    return "\n".join(lines) + "\n"


def main():
    user_source = (ROOT / "uel" / "VUEL_failure.for").read_text()
    checker_source = (ROOT / "verification" /
                      "t11_check_degradation.py").read_text()
    decks = {
        "t11_instant_chain": build_chain(0.0),
        "t11_ramp_chain": build_chain(0.002),
        "t11_ramp_tension": build_ramp_tension(),
        "t11_zero_cycle": build_cycle(0.0),
        "t11_residual_cycle": build_cycle(0.1),
    }
    for name, text in decks.items():
        (OUT / f"{name}.inp").write_text(text, newline='')
        (OUT / f"{name}_user.for").write_text(user_source, newline='')
    (OUT / "decks_t11.txt").write_text(
        "\n".join(decks) + "\n", newline='')
    (OUT / "t11_check_degradation.py").write_text(
        checker_source, newline='')
    print(f"wrote {len(decks)} Stage 5 decks to {OUT}")


if __name__ == "__main__":
    main()
