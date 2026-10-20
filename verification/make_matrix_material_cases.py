"""Generate single-element verification decks for matrix material (Stage 8).

Generates 18 decks:
- 3 loading modes: uniaxial tension, uniaxial compression, pure shear
- 3 strain rates: 0.01 /s, 1.0 /s, 1000.0 /s
- 2 model variants: User VUEL (VUEL_material.for) and Native Abaqus twin (C3D8R + *Plastic + *Damage Initiation + *Damage Evolution)

Decks are written to verification/roar/matrix_material/.
Companion user Fortran files are written for every VUEL deck.
List of deck names is saved in decks_matrix_material.txt.
"""

from __future__ import print_function
import sys
import os
from pathlib import Path

# Cube edge length [m]. 1 mm so the characteristic length (L = V^(1/3)) gives a
# visible softening branch: ubar_f/L = 2*Gf/sigy0/L = 4.2e-5/1e-3 = 0.042.
SIZE = 1.0e-3
_UNIT = {
    1: (0.0, 0.0, 0.0),
    2: (1.0, 0.0, 0.0),
    3: (1.0, 1.0, 0.0),
    4: (0.0, 1.0, 0.0),
    5: (0.0, 0.0, 1.0),
    6: (1.0, 0.0, 1.0),
    7: (1.0, 1.0, 1.0),
    8: (0.0, 1.0, 1.0),
}
NODES = dict((k, tuple(c * SIZE for c in v)) for k, v in _UNIT.items())

# Matrix material properties
EMOD = 700.0e6      # Pa
ENU = 0.45
DENS = 980.0        # kg/m^3
SIGY0 = 70.0e6      # Pa
GF_MAT = 1460.0     # J/m^2
EPS_F = 0.10        # plastic strain at damage onset


def vuel_props_lines():
    """Build UEL Property data lines for VUEL_material.for (39 properties, at most 8 per line)."""
    vals = [
        # Props 1..13 (legacy props)
        EMOD, ENU, DENS, 0.0, 0.0, 0.0, 10.0, SIGY0,
        0.0, 1.0, 0.0, 0.0, 0.0,
        # Props 14..19 (Stage 8 model control)
        1.0,          # MAT_MODEL = 1 (ductile damage active)
        0.0,          # RATE_MODE = 0 (plastic strain rate)
        GF_MAT,       # GF_MAT = 1460 J/m^2
        0.0,          # RESSTIFF = 0
        1.0,          # NYTAB = 1
        1.0,          # NETAB = 1
        # Props 20..29: Yield table (5 pairs: rate, sigy)
        0.01, SIGY0,
        0.0, 0.0,
        0.0, 0.0,
        0.0, 0.0,
        0.0, 0.0,
        # Props 30..39: Fracture strain table (5 pairs: rate, epsf)
        0.01, EPS_F,
        0.0, 0.0,
        0.0, 0.0,
        0.0, 0.0,
        0.0, 0.0,
    ]
    lines = []
    for i in range(0, len(vals), 8):
        chunk = vals[i:i + 8]
        lines.append(", ".join("{:.6g}".format(v) for v in chunk))
    return lines


