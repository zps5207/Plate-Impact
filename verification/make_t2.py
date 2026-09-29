"""Generate the T2 datacheck decks into verification/roar/t2/ (local files only)."""
import sys, math, shutil, time
import numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from verification.vlib import *
from verification.deckgen import *
from embmesh import curved_layup, writers   # API needed only for the curved case (CLI has no route)

OUT = ROOT / "verification" / "roar" / "t2"; OUT.mkdir(parents=True, exist_ok=True)
MESH = OUT / "_mesher_out"; MESH.mkdir(exist_ok=True)
PRE = "*Preprint, echo=NO, model=YES, history=NO, contact=NO"
made = []

def add_preprint(p):
    t = p.read_text().replace("*Heading\n", "*Heading\n" + PRE + "\n", 1) if "*Preprint" not in p.read_text() else p.read_text()
    p.write_text(t)

def sets_for(nodes, L, x0=0.0):
    left = sorted(k for k, c in nodes.items() if abs(c[0] - x0) < 1e-9)
    right = sorted(k for k, c in nodes.items() if abs(c[0] - (x0 + L[0])) < 1e-9)
    def fmt(v): return "\n".join(", ".join(map(str, v[i:i + 12])) for i in range(0, len(v), 12))
    return ("*Nset, nset=LEFT, instance=PLATE-1\n" + fmt(left) + "\n*Nset, nset=RIGHT, instance=PLATE-1\n" + fmt(right)), left, right

def bcs_uniax():
    return ["*Boundary", "LEFT, 1, 1", "RIGHT, 1, 1, 0.001", "PLATE-1.N1, 2, 3"]   # generic; N1 defined via instance-qualified part nset below

def full_tail(with_fiber_mat=False, fiber_name="FIBER", vumat=False):
    return materials(fiber_name, with_fiber_mat, vumat) + step_block(["*Boundary", "LEFT, 1, 1", "ORIGIN, 2, 3", "*Boundary, amplitude=RAMP", "RIGHT, 1, 1, 0.001"], T=1e-5)

def make_source(tag, nx, ny, nz, L, with_tail, **kw):
    p = OUT / f"{tag}_src.inp"
    n0, e0 = hex_plate_deck(p, nx, ny, nz, *L)                         # to know node ids
    sets, left, right = sets_for(n0, L, kw.get("x0", 0.0))
    origin = min(n0, key=lambda k: sum(abs(v) for v in n0[k]))
    asm = sets + f"\n*Nset, nset=ORIGIN, instance=PLATE-1\n{origin}"
    tail = full_tail() if with_tail else ""
    nodes, elems = source_deck(p, nx, ny, nz, L, asm_extra=asm, tail_lines=tail if tail else [], **kw)
    add_preprint(p)
    return p, nodes, elems

def deliver(tag, text):
    (OUT / f"{tag}.inp").write_text(text); made.append(tag)

def mesh_asis_and_reloc(tag, nx, ny, nz, L, d, gap=0.0, ftype="truss", nofiber_mat=False, **kw):
    # (A) as generated: complete source deck (with step) -> mesher appends fibers after *End Step
    p, nodes, elems = make_source(tag + "A", nx, ny, nz, L, True, **kw)
    o = run_mesher(p, MESH / f"{tag}A", d=d, gap=gap, ftype=ftype)
    deliver(f"{tag}_asis", o.read_text())
    # (B) relocated: source without step -> mesher -> relocate -> materials + step
    p2, _, _ = make_source(tag + "B", nx, ny, nz, L, False, **kw)
    o2 = run_mesher(p2, MESH / f"{tag}B", d=d, gap=gap, ftype=ftype)
    txt, info = relocate(o2.read_text(), fiber_material="FIBER")
    txt += "\n".join(full_tail(True) + [""])
    deliver(f"{tag}_reloc", txt)
    return nodes, elems

L = (2.0, 2.0, 1.0)
mesh_asis_and_reloc("flat_truss", 4, 4, 2, L, 0.25)
mesh_asis_and_reloc("flat_beam", 4, 4, 2, L, 0.25, ftype="beam")

