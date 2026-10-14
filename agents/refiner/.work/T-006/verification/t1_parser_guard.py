import sys, json, shutil, numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from verification.vlib import *
from embmesh.parser import parse_deck
R = {}
import time; RUN = str(int(time.time()))
W = EVID / "work"; W.mkdir(exist_ok=True, parents=True)
log = []
def rec(name, ok, detail): R[name] = {"ok": bool(ok), "detail": detail}; log.append(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")
def last(e): return e.strip().splitlines()[-1] if e.strip() else ''

# ---- T1.1 hand-checked instance transform ----
unit = "*Part, name=P\n*Node\n1,0,0,0\n2,1,0,0\n3,1,1,0\n4,0,1,0\n5,0,0,1\n6,1,0,1\n7,1,1,1\n8,0,1,1\n*Element, type=C3D8\n1,1,2,3,4,5,6,7,8\n*Nset, nset=N1\n1,2\n*Elset, elset=E1\n1\n*End Part\n*Assembly, name=A\n"
def inst(lines): return unit + "*Instance, name=I, part=P\n" + lines + "\n*End Instance\n*End Assembly\n"
p = W / "t11_a.inp"
# Abaqus convention: line 1 = translation, line 2 = rotation (a,b,c, a2,b2,c2, angle). Translated THEN rotated.
p.write_text(inst("10,0,0\n0,0,0,0,0,1,90"))
d = parse_deck(p); n1 = d.instance_nodes("I")[2]
exp_abq = np.array([0., 11., 0.]); exp_alt = np.array([10., 1., 0.])
rec("T1.1a translate-then-rotate node 2 (hand calc)", np.allclose(n1, exp_abq, atol=1e-9),
    f"mesher={n1.tolist()} hand-calc(translate then rotate)={exp_abq.tolist()}; rotate-then-translate would give {exp_alt.tolist()}")
p.write_text(inst("10,20,30")); d = parse_deck(p); n = d.instance_nodes("I")[7]
rec("T1.1b translation only node 7", np.allclose(n, [11, 21, 31]), f"mesher={n.tolist()} expected=[11,21,31]")
p.write_text(inst("0,0,0\n0,0,0,1,0,0,90")); d = parse_deck(p); n = d.instance_nodes("I")[4]
rec("T1.1c rotation about x, node 4 (0,1,0)->(0,0,1)", np.allclose(n, [0, 0, 1], atol=1e-9), f"mesher={n.tolist()}")
p.write_text(inst("0,0,0\n1,1,0,1,1,1,90")); d = parse_deck(p); n = d.instance_nodes("I")[1]
rec("T1.1d rotation about off-origin axis", np.allclose(n, [2, 0, 0], atol=1e-9), f"mesher={n.tolist()} expected=[2,0,0]")
d = parse_deck(ROOT / "examples" / "multi_instance.inp"); nb = d.instance_nodes("B")[2]
rec("T1.1e examples/multi_instance.inp uses Abaqus line order (translation first, rotation second)", False,
    f"example lists the 7-value rotation line BEFORE the 3-value translation line; mesher tolerates it and returns node2 of B = {nb.tolist()}; Abaqus would read line 1 as the translation and reject/misread it")
nodes, elems = hex_plate_deck(W / "t11_plate.inp", 4, 3, 2, 4, 3, 2, extra_part="*Nset, nset=NS, generate\n1, 10, 1\n*Elset, elset=ES, generate\n1, 12, 1")
d = parse_deck(W / "t11_plate.inp"); pt = d.parts["PLATE"]
got = (len(pt.nodes), len(pt.elements), len(pt.nsets["NS"]), len(pt.elsets["ES"]))
rec("T1.1f counts: nodes/elems/nset(generate)/elset(generate)", got == (len(nodes), len(elems), 10, 12), f"mesher={got} truth={(len(nodes), len(elems), 10, 12)}")
rc, o, e = run_cli(["visualize", W / "t11_plate.inp", "--instance", "PLATE-1", "--diameter", "0.25", "--output", W / "t11_out"])
d2 = parse_deck(W / "t11_out" / "output.inp"); p2 = d2.parts["PLATE"]
rec("T1.1g round trip: original part/instance preserved in output.inp", (len(p2.nodes), len(p2.elements)) == (len(nodes), len(elems)) and set(d2.instances) == {"PLATE-1"},
    f"rc={rc} out nodes={len(p2.nodes)} elems={len(p2.elements)} instances={list(d2.instances)}")
c20 = "*Part, name=P\n*Node\n" + "\n".join(f"{i},{i%3},{i%5},{i%7}" for i in range(1, 21)) + "\n*Element, type=C3D20R\n1, 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,\n16,17,18,19,20\n*End Part\n*Assembly, name=A\n*Instance, name=I, part=P\n*End Instance\n*End Assembly\n"
(W / "t11_c20.inp").write_text(c20); d = parse_deck(W / "t11_c20.inp"); ps = d.parts["P"]
rec("T1.1h C3D20R with continuation line -> 1 element, 20 nodes", len(ps.elements) == 1 and len(next(iter(ps.elements.values())).connectivity) == 20,
    f"mesher elements={len(ps.elements)} labels={list(ps.elements)} conn lens={[len(e.connectivity) for e in ps.elements.values()]}")
cae = unit + "*Instance, name=I, part=P\n*End Instance\n*Nset, nset=Set-1, instance=I\n1,2,3,4\n*Elset, elset=Set-2, instance=I\n1\n*End Assembly\n"
cae = cae.replace("*Assembly, name=A\n*Instance", "*Assembly, name=A\n*Instance", 1)
(W / "t11_cae.inp").write_text(cae); d = parse_deck(W / "t11_cae.inp")
rec("T1.1i assembly-level *Nset/*Elset with instance= (CAE style) captured", any("Set-1" in pt.nsets for pt in d.parts.values()),
    f"part nsets={[list(pt.nsets) for pt in d.parts.values()]}; model.Deck has no assembly-level set storage")
(W / "inc_nodes.inp").write_text("*Node\n1,0,0,0\n2,1,0,0\n3,1,1,0\n4,0,1,0\n5,0,0,1\n6,1,0,1\n7,1,1,1\n8,0,1,1\n")
(W / "t11_inc.inp").write_text("*Part, name=P\n*Include, input=inc_nodes.inp\n*Element, type=C3D8, elset=HOST\n1,1,2,3,4,5,6,7,8\n*End Part\n*Assembly, name=A\n*Instance, name=I, part=P\n*End Instance\n*End Assembly\n")
try:
    d = parse_deck(W / "t11_inc.inp"); n_inc = len(d.parts["P"].nodes)
except Exception as ex: n_inc = f"EXC {ex!r}"
rec("T1.1j *Include, input=file resolved", n_inc == 8, f"nodes read via include = {n_inc}")
rc, o, e = run_cli(["list", W / "does_not_exist.inp"])
rec("T1.1k nonexistent deck -> nonzero exit + message", rc != 0, f"rc={rc} stdout={o!r} stderr={e[-120:]!r}")
rc, o, e = run_cli(["visualize", W / "t11_plate.inp", "--instance", "PLATE-1", "--diameter", "0.25", "--elset", "host", "--output", W / "t11_case"])
hc = json.loads((W / "t11_case" / "report.json").read_text()).get("host_count")
rec("T1.1l --elset name case-insensitive (Abaqus sets are) / unknown elset rejected", rc != 0 or hc > 0, f"rc={rc} host_count={hc} fibers_written={json.loads((W / 't11_case' / 'report.json').read_text()).get('fiber_count')}")

# ---- T1.2 hex-only guard ----
def deck_with(etype, conn):
    nn = {1: (0, 0, 0), 2: (1, 0, 0), 3: (1, 1, 0), 4: (0, 1, 0), 5: (0, 0, 1), 6: (1, 0, 1), 7: (1, 1, 1), 8: (0, 1, 1)}
    return "*Part, name=P\n*Node\n" + "\n".join(f"{k},{v[0]},{v[1]},{v[2]}" for k, v in nn.items()) + f"\n*Element, type={etype}, elset=HOST\n1,{conn}\n*End Part\n*Assembly, name=A\n*Instance, name=I, part=P\n*End Instance\n*End Assembly\n"
cases = [("wedge_C3D6", "C3D6", "1,2,3,5,6,7"), ("tet_C3D4", "C3D4", "1,2,3,5"), ("tet_C3D10", "C3D10", "1,2,3,5,4,6,7,8,1,2"),
         ("shell_S4R", "S4R", "1,2,3,4"), ("shell_S4", "S4", "1,2,3,4"), ("collapsed_hex_as_wedge", "C3D8", "1,2,3,3,5,6,7,7")]
for name, et, conn in cases:
    (W / "t12.inp").write_text(deck_with(et, conn))
    for via_exe in (False, True):
        out = W / f"t12_{name}_{'exe' if via_exe else 'py'}"
        out = W / f"{out.name}_{RUN}"
        rc, o, e = run_cli(["visualize", W / "t12.inp", "--instance", "I", "--diameter", "0.2", "--output", out], exe=via_exe)
        wrote = out.exists() and any(out.iterdir())
        is_err = "HexOnlyError" in e or "unsupported host" in e
        if name.startswith("collapsed"):
            rec(f"T1.2 {name} ({'exe' if via_exe else 'py'})", rc != 0 and not wrote, f"rc={rc} wrote={wrote} last={last(e)}")
        else:
            rec(f"T1.2 {name} ({'exe' if via_exe else 'py'}): HexOnlyError, nonzero, no output", rc != 0 and is_err and not wrote,
                f"rc={rc} hexonly_msg={is_err} output_written={wrote} raw_traceback={'Traceback' in e} last={last(e)}")
mix = deck_with("C3D8", "1,2,3,4,5,6,7,8").replace("*End Part", "*Element, type=C3D4, elset=TETS\n2,1,2,3,5\n*End Part")
(W / "t12_mix.inp").write_text(mix)
rc, o, e = run_cli(["visualize", W / "t12_mix.inp", "--instance", "I", "--diameter", "0.2", "--output", W / "t12_mix_all"])
rec("T1.2 mixed hex+tet part, whole part -> error", rc != 0, f"rc={rc}")
rc, o, e = run_cli(["visualize", W / "t12_mix.inp", "--instance", "I", "--diameter", "0.2", "--elset", "HOST", "--output", W / "t12_mix_host"])
rep = json.loads((W / "t12_mix_host" / "report.json").read_text()) if (W / "t12_mix_host" / "report.json").exists() else {}
rec("T1.2 mixed part, --elset HOST (hex only) -> OK, tets excluded", rc == 0 and rep.get("host_count") == 1, f"rc={rc} host_count={rep.get('host_count')} last={last(e)}")

(EVID / "T1_parser_guard.log").write_text("\n".join(log) + "\n")
(EVID / "T1_parser_guard.json").write_text(json.dumps(R, indent=1))
print("\n".join(log))
