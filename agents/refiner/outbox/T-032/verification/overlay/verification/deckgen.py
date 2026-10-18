"""Deck builders for the ROAR runs (own code; mesher used as a black box via its CLI)."""
import sys, re, math, time, json, numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from verification.vlib import *

# consistent units: mm, tonne, s, MPa
MAT = dict(Em=3500.0, num=0.35, rhom=1.2e-9, Ef=230000.0, nuf=0.2, rhof=1.8e-9, sfail=3000.0)

def materials(fiber_name="FIBER", with_fiber=True, vumat=False):
    L = ["*Material, name=MATRIX", "*Density", f"{MAT['rhom']:.6g},", "*Elastic", f"{MAT['Em']:.6g}, {MAT['num']}"]
    if with_fiber:
        L += [f"*Material, name={fiber_name}", "*Density", f"{MAT['rhof']:.6g},"]
        if vumat: L += ["*Depvar, delete=1", "1", f"*User Material, constants=2", f"{MAT['Ef']:.6g}, {MAT['sfail']:.6g}"]
        else: L += ["*Elastic", f"{MAT['Ef']:.6g}, {MAT['nuf']}"]
    return L

def step_block(bcs, T=1e-4, name="S1", extra_out=(), print_nset="RIGHT", amp_smooth=True, mass_scale=None):
    L = ["*Amplitude, name=RAMP, definition=SMOOTH STEP", "0., 0., " + f"{T:.6g}, 1."]
    L += [f"*Step, name={name}", "*Dynamic, Explicit", f", {T:.6g}"]
    if mass_scale: L += [mass_scale]
    L += list(bcs)
    L += ["*Output, history, frequency=1000000", f"*Node Output, nset={print_nset}", "RF1, RF2, RF3, U1, U2, U3"]
    L += list(extra_out)
    L += ["*Output, field, number interval=5", "*Node Output", "U, RF", "*Element Output, directions=YES", "S, E", "*Output, history, time interval=%.6g" % (T / 50), "*Energy Output", "ALLIE, ALLKE, ALLWK, ALLVD, ALLAE, ETOTAL", "*End Step"]
    return L

def relocate(out_inp_text, host_inst="PLATE-1", host_elset="HOST", fiber_material=None, fiber_inst="EMBFIB-1", fiber_part="EMBFIB"):
    """Take the mesher's appended block (after '** embmesh generated fibers') and turn it into a valid
    Abaqus assembly addition. Two things the mesher's own output.inp gets wrong were found by iterating
    against real Abaqus 2024 datacheck error messages during this run (see docs/BUGS.md BUG-006):
      1. The whole block is appended after the deck's *End Assembly -- *Node/*Element are not valid there.
      2. *Solid/*Beam Section is not a valid suboption of a bare *Instance either -- Abaqus 2024 requires
         *Instance to reference an actual *Part ("Instance must refer to a part."). So the fiber
         *Node/*Element/*Solid or *Beam Section are wrapped in a new minimal *Part (inserted before
         *Assembly), which is then instanced inside *Assembly (before *End Assembly); *Embedded Element
         is instance-qualified to that new instance. Returns (new_text, info)."""
    lines = out_inp_text.splitlines()
    k = next(i for i, l in enumerate(lines) if l.startswith("** embmesh generated fibers"))
    head, blk = lines[:k], lines[k:]
    j_sec = next(i for i, l in enumerate(blk) if l.lower().startswith(("*solid section", "*beam section")))
    nodes_elems = blk[:j_sec]                                    # *Node, nset=... / *Element, type=...
    rest = blk[j_sec:]
    j_emb = next(i for i, l in enumerate(rest) if l.lower().startswith("*embedded element"))
    sec_mat = rest[:j_emb]                                       # *Solid/Beam Section, then its data line(s), then *Material block
    emb = rest[j_emb:]
    sym = []
    for i, l in enumerate(emb):
        if l.startswith("** embmesh propagated"): sym = emb[i:]; emb = emb[:i]; break
    jm = next(i for i, l in enumerate(sec_mat) if l.lower().startswith("*material, name=embmesh_fiber"))
    section_lines, material_lines = sec_mat[:jm], sec_mat[jm:]   # section (+ data) must stay with the elements; *Material is always model-level
    if fiber_material:
        section_lines = [l.replace("material=EMBMESH_FIBER", f"material={fiber_material}") for l in section_lines]
        material_lines = []                                     # caller supplies the real material elsewhere in the deck
    emb[0] = f"*Embedded Element, host elset={host_inst}.{host_elset}"
    emb[1] = f"{fiber_inst}.{emb[1].strip()}"                    # instance-qualify EMBMESH_FIBERS
    fib_part = [f"*Part, name={fiber_part}"] + nodes_elems + section_lines + ["*End Part"]
    fib_instance = [f"*Instance, name={fiber_inst}, part={fiber_part}", "*End Instance"]
    ip = min(i for i, l in enumerate(head) if l.lower().startswith("*assembly"))
    ia = max(i for i, l in enumerate(head) if l.lower().startswith("*end assembly"))
    new = head[:ip] + fib_part + head[ip:ia] + fib_instance + emb + head[ia:] + material_lines
    return "\n".join(new) + "\n", dict(sym=sym, fiber_material=fiber_material or "EMBMESH_FIBER")

def run_mesher(src_deck, out_dir, inst="PLATE-1", d=0.25, gap=0.0, ftype="truss", extra=()):
    rc, o, e = run_cli(["visualize", src_deck, "--instance", inst, "--diameter", d, "--gap", gap, "--fiber-type", ftype, "--output", out_dir, *extra])
    if rc != 0: raise RuntimeError(f"mesher failed rc={rc}: {e.strip().splitlines()[-1] if e.strip() else ''}")
    return Path(out_dir) / "output.inp"

def source_deck(path, nx, ny, nz, L, tail_lines=(), part_extra="", asm_extra="", **kw):
    pe = "*Solid Section, elset=HOST, material=MATRIX\n," + ("\n" + part_extra if part_extra else "")
    return hex_plate_deck(path, nx, ny, nz, *L, extra_part=pe, extra_asm=asm_extra, tail="\n".join(tail_lines), **kw)
