import sys, json, time, math, numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from verification.vlib import *
R = {}; log = []
RUN = str(int(time.time()))
W = EVID / "work"; W.mkdir(exist_ok=True, parents=True)
def rec(name, ok, detail): R[name] = {"ok": bool(ok), "detail": detail}; log.append(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}"); print(log[-1][:400], flush=True)
def mesh(tag, nx, ny, nz, L, d, gap=0.0, ftype="truss", extra=(), **kw):
    deck = W / f"{tag}.inp"; out = W / f"{tag}_out_{RUN}"
    nodes, elems = hex_plate_deck(deck, nx, ny, nz, *L, **kw)
    args = ["visualize", deck, "--instance", "PLATE-1", "--diameter", d, "--gap", gap, "--fiber-type", ftype, "--output", out, *extra]
    t = time.time(); rc, o, e = run_cli(args); dt = time.time() - t
    return dict(deck=deck, out=out, rc=rc, err=e, dt=dt, nodes=nodes, elems=elems)

# ================= T1.3 fiber volume =================
def check_volume(tag, nx, ny, nz, L, d, gap=0.0, perturb=None):
    m = mesh(tag, nx, ny, nz, L, d, gap)
    if m["rc"] != 0: rec(f"T1.3 {tag}", False, f"rc={m['rc']} {m['err'].strip().splitlines()[-1] if m['err'].strip() else ''}"); return None
    fib, et, _ = parse_fibers_from_inp(m["out"] / "output.inp")
    hdr, csv = read_csv(m["out"] / "fiber_volume.csv"); area = math.pi * d * d / 4
    totlen = sum(np.linalg.norm(p[-1] - p[0]) for p in fib.values())
    ftot = csv[:, 2].sum(); host_tot = csv[:, 1].sum(); Vplate = L[0] * L[1] * L[2]
    rel = abs(ftot - totlen * area) / (totlen * area)
    # independent per-host centerline lengths (axis-aligned hosts -> slab clip)
    keys = sorted(m["elems"]); ind = np.zeros(len(keys))
    for r_i, k in enumerate(keys):
        P = np.array([m["nodes"][n] for n in m["elems"][k]]); lo, hi = P.min(0), P.max(0)
        ind[r_i] = sum(clip_len_box(f[0], f[-1], lo, hi) for f in fib.values())
    per_host_err = np.max(np.abs(ind * area - csv[:, 2])) / max(area * ind.max(), 1e-30)
    # Monte Carlo bulk fraction of cylinders in plate
    rng = np.random.default_rng(1); N = 400000
    X = rng.random((N, 3)) * np.array(L)
    A = np.array([f[0] for f in fib.values()]); B = np.array([f[-1] for f in fib.values()])
    inside = np.zeros(N, bool)
    for a, b in zip(A, B):
        ab = b - a; t = np.clip(((X - a) @ ab) / (ab @ ab), 0, 1); dist = np.linalg.norm(X - (a + t[:, None] * ab), axis=1); inside |= dist <= d / 2
    mc = inside.mean(); mc_se = math.sqrt(mc * (1 - mc) / N)
    r = dict(nfib=len(fib), totlen=totlen, csv_total=ftot, expected=totlen * area, rel=rel, host_sum=host_tot, plate_vol=Vplate,
             per_host_err=per_host_err, mc_bulk=mc, mc_se=mc_se, csv_bulk=ftot / host_tot, ind_total=ind.sum() * area)
    rec(f"T1.3 {tag}: total fiber volume == total length*pi d^2/4 (1e-6)", rel < 1e-6,
        f"csv_total={ftot:.9g} length*area={totlen*area:.9g} rel={rel:.2e}; independent-clip total={ind.sum()*area:.9g}; per-host max err={per_host_err:.2e}")
    rec(f"T1.3 {tag}: bulk fraction ~ pi/4 within 2% (MC cylinders)", abs(mc - math.pi / 4) / (math.pi / 4) < 0.02 and abs(ftot / Vplate - math.pi / 4) / (math.pi / 4) < 0.02,
        f"MC={mc:.4f}+-{mc_se:.4f} csv fiber_vol/plate_vol={ftot/Vplate:.4f} (pi/4={math.pi/4:.4f}); host_volume sum={host_tot:.6g} vs plate {Vplate:.6g}")
    rec(f"T1.3 {tag}: per-host volumes match independent clipping", per_host_err < 1e-6, f"max rel diff {per_host_err:.2e}")
    return r

