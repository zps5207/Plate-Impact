"""Generate T3 (Explicit) decks into verification/roar/t3/."""
import sys, math, shutil
import numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from verification.vlib import *
from verification.deckgen import *

OUT = ROOT / "verification" / "roar" / "t3"; OUT.mkdir(parents=True, exist_ok=True)
MESH = OUT / "_mesher_out"; MESH.mkdir(exist_ok=True)
PRE = "*Preprint, echo=NO, model=YES, history=NO, contact=NO"
made = []
def deliver(tag, text): (OUT / f"{tag}.inp").write_text(text); made.append(tag)
def add_preprint(p):
    t = p.read_text()
    if "*Preprint" not in t: p.write_text(t.replace("*Heading\n", "*Heading\n" + PRE + "\n", 1))

def single_host(fiber_frac_fibers, tag, d, case, T=2e-5, dz=0.001, vumat=False, elemtype="truss"):
    """fiber_frac_fibers: number of straight fiber layers (each layer full 0/90 pass) via gap; d controls volume fraction."""
    L = (1.0, 1.0, 1.0)
    p = OUT / f"{tag}_src.inp"
    n0, e0 = hex_plate_deck(p, 1, 1, 1, *L)
    left = sorted(k for k, c in n0.items() if abs(c[0]) < 1e-9); right = sorted(k for k, c in n0.items() if abs(c[0] - 1) < 1e-9)
    bottom = sorted(k for k, c in n0.items() if abs(c[2]) < 1e-9); top = sorted(k for k, c in n0.items() if abs(c[2] - 1) < 1e-9)
    front = sorted(k for k, c in n0.items() if abs(c[1]) < 1e-9); back = sorted(k for k, c in n0.items() if abs(c[1] - 1) < 1e-9)
    origin = min(n0, key=lambda k: sum(n0[k]))
    def fmt(v): return ", ".join(map(str, v))
    asm = (f"*Nset, nset=LEFT, instance=PLATE-1\n{fmt(left)}\n*Nset, nset=RIGHT, instance=PLATE-1\n{fmt(right)}\n"
           f"*Nset, nset=BOTTOM, instance=PLATE-1\n{fmt(bottom)}\n*Nset, nset=TOP, instance=PLATE-1\n{fmt(top)}\n"
           f"*Nset, nset=FRONT, instance=PLATE-1\n{fmt(front)}\n*Nset, nset=BACK, instance=PLATE-1\n{fmt(back)}\n"
           f"*Nset, nset=ORIGIN, instance=PLATE-1\n{origin}\n*Nset, nset=ALLN, instance=PLATE-1\n{fmt(sorted(n0))}")
    hex_plate_deck(p, 1, 1, 1, *L, extra_part="*Solid Section, elset=HOST, material=MATRIX\n,", extra_asm=asm); add_preprint(p)
    o = run_mesher(p, MESH / tag, d=d, ftype=elemtype)
    txt, info = relocate(o.read_text(), fiber_material="FIBER")
    tail = materials("FIBER", True, vumat=vumat) + step_block(case(dz), T=T, print_nset="ALLN")
    deliver(tag, txt + "\n".join(tail))

def bc_uniax_along():   # load along fiber (t0) axis
    return lambda dz: ["*Boundary", "LEFT, 1, 1", "ORIGIN, 2, 3", "*Boundary, amplitude=RAMP", "RIGHT, 1, 1, %g" % dz]
def bc_uniax_across():  # load perpendicular (y, across t0 fibers)
    return lambda dz: ["*Boundary", "FRONT, 2, 2", "ORIGIN, 1, 3", "*Boundary, amplitude=RAMP", "BACK, 2, 2, %g" % dz]
def bc_shear():
    return lambda dz: ["*Boundary", "BOTTOM, 1, 3", "*Boundary, amplitude=RAMP", "TOP, 1, 1, %g" % dz, "TOP, 2, 3, 0"]
def bc_hydro():
    return lambda dz: ["*Boundary", "LEFT, 1, 1", "FRONT, 2, 2", "BOTTOM, 3, 3", "*Boundary, amplitude=RAMP",
                        "RIGHT, 1, 1, %g" % dz, "BACK, 2, 2, %g" % dz, "TOP, 3, 3, %g" % dz]
def bc_compress():
    return lambda dz: ["*Boundary", "BOTTOM, 3, 3", "LEFT, 1, 1", "FRONT, 2, 2", "*Boundary, amplitude=RAMP", "TOP, 3, 3, -%g" % dz]

for d in (0.15, 0.25, 0.35, 0.45):
    single_host(1, f"single_uniax_along_d{d}", d, bc_uniax_along())
    single_host(1, f"single_uniax_across_d{d}", d, bc_uniax_across())
    single_host(1, f"single_shear_d{d}", d, bc_shear())
    single_host(1, f"single_hydro_d{d}", d, bc_hydro())
single_host(1, "single_compress_d0.25_truss", 0.25, bc_compress())
single_host(1, "single_compress_d0.25_beam", 0.25, bc_compress(), elemtype="beam")
single_host(1, "single_uniax_along_d0.25_beam", 0.25, bc_uniax_along(), elemtype="beam")

# VUMAT: tension to failure, compression clamp, deletion; T3D2 and B31
single_host(1, "vumat_tension_truss", 0.25, bc_uniax_along(), T=5e-5, vumat=True, elemtype="truss")
single_host(1, "vumat_tension_beam", 0.25, bc_uniax_along(), T=5e-5, vumat=True, elemtype="beam")
single_host(1, "vumat_compress_truss", 0.25, bc_compress(), T=5e-5, vumat=True, elemtype="truss")
# fix step dz manually (larger displacement to drive fibers to failure)
def patch_dz(tag, dz):
    t = (OUT / f"{tag}.inp").read_text()
    t = t.replace("RIGHT, 1, 1, 0.001", f"RIGHT, 1, 1, {dz:.6g}").replace("TOP, 3, 3, -0.001", f"TOP, 3, 3, -{dz:.6g}")
    (OUT / f"{tag}.inp").write_text(t)
