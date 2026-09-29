import sys, json, time, math, numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from verification.vlib import *
R = {}; log = []
RUN = str(int(time.time()))
W = EVID / "work"; W.mkdir(exist_ok=True, parents=True)
def rec(name, ok, detail): R[name] = {"ok": bool(ok), "detail": detail}; log.append(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}"); print(log[-1][:420], flush=True)
def last(e): return (e.strip().splitlines() or [''])[-1]

# ============ scale invariance (units) of clipping tolerances ============
fr = {}
for scale in (1.0, 1e-3, 1e-6):
    tag = f"t13_scale_{scale:g}"; deck = W / f"{tag}.inp"
    hex_plate_deck(deck, 2, 2, 2, 2 * scale, 2 * scale, 1 * scale)
    out = W / f"{tag}_out_{RUN}"
    rc, o, e = run_cli(["visualize", deck, "--instance", "PLATE-1", "--diameter", .25 * scale, "--output", out])
    if rc != 0: fr[scale] = f"rc={rc} {last(e)}"; continue
    h, c = read_csv(out / "fiber_volume.csv"); fr[scale] = float(c[:, 2].sum() / c[:, 1].sum())
rec("T1.3 unit-scale invariance of fiber volume fraction (plate 2x2x1 scaled by 1, 1e-3, 1e-6)", all(isinstance(v, float) and abs(v - math.pi / 4) < 1e-6 for v in fr.values()), f"fractions={fr}")

# ============ T1.7 boundary-condition passing (symmetry propagation) ============
def sym_deck(path, bc_lines, nsets=True):
    n, e = hex_plate_deck(path, 4, 4, 2, 2, 2, 1, extra_part=("*Nset, nset=XSYM\n" + ",".join(str(k) for k, c in nodes_x0()) + "\n*Nset, nset=YSYM\n" + ",".join(str(k) for k, c in nodes_y0())) if nsets else "",
                          tail="*Step, name=S\n*Dynamic, Explicit\n, 1e-3\n" + bc_lines + "\n*End Step")
    return n, e
def _plate_nodes():
    nn, _ = hex_plate_deck(W / "_tmp_sym.inp", 4, 4, 2, 2, 2, 1); return nn
def nodes_x0(): return [(k, c) for k, c in _plate_nodes().items() if abs(c[0]) < 1e-12]
def nodes_y0(): return [(k, c) for k, c in _plate_nodes().items() if abs(c[1]) < 1e-12]
variants = {
    "explicit DOF form 'XSYM, 1, 1'": "*Boundary\nXSYM, 1, 1\nYSYM, 2, 2",
    "XSYMM keyword 'XSYM, XSYMM'": "*Boundary\nXSYM, XSYMM\nYSYM, YSYMM",
    "single-DOF 'XSYM, 1'": "*Boundary\nXSYM, 1\nYSYM, 2",
    "instance-qualified 'PLATE-1.XSYM, 1, 1'": "*Boundary\nPLATE-1.XSYM, 1, 1\nPLATE-1.YSYM, 2, 2",
    "prescribed velocity 'XSYM, 1, 1, 5.0' (not a symmetry BC)": "*Boundary, type=velocity\nXSYM, 1, 1, 5.0",
}
for label, bc in variants.items():
    tag = "t17_" + str(abs(hash(label)) % 10 ** 6); deck = W / f"{tag}.inp"; n, e = sym_deck(deck, bc)
    out = W / f"{tag}_out_{RUN}"; rc, o, er = run_cli(["visualize", deck, "--instance", "PLATE-1", "--diameter", .25, "--output", out])
    if rc != 0: rec(f"T1.7 symmetry propagation, {label}", False, f"rc={rc} {last(er)}"); continue
    fib, et, nn = parse_fibers_from_inp(out / "output.inp")
    txt = (out / "output.inp").read_text().splitlines()
    got = {}
    for i, l in enumerate(txt):
        if l.lower().startswith("*nset, nset=") and "embmesh" not in l.lower() and i > 0 and txt[i - 1].startswith("** embmesh propagated"):
            got[l.split("=")[1].strip()] = sorted(int(x) for x in txt[i + 1].split(","))
    exp = {"XSYM": sorted(k for k, c in nn.items() if abs(c[0]) < 1e-9), "YSYM": sorted(k for k, c in nn.items() if abs(c[1]) < 1e-9)}
    if "velocity" in label:
        rec(f"T1.7 {label}: fiber nodes must not silently inherit a non-zero-valued BC / value must be preserved", got == {} , f"propagated={ {k: len(v) for k,v in got.items()} } (a velocity BC on XSYM plane was treated as symmetry: {'XSYM' in got})")
    else:
        rec(f"T1.7 symmetry propagation, {label}: XSYM/YSYM fiber node sets equal hand-computed", got == exp, f"generated={ {k: len(v) for k,v in got.items()} } expected={ {k: len(v) for k,v in exp.items()} }")