check_volume("t13_flat_a", 4, 4, 2, (2, 2, 1), 0.25)
check_volume("t13_flat_b", 3, 3, 3, (3, 3, 1.5), 0.3)
check_volume("t13_cube_flat_a", 2, 2, 2, (1, 1, 1), 0.25)
check_volume("t13_cube_3", 3, 3, 3, (3, 3, 3), 0.3)   # cube: thickness axis is ambiguous
# fibers exactly on inter-element faces (d=0.5, gap=0.5, 0.5 element size)
r = check_volume("t13_onface", 4, 4, 2, (2, 2, 1), 0.5, gap=0.5)

# skewed mesh: perturb interior nodes; independent clip via inverse mapping
def skew_case():
    tag = "t13_skew"; deck = W / f"{tag}.inp"
    nodes, elems = hex_plate_deck(deck, 3, 3, 2, 3, 3, 2)
    rng = np.random.default_rng(7); txt = deck.read_text().splitlines(); outl = []; sec = None; new = {}
    for ln in txt:
        if ln.startswith("*"): sec = ln.lower(); outl.append(ln); continue
        if sec and sec.startswith("*node"):
            v = ln.split(","); n = int(v[0]); c = np.array([float(x) for x in v[1:4]])
            interior = (0 < c[0] < 3) and (0 < c[1] < 3) and (0 < c[2] < 2)
            if interior: c = c + rng.uniform(-0.18, 0.18, 3)
            c[0] += 0.2 * c[2]                # shear
            new[n] = c; outl.append(f"{n}, {c[0]:.12g}, {c[1]:.12g}, {c[2]:.12g}")
        else: outl.append(ln)
    deck.write_text("\n".join(outl) + "\n")
    out = W / f"{tag}_out_{RUN}"; d = 0.2
    rc, o, e = run_cli(["visualize", deck, "--instance", "PLATE-1", "--diameter", d, "--output", out])
    if rc != 0: rec("T1.3 skew", False, f"rc={rc} {e.strip().splitlines()[-1]}"); return
    fib, et, _ = parse_fibers_from_inp(out / "output.inp"); hdr, csv = read_csv(out / "fiber_volume.csv"); area = math.pi * d * d / 4
    keys = sorted(elems); errs = []; ind = []
    for i, k in enumerate(keys):
        P = np.array([new[n] for n in elems[k]]); L_e = 0.0
        for f in fib.values():
            if np.all(f.max(0) < P.min(0) - 1e-9) or np.any(f.min(0) > P.max(0) + 1e-9): continue
            L_e += clip_len_hex_own(f[0], f[-1], P, 40001)
        ind.append(L_e * area)
        hv = hex_volume_own(P); errs.append((csv[i, 1] - hv) / hv)
    ind = np.array(ind); rel = np.abs(ind - csv[:, 2]) / np.maximum(ind, 1e-12)
    tot_ind = ind.sum(); tot_csv = csv[:, 2].sum(); totlen = sum(np.linalg.norm(f[-1] - f[0]) for f in fib.values())
    rec("T1.3 skewed/sheared mesh: host volumes vs own Gauss volume (1e-9)", max(abs(np.array(errs))) < 1e-9, f"max rel host volume err={max(abs(np.array(errs))):.2e}")
    rec("T1.3 skewed/sheared mesh: per-host fiber volume vs independent inverse-map clip (2e-3)", rel.max() < 2e-3,
        f"max per-host rel diff={rel.max():.3e}; total csv={tot_csv:.6g} independent={tot_ind:.6g} total(length*area)={totlen*area:.6g} rel(total vs length*area)={(tot_csv-totlen*area)/(totlen*area):.3e}")
skew_case()