def build_vuel_deck(name, mode, rate, total_time, peak_disp):
    """Generate User VUEL input deck."""
    dt_out = total_time / 100.0
    props = vuel_props_lines()

    L = [
        "*Heading",
        "** Matrix Material VUEL single-element check: " + name,
        "** Mode: " + mode + ", Nominal Rate: " + str(rate) + " /s",
        "** Units: SI (m, kg, s, Pa, J)",
        "*Preprint, echo=NO, model=YES, history=NO, contact=NO",
        "*Part, name=CELL",
        "*Node",
    ]
    for nid, (x, y, z) in NODES.items():
        L.append("{}, {:.8g}, {:.8g}, {:.8g}".format(nid, x, y, z))

    L += [
        "*User Element, type=VU1, nodes=8, coordinates=3, properties=39, variables=159",
        "1, 2, 3",
        "*Element, type=VU1, elset=HOSTUEL",
        "1, 1, 2, 3, 4, 5, 6, 7, 8",
        "*UEL Property, elset=HOSTUEL",
    ]
    L += props
    L += [
        "*End Part",
        "*Assembly, name=Assembly",
        "*Instance, name=CELL-1, part=CELL",
        "*End Instance",
        "*Nset, nset=FIXED, instance=CELL-1",
        "1",
        "*Nset, nset=ALLN, instance=CELL-1",
        "1, 2, 3, 4, 5, 6, 7, 8",
        "*Nset, nset=FRONT_X, instance=CELL-1",
        "2, 3, 6, 7",
        "*Nset, nset=BACK_X, instance=CELL-1",
        "1, 4, 5, 8",
        "*Nset, nset=BOT_Y, instance=CELL-1",
        "1, 2, 5, 6",
        "*Nset, nset=TOP_Y, instance=CELL-1",
        "3, 4, 7, 8",
        "*End Assembly",
        "*Amplitude, name=RAMP, definition=SMOOTH STEP",
        "0., 0., {:.6g}, 1.".format(total_time),
        "*Step, name=S1",
        "*Dynamic, Explicit",
        ", {:.6g}".format(total_time),
    ]

    # Boundary conditions
    if mode in ("tension", "compression"):
        L += [
            "*Boundary",
            "FIXED, 1, 3",
            "CELL-1.4, 1, 1",
            "CELL-1.4, 3, 3",
            "CELL-1.5, 1, 1",
            "CELL-1.5, 2, 2",
            "CELL-1.8, 1, 1",
            "*Boundary, amplitude=RAMP",
            "FRONT_X, 1, 1, {:.6g}".format(peak_disp),
        ]
    elif mode == "shear":
        L += [
            "*Boundary",
            "BOT_Y, 1, 3",
            "TOP_Y, 2, 3",
            "*Boundary, amplitude=RAMP",
            "TOP_Y, 1, 1, {:.6g}".format(peak_disp),
        ]

    # History & field outputs
    L += [
        "*Output, history, frequency=1000000",
        "*Node Output, nset=ALLN",
        "RF1, RF2, RF3, U1, U2, U3",
        "*Output, history, time interval={:.6g}".format(dt_out),
        "*Energy Output",
        "ALLIE, ALLPD, ALLKE, ALLDMD, ALLWK, ETOTAL",
        "*Output, field, number interval=400",
        "*Node Output",
        "U, RF",
        "*End Step",
    ]
    return "\n".join(L) + "\n"


def build_native_deck(name, mode, rate, total_time, peak_disp):
    """Generate Native Abaqus twin input deck (C3D8R + ductile damage)."""
    dt_out = total_time / 100.0

    L = [
        "*Heading",
        "** Matrix Material Native Twin check: " + name,
        "** Mode: " + mode + ", Nominal Rate: " + str(rate) + " /s",
        "** Units: SI (m, kg, s, Pa, J)",
        "*Preprint, echo=NO, model=YES, history=NO, contact=NO",
        "*Part, name=CELL",
        "*Node",
    ]
    for nid, (x, y, z) in NODES.items():
        L.append("{}, {:.8g}, {:.8g}, {:.8g}".format(nid, x, y, z))

    L += [
        "*Element, type=C3D8R, elset=HOSTNATIVE",
        "1, 1, 2, 3, 4, 5, 6, 7, 8",
        "*Solid Section, elset=HOSTNATIVE, material=MATRIX_NATIVE",
        "1.0",
        "*End Part",
        "*Material, name=MATRIX_NATIVE",
        "*Density",
        "{:.6g}".format(DENS),
        "*Elastic",
        "{:.6g}, {:.6g}".format(EMOD, ENU),
        "*Plastic",
        "{:.6g}, 0.".format(SIGY0),
        "*Damage Initiation, criterion=DUCTILE",
        "{:.6g}, 0.333333333333, 0.01".format(EPS_F),
        "*Damage Evolution, type=ENERGY",
        "{:.6g}".format(GF_MAT),
        "*Assembly, name=Assembly",
        "*Instance, name=CELL-1, part=CELL",
        "*End Instance",
        "*Nset, nset=FIXED, instance=CELL-1",
        "1",
        "*Nset, nset=ALLN, instance=CELL-1",
        "1, 2, 3, 4, 5, 6, 7, 8",
        "*Nset, nset=FRONT_X, instance=CELL-1",
        "2, 3, 6, 7",
        "*Nset, nset=BACK_X, instance=CELL-1",
        "1, 4, 5, 8",
        "*Nset, nset=BOT_Y, instance=CELL-1",
        "1, 2, 5, 6",
        "*Nset, nset=TOP_Y, instance=CELL-1",
        "3, 4, 7, 8",
        "*End Assembly",
        "*Amplitude, name=RAMP, definition=SMOOTH STEP",
        "0., 0., {:.6g}, 1.".format(total_time),
        "*Step, name=S1",
        "*Dynamic, Explicit",
        ", {:.6g}".format(total_time),
    ]

    # Boundary conditions
    if mode in ("tension", "compression"):
        L += [
            "*Boundary",
            "FIXED, 1, 3",
            "CELL-1.4, 1, 1",
            "CELL-1.4, 3, 3",
            "CELL-1.5, 1, 1",
            "CELL-1.5, 2, 2",
            "CELL-1.8, 1, 1",
            "*Boundary, amplitude=RAMP",
            "FRONT_X, 1, 1, {:.6g}".format(peak_disp),
        ]
    elif mode == "shear":
        L += [
            "*Boundary",
            "BOT_Y, 1, 3",
            "TOP_Y, 2, 3",
            "*Boundary, amplitude=RAMP",
            "TOP_Y, 1, 1, {:.6g}".format(peak_disp),
        ]

    # History & field outputs
    L += [
        "*Output, history, frequency=1000000",
        "*Node Output, nset=ALLN",
        "RF1, RF2, RF3, U1, U2, U3",
        "*Output, history, time interval={:.6g}".format(dt_out),
        "*Energy Output",
        "ALLIE, ALLPD, ALLKE, ALLDMD, ALLWK, ETOTAL",
        "*Output, field, number interval=400",
        "*Node Output",
        "U, RF",
        "*Element Output, directions=YES",
        "S, E, PEEQ, SDEG, DMICRT, STATUS",
        "*End Step",
    ]
    return "\n".join(L) + "\n"