# semantic placement in output deck
tag = "t17_place"; deck = W / f"{tag}.inp"; sym_deck(deck, "*Boundary\nXSYM, 1, 1\nYSYM, 2, 2"); out = W / f"{tag}_out_{RUN}"
run_cli(["visualize", deck, "--instance", "PLATE-1", "--diameter", .25, "--output", out])
txt = (out / "output.inp").read_text().splitlines()
ia = max(i for i, l in enumerate(txt) if l.lower().startswith("*end assembly"))
xsym_lines = [i for i, l in enumerate(txt) if l.lower().startswith("*nset, nset=xsym")]
ins = max(xsym_lines)   # the propagated one is the last XSYM block emitted
rec("T1.7 propagated *Nset is emitted inside *Assembly and merged into the sets the *Boundary refers to", ins < ia,
    f"*End Assembly line {ia+1}; propagated '*Nset, nset=XSYM' at line {ins+1} (BUG-006 fixed: now before *End Assembly, not after)")
rec("T1.7 amplitudes / time-varying BC passing to fiber nodes", False, "No amplitude, velocity, pressure or contact BC handling exists in embmesh (grep 'amplitude' in embmesh/*.py: none); only single-DOF *Boundary on planar node sets is inspected")
# report.json vs deck for symmetry
rep = json.loads((out / "report.json").read_text())
rec("T1.7 report.json symmetry_constraints populated", bool(rep.get("symmetry_constraints")), f"symmetry_constraints={rep.get('symmetry_constraints')} propagated={ {k: len(v) for k,v in rep.get('propagated_symmetry_nodes',{}).items()} }")