# L-shaped (non-rectangular) plate: fibers span the bounding box
m = mesh("t13_Lshape", 4, 4, 2, (2, 2, 1), 0.25, skip_elems={4, 8, 12, 16, 3, 7, 11, 15, 20, 24, 28, 32, 19, 23, 27, 31})  # remove x>=1 & y>=1... (arbitrary hole region)
if m["rc"] == 0:
    fib, et, nn = parse_fibers_from_inp(m["out"] / "output.inp"); hdr, csv = read_csv(m["out"] / "fiber_volume.csv"); area = math.pi * .25 ** 2 / 4
    totlen = sum(np.linalg.norm(f[-1] - f[0]) for f in fib.values()); rep = json.loads((m["out"] / "report.json").read_text())
    # own point-in-any-host test for every fiber endpoint (axis-aligned hosts)
    boxes = [(np.array([m["nodes"][n] for n in c]).min(0), np.array([m["nodes"][n] for n in c]).max(0)) for c in m["elems"].values()]
    def inhost(p): return any(np.all(p >= lo - 1e-9) and np.all(p <= hi + 1e-9) for lo, hi in boxes)
    out_nodes = sum(1 for f in fib.values() for p in (f[0], f[-1]) if not inhost(p))
    rec("T1.3 non-rectangular plate (elements removed): all fiber end nodes inside a host", out_nodes == 0,
        f"{out_nodes} of {2*len(fib)} fiber end nodes lie in no host element; length outside hosts = {(totlen*area-csv[:,2].sum())/(totlen*area)*100:.1f}% of generated fiber volume; report.json embedded_endpoints_inside={rep['embedded_endpoints_inside']} of {rep['embedded_endpoint_total']}")
else: rec("T1.3 non-rectangular plate", False, f"rc={m['rc']}")

# ================= T1.4 layup =================
def layup(tag, L, d, gap=0.0, n_xyz=(2, 2, 2), **kw):
    m = mesh(tag, *n_xyz, L, d, gap, **kw)
    if m["rc"] != 0: return m, None
    fib, et, _ = parse_fibers_from_inp(m["out"] / "output.inp")
    return m, fib
def layers(fib, axis):
    z = np.array([f.mean(0)[axis] for f in fib.values()]); zs = np.unique(np.round(z, 9)); return zs
for tag, L, d, gap in [("t14_a", (1, 1, 1), .25, 0), ("t14_b", (1, 1, 1), .3, 0), ("t14_c", (1, 1, 1), .1, 0), ("t14_d", (2, 2, 1), .2, .05), ("t14_e", (1.1, 1.1, 0.7), .4, 0), ("t14_f", (3, 2, 1.2), .2, 0)]:
    m, fib = layup(tag, L, d, gap)
    if fib is None: rec(f"T1.4 {tag} d={d} gap={gap}", False, f"rc={m['rc']} {m['err'].strip().splitlines()[-1]}"); continue
    pitch = d + gap
    # thickness axis = the axis along which layers are stacked (each layer is planar): detect as axis with unique-levels count = Lz/pitch
    zs = layers(fib, 2)
    exp_n = int(math.floor(L[2] / pitch + 1e-9))
    rec(f"T1.4 {tag} layer count (t={L[2]}, pitch={pitch:g})", len(zs) == exp_n, f"layers found={len(zs)} expected floor(t/pitch)={exp_n} (t/pitch={L[2]/pitch:.6f})")
    # alternation
    dirs = {}
    for f in fib.values():
        dv = f[-1] - f[0]; dv /= np.linalg.norm(dv); dirs.setdefault(round(f.mean(0)[2], 9), set()).add(tuple(np.round(np.abs(dv), 6)))
    seq = [dirs[z] for z in sorted(dirs)]; alt = all(len(s) == 1 for s in seq) and all(seq[i] != seq[i + 1] for i in range(len(seq) - 1)) and all(a in ((1., 0., 0.), (0., 1., 0.)) for s in seq for a in s)
    rec(f"T1.4 {tag} strict 0/90 alternation layer to layer", alt, f"direction sets per layer={[sorted(s) for s in seq]}")
    md, pr = min_center_dist(fib)
    rec(f"T1.4 {tag} min centerline distance >= d (zero gap) / >= pitch", md >= d * (1 - 1e-9) and md >= pitch * (1 - 1e-9), f"min dist={md:.9g} d={d} pitch={pitch} pair={pr}")
    # fibers stay inside plate (cylinder envelope)
    lo = np.array([f.min(0) for f in fib.values()]).min(0); hi = np.array([f.max(0) for f in fib.values()]).max(0)
    worst = 0.0
    for f in fib.values():
        dv = f[-1] - f[0]; ax = int(np.argmax(np.abs(dv))); other = [a for a in range(3) if a != ax]
        for a in other:
            c = f.mean(0)[a]; worst = max(worst, d / 2 - (c - 0.0), d / 2 - (L[a] - c))
    rec(f"T1.4 {tag} fiber cylinders inside plate envelope (centerline >= d/2 from faces)", worst <= 1e-9, f"max protrusion of any fiber cylinder beyond plate faces = {max(worst,0):.4g} (d/2={d/2:g})")