# fibers exactly on inter-element faces + one fiber wholly outside the plate
_, _ = mesh_asis_and_reloc("face", 4, 4, 2, L, 0.5, gap=0.5)
# L-shaped plate: many fiber ends in no host
skip = {e for e in range(1, 33) if ((e - 1) % 4) >= 2 and (((e - 1) // 4) % 4) >= 2}
_, _ = mesh_asis_and_reloc("lshape", 4, 4, 2, L, 0.25, skip_elems=skip)

# skewed / sheared mesh, plus exterior-tolerance variants
def skewed_source(tag, with_tail):
    p, nodes, elems = make_source(tag, 3, 3, 2, (3.0, 3.0, 2.0), with_tail)
    rng = np.random.default_rng(7); out = []; sec = ""
    for ln in p.read_text().splitlines():
        if ln.startswith("*"): sec = ln.lower(); out.append(ln); continue
        if sec.startswith("*node") and "nset" not in sec and ln[0].isdigit() and ln.count(",") == 3:
            v = ln.split(","); n = int(v[0]); c = np.array([float(x) for x in v[1:4]])
            if (0 < c[0] < 3) and (0 < c[1] < 3) and (0 < c[2] < 2): c = c + rng.uniform(-0.18, 0.18, 3)
            c[0] += 0.2 * c[2]; out.append(f"{n}, {c[0]:.12g}, {c[1]:.12g}, {c[2]:.12g}")
        else: out.append(ln)
    p.write_text("\n".join(out) + "\n"); return p
sk = skewed_source("skewB", False); o = run_mesher(sk, MESH / "skewB", d=0.2)
base, _ = relocate(o.read_text(), fiber_material="FIBER"); base += "\n".join(full_tail(True) + [""])
# (RIGHT/LEFT sets are x-coordinate based in make_source; on the sheared mesh LEFT/RIGHT no longer lie on x=0/3, so use node ids)
deliver("skew_reloc", base)
deliver("skew_tol1e-3", base.replace("*Embedded Element, host elset=PLATE-1.HOST", "*Embedded Element, host elset=PLATE-1.HOST, absolute exterior tolerance=1e-3"))
deliver("skew_tol0p5", base.replace("*Embedded Element, host elset=PLATE-1.HOST", "*Embedded Element, host elset=PLATE-1.HOST, absolute exterior tolerance=0.5"))
deliver("skew_tolfrac0p3", base.replace("*Embedded Element, host elset=PLATE-1.HOST", "*Embedded Element, host elset=PLATE-1.HOST, fractional exterior tolerance=0.3"))

# curved: cylindrical shell (ring of hexes) + API-generated axial fibers (no CLI route exists for curved layup)
def cyl_source(with_tail):
    nr, nt, nz = 5, 24, 10; r0, r1, H = 2.0, 3.0, 5.0
    nid = lambda i, j, k: 1 + i + (nr + 1) * ((j % nt) + nt * k)
    nodes = {}
    for k in range(nz + 1):
        for j in range(nt):
            for i in range(nr + 1):
                r = r0 + (r1 - r0) * i / nr; th = 2 * math.pi * j / nt; nodes[nid(i, j, k)] = (r * math.cos(th), r * math.sin(th), H * k / nz)
    el = {}; e = 1
    for k in range(nz):
        for j in range(nt):
            for i in range(nr):
                el[e] = (nid(i, j, k), nid(i + 1, j, k), nid(i + 1, j + 1, k), nid(i, j + 1, k), nid(i, j, k + 1), nid(i + 1, j, k + 1), nid(i + 1, j + 1, k + 1), nid(i, j + 1, k + 1)); e += 1
    z0 = sorted(k for k, c in nodes.items() if abs(c[2]) < 1e-9); z1 = sorted(k for k, c in nodes.items() if abs(c[2] - H) < 1e-9)
    def fmt(v): return "\n".join(", ".join(map(str, v[i:i + 12])) for i in range(0, len(v), 12))
    Ls = ["*Heading", PRE, "*Part, name=PLATE", "*Node"] + [f"{n}, {c[0]:.12g}, {c[1]:.12g}, {c[2]:.12g}" for n, c in nodes.items()]
    Ls += ["*Element, type=C3D8R, elset=HOST"] + [f"{e}, " + ", ".join(map(str, c)) for e, c in el.items()]
    Ls += ["*Solid Section, elset=HOST, material=MATRIX", ",", "*End Part", "*Assembly, name=Assembly", "*Instance, name=PLATE-1, part=PLATE", "*End Instance",
           "*Nset, nset=LEFT, instance=PLATE-1", fmt(z0), "*Nset, nset=RIGHT, instance=PLATE-1", fmt(z1), f"*Nset, nset=ORIGIN, instance=PLATE-1\n{z0[0]}", "*End Assembly"]
    return "\n".join(Ls) + "\n", nodes, el, H
txt, cn, ce, H = cyl_source(False)
fibers, radii = curved_layup.concentric_shell_fibers(2.0, 3.0, H, 0.2, gap=0.0, count=32)
tmp = MESH / "cyl_src.inp"; tmp.write_text(txt)
writers.append_fibers_to_deck(txt, MESH / "cyl_out.inp", fibers, "truss", 0.2)
ctext, _ = relocate((MESH / "cyl_out.inp").read_text(), fiber_material="FIBER")
ctext += "\n".join(materials("FIBER", True) + step_block(["*Boundary", "LEFT, 3, 3", "ORIGIN, 1, 2", "*Boundary, amplitude=RAMP", "RIGHT, 3, 3, 0.001"], T=1e-5))
deliver("cyl_reloc", ctext)

# symmetry BC forms
def sym_case(tag, bc_line, part_nsets=True):
    p = OUT / f"{tag}_src.inp"
    nn, ee = hex_plate_deck(p, 4, 4, 2, *L)
    x0 = ",".join(str(k) for k, c in nn.items() if abs(c[0]) < 1e-12); y0 = ",".join(str(k) for k, c in nn.items() if abs(c[1]) < 1e-12)
    left = sorted(k for k, c in nn.items() if abs(c[0]) < 1e-12)
    right = sorted(k for k, c in nn.items() if abs(c[0] - 2) < 1e-12)
    pe = "*Nset, nset=XSYM\n" + x0 + "\n*Nset, nset=YSYM\n" + y0 + "\n*Solid Section, elset=HOST, material=MATRIX\n,"
    asm = "*Nset, nset=RIGHT, instance=PLATE-1\n" + ", ".join(map(str, right))
    tail = materials("FIBER", False) + step_block(bc_line + ["*Boundary, amplitude=RAMP", "RIGHT, 1, 1, 0.001"], T=1e-5)
    hex_plate_deck(p, 4, 4, 2, *L, extra_part=pe, extra_asm=asm, tail="\n".join(tail)); add_preprint(p)
    return p
for tag, bc in [("symbare", ["*Boundary", "XSYM, 1, 1", "YSYM, 2, 2"]), ("symvalid", ["*Boundary", "PLATE-1.XSYM, 1, 1", "PLATE-1.YSYM, 2, 2"])]:
    p = sym_case(tag, bc); deliver(f"{tag}_srconly", p.read_text())
    o = run_mesher(p, MESH / tag, d=0.25); deliver(f"{tag}_asis", o.read_text())
    print(tag, "propagated sets in deck:", [l for l in o.read_text().splitlines() if l.startswith("** embmesh propagated")])

# instance transform check (translation then rotation) with a printed COORD
xf = ["*Heading", PRE, "*Part, name=P", "*Node", "1,0,0,0", "2,1,0,0", "3,1,1,0", "4,0,1,0", "5,0,0,1", "6,1,0,1", "7,1,1,1", "8,0,1,1",
      "*Element, type=C3D8R, elset=HOST", "1,1,2,3,4,5,6,7,8", "*Solid Section, elset=HOST, material=MATRIX", ",", "*End Part", "*Assembly, name=A",
      "*Instance, name=I, part=P", "10,0,0", "0,0,0,0,0,1,90", "*End Instance", "*Nset, nset=ALLN, instance=I", "1,2,3,4,5,6,7,8", "*End Assembly"]
xf += materials("FIBER", False) + ["*Step, name=S", "*Dynamic, Explicit", ", 1e-7", "*Boundary", "ALLN, 1, 3", "*Output, history, frequency=1", "*Node Output, nset=ALLN", "U1, U2, U3", "*End Step"]
deliver("xform", "\n".join(xf) + "\n")
print("made", made)
(OUT / "decks.txt").write_text("\n".join(made) + "\n")