def main():
    # Resolve target output directory
    here = Path(__file__).resolve().parent
    out_dir = here / "roar" / "matrix_material"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Locate source VUEL_material.for
    vuel_src_path = here.parent / "uel" / "VUEL_material.for"
    if not vuel_src_path.exists():
        # Fallback to current directory or outbox
        alt_path = Path("outbox/T-042/uel/VUEL_material.for")
        if alt_path.exists():
            vuel_src_path = alt_path
        else:
            raise RuntimeError("Cannot find VUEL_material.for at " + str(vuel_src_path))
    vuel_src = vuel_src_path.read_text()

    # Cases matrix: 3 modes x 3 rates
    modes = {
        "tension": 0.50,      # peak nominal strain +0.5 (onset near 0.22)
        "compression": -0.40, # peak nominal strain -0.4 (onset near -0.18)
        "shear": 1.00,        # peak shear gamma 1.0 (onset near 0.35)
    }
    rates = {
        "r0p01": 0.01,
        "r1": 1.0,
        "r1000": 1000.0,
    }

    deck_names = []
    count = 0

    for mode, strain in modes.items():
        for rname, rval in rates.items():
            abs_strain = abs(strain)
            total_time = abs_strain / rval   # smooth step: mean rate = rval
            disp = strain * SIZE             # nominal strain -> displacement [m]

            # 1. User VUEL deck
            vuel_name = "vuel_{}_{}".format(mode, rname)
            vuel_inp = build_vuel_deck(vuel_name, mode, rval, total_time, disp)
            (out_dir / "{}.inp".format(vuel_name)).write_text(vuel_inp, newline="")
            (out_dir / "{}_user.for".format(vuel_name)).write_text(vuel_src, newline="")
            deck_names.append(vuel_name)
            count += 1

            # 2. Native Abaqus twin deck
            native_name = "native_{}_{}".format(mode, rname)
            native_inp = build_native_deck(native_name, mode, rval, total_time, disp)
            (out_dir / "{}.inp".format(native_name)).write_text(native_inp, newline="")
            deck_names.append(native_name)
            count += 1

    # Write decks listing file
    list_path = out_dir / "decks_matrix_material.txt"
    list_path.write_text("\n".join(deck_names) + "\n", newline="")

    print("Generated {} verification decks to {}".format(count, out_dir))
    print("Wrote deck list to {}".format(list_path))


if __name__ == "__main__":
    main()