# thickness axis / orientation robustness
for tag, L in [("t14_thickY", (2, 0.5, 2)), ("t14_thickX", (0.5, 2, 2)), ("t14_cube", (1, 1, 1))]:
    m, fib = layup(tag, L, .1)
    if fib is None: rec(f"T1.4 {tag} thickness axis {L}", False, f"rc={m['rc']} {m['err'].strip().splitlines()[-1]}"); continue
    ax = int(np.argmin(L))
    lv = layers(fib, ax); exp = int(math.floor(min(L) / .1 + 1e-9))
    rec(f"T1.4 {tag} plate {L}: layers stack along thin axis, count {exp}", len(lv) == exp and len(layers(fib, (ax + 1) % 3)) != exp or (len(lv) == exp and tag == "t14_cube"),
        f"levels along thin axis {ax}: {len(lv)}; per-axis level counts={[len(layers(fib,a)) for a in range(3)]}")
# label collisions / offsets
nn, ee = hex_plate_deck(W / "t14_bigid.inp", 1, 1, 1)
txt = (W / "t14_bigid.inp").read_text().replace("\n8, ", "\n250000, ", 1)
(W / "t14_bigid.inp").write_text(txt)
rc, o, e = run_cli(["visualize", W / "t14_bigid.inp", "--instance", "PLATE-1", "--diameter", ".25", "--output", W / f"t14_bigid_out_{RUN}"])
rec("T1.4 label collision: deck with node labels >100000 processed (offset configurable)", rc == 0, f"rc={rc} last={(e.strip().splitlines() or [''])[-1]}; CLI has no --node-offset option (hard-coded 100000)")
m = mesh("t14_twice", 1, 1, 1, (1, 1, 1), .25)
rc, o, e = run_cli(["visualize", m["out"] / "output.inp", "--instance", "PLATE-1", "--diameter", ".25", "--output", W / f"t14_twice2_{RUN}"])
rec("T1.4 label collision: second pass on an already-fibered deck (e.g. 2nd instance) works", rc == 0, f"rc={rc} last={(e.strip().splitlines() or [''])[-1]}")

# ================= T1.5 truss / beam toggle =================
for ft in ("truss", "beam"):
    m = mesh(f"t15_{ft}", 2, 2, 2, (1, 1, 1), .25, ftype=ft)
    txt = (m["out"] / "output.inp").read_text().splitlines()
    kws = [l for l in txt if l.lower().startswith(("*element, type", "*solid section", "*beam section"))]
    idx = [i for i, l in enumerate(txt) if l.lower().startswith(("*solid section", "*beam section"))][0]
    (EVID / f"T1_5_{ft}_keywords.txt").write_text("\n".join(txt[idx - 3 if False else idx:idx + 4]) + "\n")
    if ft == "truss":
        ok = any("type=T3D2" in l for l in kws) and any(l.lower().startswith("*solid section") for l in kws) and abs(float(txt[idx + 1]) - math.pi * .25 ** 2 / 4) < 1e-12
        rec("T1.5 truss: T3D2 + *Solid Section with area pi d^2/4", ok, f"keywords={kws}; area line={txt[idx+1]}")
    else:
        fib, et, _ = parse_fibers_from_inp(m["out"] / "output.inp")
        sec = txt[idx]; data = txt[idx + 1]; vals = [float(x) for x in data.split(",")]
        ok1 = et == "B31" and "section=CIRC" in sec and abs(vals[0] - .125) < 1e-12
        n1 = np.array(vals[1:4]) if len(vals) >= 4 else None
        rec("T1.5 beam: B31 + *Beam Section CIRC radius d/2 and n1 present", ok1 and n1 is not None, f"type={et}; section={sec}; data line={data!r}; Abaqus expects radius on the first data line and n1 on a SECOND data line")
        bad = 0
        for f in fib.values():
            ax = (f[-1] - f[0]); ax /= np.linalg.norm(ax)
            if abs(ax @ n1 / np.linalg.norm(n1)) > 0.999 or abs(ax @ n1) > 1e-6 * 0 + 0.999: bad += 1
        nperp = sum(1 for f in fib.values() if abs(((f[-1] - f[0]) / np.linalg.norm(f[-1] - f[0])) @ n1) > 1e-6)
        rec("T1.5 beam: n1 perpendicular to EVERY beam axis (single n1 for all fibers)", nperp == 0, f"{sum(1 for f in fib.values() if abs(((f[-1]-f[0])/np.linalg.norm(f[-1]-f[0]))@n1)>0.999)} of {len(fib)} fibers have n1 parallel to axis; {nperp} not orthogonal; single n1={n1.tolist()}")
    fibsec = [l for l in txt if l.strip().lower().startswith("*elastic")]
    mat = txt[[i for i, l in enumerate(txt) if l.lower().startswith("*material, name=embmesh_fiber")][0] + 1:][:4]
    rec(f"T1.5 {ft}: fiber material is a placeholder (E=1, nu=0.3, no density)", False, f"material block={mat}; deck contains no *Density and no VUMAT hook; user must edit by hand and nothing warns them")