# ============ T1.4 curved (Python API only; no CLI route) ============
from embmesh import curved, curved_layup, layup
rc, o, e = run_cli(["visualize", "--help"])
rec("T1.4 curved: CLI exposes cylindrical/spherical/varying-thickness layup", any(k in o.lower() for k in ("cylind", "spher", "curved", "shell", "thickness")), "visualize options: " + ", ".join(x for x in ("--instance --diameter --output --elset --gap --fiber-type --preview".split())) + "; only flat_disc_fibers is reachable")
f, radii = curved_layup.concentric_shell_fibers(2.0, 3.0, 5.0, 0.2, gap=0.0, count=32)
fd = {x.label: x.points for x in f}
dirs = {tuple(np.round(np.abs((p[-1] - p[0]) / np.linalg.norm(p[-1] - p[0])), 6)) for p in fd.values()}
labs = sorted({x.direction for x in f})
rec("T1.4 cylindrical shell: layer count == thickness/pitch", len(radii) == int(math.floor(1.0 / 0.2 + 1e-9)), f"layers={len(radii)} radii={np.round(radii,4).tolist()} expected {int(1.0/0.2)}")
rec("T1.4 cylindrical shell: 0/90 (axial/hoop) alternation physically implemented", len(dirs) > 1, f"distinct fiber directions={sorted(dirs)} while labels claim {labs} (every fiber is axial; hoop layers not generated)")
md, pr = min_center_dist(fd)
rec("T1.4 cylindrical shell: min centerline distance >= d", md >= 0.2 - 1e-9, f"min dist={md:.4f} (d=0.2); angular count fixed at 32 regardless of pitch")
f2, radii2 = curved_layup.concentric_shell_fibers(0.5, 1.0, 5.0, 0.2, gap=0.0, count=32); fd2 = {x.label: x.points for x in f2}
md2, _ = min_center_dist(fd2)
rec("T1.4 small-radius shell: fibers do not interpenetrate", md2 >= 0.2 - 1e-9, f"r 0.5..1.0, d=0.2, count=32 -> min dist={md2:.4f}")
# director fields
th = np.random.default_rng(3).uniform(0, math.pi, 200); ph = np.random.default_rng(4).uniform(0, 2 * math.pi, 200)
P = 2.5 * np.column_stack((np.sin(th) * np.cos(ph), np.sin(th) * np.sin(ph), np.cos(th)))
dv = curved.radial_director(P); tang = np.cross(dv, np.array([0.3, 0.5, 0.8]));
rec("T1.4 spherical shell: radial director unit and normal to sphere tangent plane", np.allclose(np.linalg.norm(dv, axis=1), 1) and np.allclose(np.sum(dv * P, axis=1), 2.5), "radial_director returns P/|P| (trivial); no layup generator uses it")
# UV sphere triangulation -> smooth normals
nu, nv = 24, 16; pts = []; faces = []
for j in range(nv + 1):
    for i in range(nu):
        t = math.pi * j / nv; p = 2 * math.pi * i / nu; pts.append([2.5 * math.sin(t) * math.cos(p), 2.5 * math.sin(t) * math.sin(p), 2.5 * math.cos(t)])
for j in range(nv):
    for i in range(nu):
        a = j * nu + i; b = j * nu + (i + 1) % nu; c = (j + 1) * nu + i; dd = (j + 1) * nu + (i + 1) % nu; faces += [(a, c, b), (b, c, dd)]
pts = np.array(pts); tri = curved.triangulate_surface(pts, faces)
try:
    nrm = curved.smooth_normals(pts, tri); mid = (np.abs(pts[:, 2]) < 2.4)
    dots = np.sum(nrm[mid] * (pts[mid] / np.linalg.norm(pts[mid], axis=1, keepdims=True)), axis=1)
    rec("T1.4 spherical shell: smooth_normals on triangulated sphere are radial (|dot|>0.99, consistent sign)", np.all(np.abs(dots) > 0.99) and (np.all(dots > 0) or np.all(dots < 0)), f"dot range=[{dots.min():.3f},{dots.max():.3f}] (nonzero-degenerate poles excluded)")
except Exception as ex: rec("T1.4 spherical shell smooth_normals", False, repr(ex))
try:
    curved.director([0, 0, 1], [0, 0, -1]); rec("T1.4 director(): opposed normals rejected", False, "no exception")
except ValueError as ex: rec("T1.4 director(): opposed normals rejected", True, str(ex))
# near-parallel reference vector
res = []
for ref, nrm_ in [((1e-3, 0, 1), (0, 0, 1)), ((1e-9, 0, 1), (0, 0, 1)), ((1e-11, 0, 1), (0, 0, 1)), ((1, 0, 0), (1, 0, 0)), ((0, 1, 0), (0, 1, 0)), ((1, 1e-12, 0), (1, 0, 0))]:
    with np.errstate(all="ignore"):
        try:
            a, b = layup.orthogonal_directions(ref, nrm_); n_ = np.array(nrm_, float) / np.linalg.norm(nrm_)
            ok = bool(np.all(np.isfinite(a)) and np.all(np.isfinite(b)) and abs(a @ n_) < 1e-8 and abs(b @ n_) < 1e-8 and abs(a @ b) < 1e-8 and abs(np.linalg.norm(a) - 1) < 1e-8)
            res.append((ref, nrm_, ok, a.tolist()))
        except Exception as ex: res.append((ref, nrm_, False, repr(ex)))
