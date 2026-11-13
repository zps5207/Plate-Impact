"""Build the corrected-ball Valerie plywise decks: vrb_native (native C3D8R matrix) and vrb_vuel (VU1 + Stage 7 volume
correction), both with a RIGID ball of the paper's size.

Why: Meshing/Vals.inp has a ball of radius 9.525 mm (3/4 in diameter); Valerie's paper uses 3/8 in diameter
(radius 4.7625 mm), see References/Valerie's Paper.pdf and memory ball-size-error-vals-inp. Changes versus the earlier
vr_native / vr_vuel decks (build_vals_plywise.py + build_vals_rigid.py), and nothing else:
  * ball radius 4.7625 mm, new uniform O-grid hex mesh (ball_tests/ball_mesh.py, quarter sphere, pole on the impact
    axis) with elements about the size of the matrix elements (~1.2 mm in plane; set N_CELLS / N_RAD below)
  * ball centre z = R + 1.5 mm gap above the plate top face (old deck: 11 mm = 9.525 + 1.475)
  * steel density scaled up by exact-sphere-volume / faceted-mesh-volume so the rigid mass is a true 3/8 in sphere
  * impact speed 1028 m/s (paper), rigid body with reference node at the ball centre (as build_vals_rigid.py)
  * same plies, fibers, cohesive numbers, node-based ball contact, step 7e-5 s, output cadence

Usage: python verification/roar/build_vals_ballfix.py [out_dir]   (default Meshing/vals-plywise-ballfix)
Writes <out_dir>/{native,vuel}/vrb_{native,vuel}.inp plus Vals_ballfix.inp, ballfix_build_log.json.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "ball_tests"))
import ball_mesh as bm          # noqa: E402
import build_vals_plywise as bvp  # noqa: E402  (its CLI switch only reads argv[1] == "--element-deletion")

ROOT = bvp.ROOT
VALS = ROOT / "Meshing" / "Vals.inp"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "Meshing" / "vals-plywise-ballfix"

R_NEW = 0.0047625           # 3/8 in diameter
GAP = 0.0015                # 1.5 mm between the ball and the plate top face (plate top is z = 0)
CENTRE_Z = R_NEW + GAP
SPEED = 1028.0              # m/s, paper
N_CELLS, N_RAD, HC, SMOOTH = 4, 2, 0.5, 10   # ~1.19 mm elements at R = 4.7625 mm (matrix hosts ~1.22 x 1.22 x 1.27)


def fmt(v):
    return "%.9g" % v


def chunks(ids, n=16):
    return [", ".join(str(i) for i in ids[s:s + n]) for s in range(0, len(ids), n)]


def span(lines, header_re, start=0):
    """(header index, index past its data lines) of the first header at/after start."""
    for i in range(start, len(lines)):
        if re.match(header_re, lines[i]):
            j = i + 1
            while j < len(lines) and not lines[j].startswith("*"):
                j += 1
            return i, j
    raise ValueError(header_re)


def gauss_volume(pts, hexes):
    """Exact trilinear-hex volume (2x2x2 Gauss), what Abaqus integrates for C3D8 mass."""
    g = 1.0 / np.sqrt(3.0)
    corners = np.array([[-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1],
                        [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1]], float)
    vol = 0.0
    for e in hexes:
        X = pts[e]
        for s in corners * g:
            d = np.empty((8, 3))
            for a in range(8):
                c = corners[a]
                d[a] = [0.125 * c[0] * (1 + c[1] * s[1]) * (1 + c[2] * s[2]),
                        0.125 * c[1] * (1 + c[0] * s[0]) * (1 + c[2] * s[2]),
                        0.125 * c[2] * (1 + c[0] * s[0]) * (1 + c[1] * s[1])]
            vol += abs(np.linalg.det(d.T @ X))
    return vol


def make_ball():
    pts, hexes = bm.build(N_CELLS, N_RAD, HC, iters=SMOOTH)
    pts = pts * (R_NEW / bm.R)
    q = bm.quality(pts, hexes)
    info = dict(nodes=len(pts), elements=len(hexes), scaled_jacobian_min=float(q["sj"].min()),
                edge_min=float(q["emin"].min()), edge_max=float(q["emax"].max()),
                edge_median=float(np.median(q["emax"])), volume_quarter=float(q["vol_total"]),
                radius=float(np.linalg.norm(pts, axis=1).max()))
    info["volume_quarter_gauss"] = float(gauss_volume(pts, hexes))
    info["volume_quarter_exact"] = float(np.pi * R_NEW ** 3 / 3.0)
    # the faceted O-grid is smaller than the sphere; scale the density so the rigid mass is that of a true sphere
    info["density"] = 7850.0 * info["volume_quarter_exact"] / info["volume_quarter_gauss"]
    return pts, hexes, info


def swap_ball(lines, pts, hexes):
    """Replace the Ball part mesh, the ball sets in the assembly and the instance placement of Vals.inp."""
    nn, ne = len(pts), len(hexes)
    p0, _ = span(lines, r"\*Part, name=Ball")
    cards = ["*Node"]
    cards += ["%7d, %s, %s, %s" % (i + 1, fmt(p[0]), fmt(p[1]), fmt(p[2])) for i, p in enumerate(pts)]
    cards += ["*Element, type=C3D8R"]
    cards += ["%7d, " % (i + 1) + ", ".join(str(k + 1) for k in h) for i, h in enumerate(hexes)]
    ns, _ = span(lines, r"\*Nset, nset=_PickedSet2, internal, generate", p0)
    lines = lines[:p0 + 1] + cards + lines[ns:]
    for hdr, count in ((r"\*Nset, nset=_PickedSet2, internal, generate", nn),
                       (r"\*Elset, elset=_PickedSet2, internal, generate", ne)):
        i, _ = span(lines, hdr, p0)
        lines[i + 1] = "     1,  %d,      1" % count
    xs = {i + 1 for i in range(nn) if abs(pts[i, 0]) < 1e-12}
    zs = {i + 1 for i in range(nn) if abs(pts[i, 2]) < 1e-12}
    ex = [i + 1 for i, h in enumerate(hexes) if sum((k + 1) in xs for k in h) >= 4]
    ez = [i + 1 for i, h in enumerate(hexes) if sum((k + 1) in zs for k in h) >= 4]
    all_n, all_e = list(range(1, nn + 1)), list(range(1, ne + 1))

    def put(header, data, new_header=None):
        nonlocal lines
        i, j = span(lines, header)
        lines = lines[:i] + [new_header or lines[i]] + chunks(data) + lines[j:]

    put(r"\*Nset, nset=X, instance=Ball-1$", sorted(xs))
    put(r"\*Elset, elset=X, instance=Ball-1$", ex)
    put(r"\*Nset, nset=Y, instance=Ball-1, generate", sorted(zs), "*Nset, nset=Y, instance=Ball-1")
    put(r"\*Elset, elset=Y, instance=Ball-1$", ez)
    put(r"\*Nset, nset=ball, instance=Ball-1, generate", all_n, "*Nset, nset=ball, instance=Ball-1")
    put(r"\*Elset, elset=ball, instance=Ball-1, generate", all_e, "*Elset, elset=ball, instance=Ball-1")
    put(r"\*Nset, nset=_PickedSet13, internal, instance=Ball-1, generate", all_n,
        "*Nset, nset=_PickedSet13, internal, instance=Ball-1")
    put(r"\*Elset, elset=_PickedSet13, internal, instance=Ball-1, generate", all_e,
        "*Elset, elset=_PickedSet13, internal, instance=Ball-1")
    # instance placement: translation and the rotation axis (through the ball centre, along -x) share the old z
    i, _ = span(lines, r"\*Instance, name=Ball-1, part=Ball")
    old = "0.011"
    z = fmt(CENTRE_Z)
    assert old in lines[i + 1] and lines[i + 2].count(old) == 2, lines[i + 1:i + 3]
    lines[i + 1] = "          0.,           0.,        " + z
    lines[i + 2] = "          0.,           0.,        %s,          -1.,           0.,        %s,          90." % (z, z)
    return lines


def once(text, old, new, label):
    assert text.count(old) == 1, "%s: expected 1 match, found %d" % (label, text.count(old))
    return text.replace(old, new)


def rigid_ball(text, density):
    """Element-based rigid ball driven by a reference node at the ball centre (as build_vals_rigid.py)."""
    for nset in ("X", "Y"):  # symmetry acts on the reference node instead of the ball nodes
        pat = re.compile(r"\*Nset, nset=%s, instance=Ball-1[^\n]*\n(?:[^*][^\n]*\n)*" % nset)
        assert len(pat.findall(text)) == 1, nset
        text = pat.sub("", text)
    z = fmt(CENTRE_Z)
    text = once(text, "*Density\n7850.,",
                "** density raised so the faceted rigid ball has the mass of a 3/8 in steel sphere\n"
                "*Density\n%s," % fmt(density), "steel density")
    text = once(text, "*End Assembly\n",
                "** rigid ball reference point, on the impact axis at the ball centre\n"
                "*Node, nset=BALL_RP\n1, 0., 0., %s\n"
                "** rigid ball: mass and inertia from the steel density of its elements\n"
                "*Rigid Body, ref node=BALL_RP, elset=ball\n*End Assembly\n" % z, "rigid body")
    text = once(text, "*Initial Conditions, type=VELOCITY\n_PickedSet13, 3, -1028.\n",
                "*Boundary\nBALL_RP, 1, 2\nBALL_RP, 4, 6\n"
                "*Initial Conditions, type=VELOCITY\nBALL_RP, 3, -%s.\n" % fmt(SPEED).rstrip("."), "velocity")
    text = once(text, "*Output, history, variable=PRESELECT, time interval=7e-08\n",
                "*Output, history, variable=PRESELECT, time interval=7e-08\n*Node Output, nset=BALL_RP\nU3, V3, A3\n",
                "ball history")
    text = once(text, "*Output, field, variable=PRESELECT, number interval=1000\n",
                "*Output, field, variable=PRESELECT, number interval=1000\n"
                "*Contact Output\nCSDMG, CSMAXSCRT, CSTRESS, CDISP\n", "contact output")
    return text


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    raw = VALS.read_bytes()
    crlf = b"\r\n" in raw[:2000]
    lines = raw.decode().replace("\r\n", "\n").split("\n")
    pts, hexes, info = make_ball()
    lines = swap_ball(lines, pts, hexes)
    text = "\n".join(lines)
    text = once(text, "_PickedSet13, 3, -1000.", "_PickedSet13, 3, -1028.", "speed")
    src = OUT / "Vals_ballfix.inp"
    src.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode())
    print("ball:", info)

    base = OUT / "_plywise"
    shared = base / "Vals_cohesive.inp"
    shared.parent.mkdir(parents=True, exist_ok=True)
    shared.write_text(bvp.with_static_fiber_curve(bvp.with_cohesive(src.read_text())))
    log = {"ball": info, "gap_m": GAP, "centre_z_m": CENTRE_Z, "speed": SPEED, "source_sha256": hashlib.sha256(raw).hexdigest()}
    for kind, extra in (("native", ["--host-mode", "native"]),
                        ("vuel", ["--host-mode", "vuel-ghost", "--matrix-model", "ductile-damage",
                                  "--vuel-eps-fail", str(bvp.EPSF)])):
        out = base / kind
        rep = bvp.run_cli(shared, out, extra)
        deck = (out / "output.inp").read_bytes()
        crlf2 = b"\r\n" in deck[:2000]
        t = rigid_ball(deck.decode().replace("\r\n", "\n"), info["density"])
        if crlf2:
            t = t.replace("\n", "\r\n")
        dst = OUT / kind / ("vrb_" + kind + ".inp")
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(t.encode())
        log[kind] = {"deck": str(dst.relative_to(ROOT)), "sha256": hashlib.sha256(t.encode()).hexdigest(),
                     "ball_contact": {k: rep["ball_contact"].get(k) for k in
                                      ("plate_node_count", "fiber_node_count", "plate_contact_thickness",
                                       "fiber_contact_thickness", "host_median_edge_length", "thickness_note")}}
        print("wrote", dst)
    (OUT / "ballfix_build_log.json").write_text(json.dumps(log, indent=2))


if __name__ == "__main__":
    main()