# ================= T1.6 visualization =================
m = mesh("t16", 4, 4, 2, (2, 2, 1), 0.25, extra=["--preview"])
rec("T1.6 --preview PNG written (python env)", (m["out"] / "preview.png").exists(), f"rc={m['rc']} err={(m['err'].strip().splitlines() or [''])[-1]}")
if m["rc"] == 0:
    pts, lines, sc = parse_vtk_polydata(m["out"] / "host_fibers.vtk")
    fib, et, _ = parse_fibers_from_inp(m["out"] / "output.inp"); hdr, csv = read_csv(m["out"] / "fiber_volume.csv")
    nh = len(m["elems"]); nf = len(fib)
    okc = len(pts) == 8 * nh + 2 * nf and len(lines) == 12 * nh + nf and len(sc) == len(lines)
    rec("T1.6 vtk counts (points/lines/cell scalars) vs data", okc, f"points={len(pts)} lines={len(lines)} scalars={len(sc)} expected points={8*nh+2*nf} lines={12*nh+nf}")
    fl = [l for l, s in zip(lines, sc) if s == -1.0]
    flen = sum(np.linalg.norm(pts[b] - pts[a]) for a, b in fl); area = math.pi * .25 ** 2 / 4
    rec("T1.6 fiber volume from vtk == csv total", abs(flen * area - csv[:, 2].sum()) / csv[:, 2].sum() < 1e-9, f"vtk length*area={flen*area:.9g} csv={csv[:,2].sum():.9g}")
    hostl = [(l, s) for l, s in zip(lines, sc) if s != -1.0]
    frac_vtk = sorted(set(round(s, 9) for l, s in hostl)); frac_csv = sorted(set(np.round(csv[:, 3], 9)))
    rec("T1.6 host scalar (volume fraction) in vtk == csv", frac_vtk == frac_csv, f"vtk={frac_vtk} csv={frac_csv}")
    # fibers inside plate & layer alternation from vtk
    fpts = np.array([pts[i] for l in fl for i in l]); inside = np.all(fpts >= -1e-9) and np.all(fpts <= np.array([2, 2, 1]) + 1e-9)
    zs = np.unique(np.round([(pts[a] + pts[b])[2] / 2 for a, b in fl], 9)); dirs = []
    for z in zs:
        s = set();
        for a, b in fl:
            if abs((pts[a] + pts[b])[2] / 2 - z) < 1e-9: s.add(int(np.argmax(np.abs(pts[b] - pts[a]))))
        dirs.append(s)
    rec("T1.6 vtk: fibers inside plate bbox, layers alternate x/y", inside and all(len(s) == 1 for s in dirs) and all(dirs[i] != dirs[i + 1] for i in range(len(dirs) - 1)), f"inside={inside} layer dirs={[sorted(s) for s in dirs]}")
    hv = sum(hex_volume_own(np.array([m['nodes'][n] for n in c])) for c in m["elems"].values())
    rec("T1.6 host volume in csv == own Gauss host volume", abs(csv[:, 1].sum() - hv) < 1e-9, f"csv={csv[:,1].sum()} own={hv}")
# scaling / performance
for tag, n3, L, d in [("t16_perf1", (10, 10, 4), (10, 10, 2), .25), ("t16_perf2", (20, 20, 4), (10, 10, 2), .25)]:
    m = mesh(tag, *n3, L, d)
    fib = parse_fibers_from_inp(m["out"] / "output.inp")[0] if m["rc"] == 0 else {}
    rec(f"T1.6 performance {tag}: {n3[0]*n3[1]*n3[2]} hosts, {len(fib)} fibers", m["dt"] < 60, f"wall={m['dt']:.1f}s rc={m['rc']}")

(EVID / "T1_volume_layup.log").write_text("\n".join(log) + "\n")
(EVID / "T1_volume_layup.json").write_text(json.dumps(R, indent=1, default=float))