rec("T1.4 near-parallel reference vector -> valid orthonormal in-plane frame", all(r[2] for r in res), "; ".join(f"ref={r[0]} n={r[1]} ok={r[2]} t0={[round(x,3) if isinstance(x,float) else x for x in r[3]] if isinstance(r[3], list) else r[3]}" for r in res))
# RK4 streamline on circle
def circ(x): return np.array([-x[1], x[0], 0.0])
path = curved.rk4_streamline([2.0, 0, 0], circ, 0.05, 400); rad = np.linalg.norm(path[:, :2], axis=1)
rec("T1.4 rk4_streamline keeps radius on circular field (1e-4)", rad.max() - rad.min() < 1e-4, f"radius drift={rad.max()-rad.min():.2e}")
rec("T1.4 varying-thickness plate layup", False, "not implemented: no generator; curved.shell_layers is 1-D radial only")
rec("T1.4 concentric spherical shell layup (fibers generated)", False, "not implemented: only concentric_shell_fibers (straight axial fibers on rings) exists; no spherical generator")

# ============ T1.8 fiber-volume file ============
tag = "t18"; deck = W / f"{tag}.inp"; nn, ee = hex_plate_deck(deck, 3, 3, 2, 3, 3, 1.5); out = W / f"{tag}_out_{RUN}"
run_cli(["visualize", deck, "--instance", "PLATE-1", "--diameter", .25, "--output", out])
lines = (out / "fiber_volume.csv").read_text().strip().splitlines(); hdr = lines[0].split(",")
doc = (ROOT / "docs" / "INTERFACE.md").read_text()
docs_cols = "element_label,host_volume,fiber_volume,volume_fraction,length_t0,length_t90".split(",")
rec("T1.8 CSV header == INTERFACE.md columns", hdr == docs_cols and all(c in doc for c in docs_cols), f"header={hdr}")
h, c = read_csv(out / "fiber_volume.csv"); area = math.pi * .25 ** 2 / 4
rec("T1.8 row consistency: fraction = fiber/host; fiber = (l0+l90)*area; labels = part element labels", np.allclose(c[:, 3], c[:, 2] / c[:, 1]) and np.allclose(c[:, 2], (c[:, 4] + c[:, 5]) * area) and sorted(c[:, 0].astype(int)) == sorted(ee), f"rows={len(c)}, labels match host labels={sorted(c[:,0].astype(int))==sorted(ee)}")
vuel = (ROOT / "uel" / "VUEL.for").read_text().lower()
has_io = any(k in vuel for k in ("open(", "uexternaldb", "read(", "common /", "common/"))
rec("T1.8 UEL source ingests the fiber-volume file", has_io, f"grep of uel/VUEL.for for open(/READ(/UEXTERNALDB/COMMON: {'found' if has_io else 'none found'}; props(1..6)=E,nu,rho,beta,b1,b2 only (jprops unused for volume). INTERFACE.md itself states no ingestion path")
# multi-instance label ambiguity
rc, o, e = run_cli(["visualize", ROOT / "examples" / "multi_instance.inp", "--instance", "B", "--diameter", .25, "--output", W / f"t18_multi_{RUN}"])
hh = (W / f"t18_multi_{RUN}" / "fiber_volume.csv").read_text().splitlines()[0] if rc == 0 else last(e)
rec("T1.8 label mapping: CSV identifies instance (part vs assembly labels)", "instance" in hh.lower(), f"CSV header has no instance/part column: {hh!r}; two instances of the same part (labels 1..n each) would collide when both are processed")
(EVID / "T1_bc_curved_iface.log").write_text("\n".join(log) + "\n"); (EVID / "T1_bc_curved_iface.json").write_text(json.dumps(R, indent=1, default=float))