patch_dz("vumat_tension_truss", 0.02); patch_dz("vumat_tension_beam", 0.02); patch_dz("vumat_compress_truss", 0.02)

# fibers-off control (matrix only, same mesh) for mass/energy baseline
p = OUT / "control_nofiber_src.inp"
n0, e0 = hex_plate_deck(p, 1, 1, 1, 1, 1, 1)
left = sorted(k for k, c in n0.items() if abs(c[0]) < 1e-9); right = sorted(k for k, c in n0.items() if abs(c[0] - 1) < 1e-9)
origin = min(n0, key=lambda k: sum(n0[k]))
asm = f"*Nset, nset=LEFT, instance=PLATE-1\n{','.join(map(str,left))}\n*Nset, nset=RIGHT, instance=PLATE-1\n{','.join(map(str,right))}\n*Nset, nset=ORIGIN, instance=PLATE-1\n{origin}\n*Nset, nset=ALLN, instance=PLATE-1\n{','.join(map(str,sorted(n0)))}"
tail = materials("FIBER", False) + step_block(["*Boundary", "LEFT,1,1", "ORIGIN,2,3", "*Boundary, amplitude=RAMP", "RIGHT,1,1,0.001"], T=2e-5, print_nset="ALLN")
hex_plate_deck(p, 1, 1, 1, 1, 1, 1, extra_part="*Solid Section, elset=HOST, material=MATRIX\n,", extra_asm=asm, tail="\n".join(tail)); add_preprint(p)
deliver("control_nofiber", p.read_text())

# ---- Cantilever ----
def cantilever(tag, nx, ny, nz, L, d, gap=0.0, ftype="truss"):
    p = OUT / f"{tag}_src.inp"
    n0, e0 = hex_plate_deck(p, nx, ny, nz, *L)
    fixed = sorted(k for k, c in n0.items() if abs(c[0]) < 1e-9)
    tipset = sorted(k for k, c in n0.items() if abs(c[0] - L[0]) < 1e-9)
    def fmt(v): return "\n".join(", ".join(map(str, v[i:i+12])) for i in range(0, len(v), 12))
    asm = f"*Nset, nset=FIXED, instance=PLATE-1\n{fmt(fixed)}\n*Nset, nset=TIP, instance=PLATE-1\n{fmt(tipset)}"
    hex_plate_deck(p, nx, ny, nz, *L, extra_part="*Solid Section, elset=HOST, material=MATRIX\n,", extra_asm=asm); add_preprint(p)
    o = run_mesher(p, MESH / tag, d=d, gap=gap, ftype=ftype)
    txt, info = relocate(o.read_text(), fiber_material="FIBER")
    T = 4e-4
    tail = materials("FIBER", True) + step_block(["*Boundary", "FIXED, 1, 6" if False else "FIXED, 1, 3", "*Dload", "PLATE-1.HOST, GRAV, 9810., 0., 0., -1."], T=T, print_nset="TIP",
                                                    mass_scale="*Fixed Mass Scaling, factor=1.0")
    deliver(tag, txt + "\n".join(tail))
cantilever("cantilever_10x2x2", 10, 2, 2, (100.0, 10.0, 10.0), 2.0)
cantilever("cantilever_40x4x4", 40, 4, 4, (100.0, 10.0, 10.0), 2.0)

# ---- Sensitivity: fiber element length vs host size (systematic sweep of mesh density with fixed d) ----
for n in (1, 2, 4):
    single_host(1, f"sens_hostsize_n{n}", 0.15, bc_uniax_along())  # reuse single-host but vary via separate mesh below
def sens_mesh(tag, n, L, d):
    p = OUT / f"{tag}_src.inp"
    n0, e0 = hex_plate_deck(p, n, n, n, *L)
    left = sorted(k for k, c in n0.items() if abs(c[0]) < 1e-9); right = sorted(k for k, c in n0.items() if abs(c[0] - L[0]) < 1e-9)
    origin = min(n0, key=lambda k: sum(n0[k]))
    def fmt(v): return "\n".join(", ".join(map(str, v[i:i+12])) for i in range(0, len(v), 12))
    asm = f"*Nset, nset=LEFT, instance=PLATE-1\n{fmt(left)}\n*Nset, nset=RIGHT, instance=PLATE-1\n{fmt(right)}\n*Nset, nset=ORIGIN, instance=PLATE-1\n{origin}\n*Nset, nset=ALLN, instance=PLATE-1\n{fmt(sorted(n0))}"
    hex_plate_deck(p, n, n, n, *L, extra_part="*Solid Section, elset=HOST, material=MATRIX\n,", extra_asm=asm); add_preprint(p)
    o = run_mesher(p, MESH / tag, d=d)
    txt, info = relocate(o.read_text(), fiber_material="FIBER")
    tail = materials("FIBER", True) + step_block(["*Boundary", "LEFT,1,1", "ORIGIN,2,3", "*Boundary, amplitude=RAMP", "RIGHT,1,1,0.001"], T=3e-5, print_nset="ALLN")
    deliver(tag, txt + "\n".join(tail))
for n in (1, 2, 3, 4):
    sens_mesh(f"sens_refine_n{n}", n, (2.0, 2.0, 2.0), 0.2)

(OUT / "decks.txt").write_text("\n".join(made) + "\n")
print(len(made), "decks written")
