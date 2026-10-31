"""Build the short-onset ball-failure decks from the full vp5 native Vals deck (T-050 follow-up).

  b0_base      vp5 unchanged except the step length (comparison baseline, same output cadence)
  b1_beamsurf  fibers T3D2 -> B31 (circular section r = 0.316 mm) with an ELEMENT-based fiber contact surface
               instead of the node surface with THICKNESS 0.618 mm
  b2_newball   uniform O-grid ball mesh (ball_mesh.py), node-based fiber contact as in vp5
  b3_both      b1 + b2
  b4_d4fix     vp5 with only the JC damage D4 changed -0.05279 -> +0.002 (agy T-049 hypothesis: negative D4 makes the
               failure strain negative above ~1.7e4 /s)
  b5_steelA    agy's recalibrated mild steel (Option A: plasticity rate term C, D1..D5 literature set)
  b6_316L      agy's AISI 316L card (Option B), density 8060; card keeps the name "Mild Steel" so sections still match

Usage: python verification/roar/ball_tests/build_ball_tests.py [out_dir] [step_time_s]
"""
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ball_mesh as bm

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "Meshing" / "vals-plywise-erode" / "native" / "output.inp"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "Meshing" / "vals-plywise-balltests"
STEP = sys.argv[2] if len(sys.argv) > 2 else "1.2e-05"

N_CELLS, N_RAD, HC, SMOOTH = 28, 10, 0.5, 10
FIBER_RADIUS = "0.000316"


def chunks(ids, n=16):
    return [", ".join(str(i) for i in ids[s:s + n]) for s in range(0, len(ids), n)]


def fmt(v):
    return "%.9g" % v


def block_span(lines, header_re, start=0):
    """(index of the header, index one past its data lines) for the first header match at/after start."""
    for i in range(start, len(lines)):
        if re.match(header_re, lines[i]):
            j = i + 1
            while j < len(lines) and not lines[j].startswith("*"):
                j += 1
            return i, j
    raise ValueError(header_re)


def old_ball_volume(lines):
    """Volume of the vp5 ball part (hex + wedge) from its node/element cards, to keep the mass identical."""
    i0, _ = block_span(lines, r"\*Part, name=Ball")
    nodes, j = {}, i0 + 2
    while not lines[j].startswith("*"):
        p = lines[j].split(",")
        nodes[int(p[0])] = [float(x) for x in p[1:4]]
        j += 1
    vol = 0.0
    while True:
        if lines[j].startswith("*Element"):
            etype = lines[j].split("type=")[1].split(",")[0].strip()
            j += 1
            if etype == "C3D8R":
                faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
            else:
                faces = [(0, 2, 1), (3, 4, 5), (0, 1, 4, 3), (1, 2, 5, 4), (2, 0, 3, 5)]
            while not lines[j].startswith("*"):
                p = [int(x) for x in lines[j].split(",")]
                X = np.array([nodes[k] for k in p[1:]])
                c = X.mean(0)
                for f in faces:
                    for t in range(1, len(f) - 1):
                        a, b, d = X[f[0]] - c, X[f[t]] - c, X[f[t + 1]] - c
                        vol += abs(np.dot(a, np.cross(b, d))) / 6.0
                j += 1
        elif lines[j].startswith("*Nset") or lines[j].startswith("*End Part"):
            break
        else:
            j += 1
    return vol


def new_ball(target_volume):
    pts, hexes = bm.build(N_CELLS, N_RAD, HC, iters=SMOOTH)
    q = bm.quality(pts, hexes)
    pts = pts * (target_volume / q["vol_total"]) ** (1.0 / 3.0)
    q = bm.quality(pts, hexes)
    info = dict(nodes=len(pts), elements=len(hexes), sj_min=float(q["sj"].min()),
                edge_min=float(q["emin"].min()), edge_max=float(q["emax"].max()),
                edge_median=float(np.median(q["emax"])), volume=q["vol_total"],
                radius_scale=float(np.linalg.norm(pts, axis=1).max() / bm.R))
    return pts, hexes, info


def with_new_ball(lines, pts, hexes):
    nn, ne = len(pts), len(hexes)
    p0, _ = block_span(lines, r"\*Part, name=Ball")
    cards = ["*Node"]
    cards += ["%7d, %s, %s, %s" % (i + 1, fmt(p[0]), fmt(p[1]), fmt(p[2])) for i, p in enumerate(pts)]
    cards += ["*Element, type=C3D8R"]
    cards += ["%7d, " % (i + 1) + ", ".join(str(k + 1) for k in h) for i, h in enumerate(hexes)]
    ns, _ = block_span(lines, r"\*Nset, nset=_PickedSet2, internal, generate", p0)
    lines = lines[:p0 + 1] + cards + lines[ns:]
    for hdr, count in ((r"\*Nset, nset=_PickedSet2, internal, generate", nn),
                       (r"\*Elset, elset=_PickedSet2, internal, generate", ne)):
        i, _ = block_span(lines, hdr, p0)
        lines[i + 1] = "     1,  %d,      1" % count
    onx = [i + 1 for i in range(nn) if abs(pts[i, 0]) < 1e-12]
    onz = [i + 1 for i in range(nn) if abs(pts[i, 2]) < 1e-12]
    xs, zs = set(onx), set(onz)
    ex = [i + 1 for i, h in enumerate(hexes) if sum((k + 1) in xs for k in h) >= 4]
    ez = [i + 1 for i, h in enumerate(hexes) if sum((k + 1) in zs for k in h) >= 4]
    all_nodes, all_elems = list(range(1, nn + 1)), list(range(1, ne + 1))

    def put(header, data, new_header=None):
        nonlocal lines
        i, j = block_span(lines, header)
        lines = lines[:i] + [new_header or lines[i]] + chunks(data) + lines[j:]

    put(r"\*Nset, nset=X, instance=Ball-1$", onx)
    put(r"\*Elset, elset=X, instance=Ball-1$", ex)
    put(r"\*Nset, nset=Y, instance=Ball-1, generate", onz, "*Nset, nset=Y, instance=Ball-1")
    put(r"\*Elset, elset=Y, instance=Ball-1$", ez)
    put(r"\*Nset, nset=ball, instance=Ball-1, generate", all_nodes, "*Nset, nset=ball, instance=Ball-1")
    put(r"\*Elset, elset=ball, instance=Ball-1, generate", all_elems, "*Elset, elset=ball, instance=Ball-1")
    put(r"\*Nset, nset=_PickedSet13, internal, instance=Ball-1, generate", all_nodes,
        "*Nset, nset=_PickedSet13, internal, instance=Ball-1")
    put(r"\*Elset, elset=_PickedSet13, internal, instance=Ball-1, generate", all_elems,
        "*Elset, elset=_PickedSet13, internal, instance=Ball-1")
    put(r"\*Elset, elset=EMBMESH_BALL_ELEMENTS, instance=Ball-1$", all_elems)
    return lines


def with_beam_fibers(lines):
    text = "\n".join(lines)
    assert text.count("*Element, type=T3D2, elset=FIBERS") == 2
    text = text.replace("*Element, type=T3D2, elset=FIBERS", "*Element, type=B31, elset=FIBERS")
    sec = re.compile(r"\*Solid Section, elset=FIBERS, material=Fiber, controls=EMBMESH_DELETE_ALL\n[^\n]*\n")
    assert len(sec.findall(text)) == 2
    text = sec.sub("*Beam Section, elset=FIBERS, material=Fiber, section=CIRC, controls=EMBMESH_DELETE_ALL\n"
                   + FIBER_RADIUS + "\n0.,0.,-1.\n", text)
    inst = re.findall(r"^\*Instance, name=(Fibers-Ply-\d+), part=", text, re.M)
    assert len(inst) == 20
    surf = "*Surface, type=ELEMENT, name=EMBMESH_FIBER_SURF\n" + "\n".join("%s.FIBERS," % n for n in inst) + "\n"
    old = "*Surface, type=NODE, name=EMBMESH_FIBER_NODES\nEMBMESH_FIBER_ALL_NODES,\n"
    assert old in text
    text = text.replace(old, surf)
    pair = "EMBMESH_FIBER_NODES , EMBMESH_BALL_SURF"
    assert pair in text
    text = text.replace(pair, "EMBMESH_FIBER_SURF , EMBMESH_BALL_SURF")
    prop = re.compile(r"\*Surface Property Assignment, property=THICKNESS\nEMBMESH_FIBER_NODES, [^\n]*\n")
    assert len(prop.findall(text)) == 1
    text = prop.sub("", text)
    assert "EMBMESH_FIBER_NODES" not in text
    return text.split("\n")


STEEL_A = """*Material, name="Mild Steel"
*Density
7850.,
*Elastic
 2.03e+11, 0.33
*Plastic, hardening=JOHNSON COOK
 3.0433e+08, 4.22007e+08, 0.345, 0.87, 1800., 293.
*Rate Dependent, type=JOHNSON COOK
 0.0156, 1.0
*Damage Initiation, criterion=JOHNSON COOK
 0.05, 0.344, -2.12, 0.002, 0.61, 1800., 293., 1.0
*Damage Evolution, type=DISPLACEMENT
0."""
STEEL_316L = """*Material, name="Mild Steel"
*Density
8060.,
*Elastic
 2.02e+11, 0.27
*Plastic, hardening=JOHNSON COOK
 3.05e+08, 1.161e+09, 0.610, 0.517, 1800., 293.
*Rate Dependent, type=JOHNSON COOK
 0.015, 1.0
*Damage Initiation, criterion=JOHNSON COOK
 0.071, 1.248, -1.142, 0.002, 0.10, 1800., 293., 1.0
*Damage Evolution, type=DISPLACEMENT
0."""


def with_steel(lines, card=None, d4=None):
    """Swap the whole steel material card, or only the damage D4 (keeps every other number of vp5)."""
    nl = chr(10)
    text = nl.join(lines)
    if d4 is not None:
        old = " 0.1152,   1.0116,  -1.7684, -0.05279,   0.5262,    1800.,     293.,   0.0001"
        assert text.count(old) == 1
        return text.replace(old, " 0.1152,   1.0116,  -1.7684, %s,   0.5262,    1800.,     293.,   0.0001" % d4).split(nl)
    i = text.index('*Material, name="Mild Steel"')
    j = text.index("** " + nl + "** INTERACTION PROPERTIES", i)
    return (text[:i] + card + nl + text[j:]).split(nl)


def with_step(lines):
    text = "\n".join(lines)
    old = "*Dynamic, Explicit\n, 7e-05\n"
    assert old in text
    return text.replace(old, "*Dynamic, Explicit\n, %s\n" % STEP).split("\n")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    lines = SRC.read_text().split("\n")
    vol = old_ball_volume(lines)
    pts, hexes, info = new_ball(vol)
    info["old_volume"] = vol
    print({k: (round(v, 6) if isinstance(v, float) else v) for k, v in info.items()})
    base = with_step(lines)
    decks = {"b0_base": base,
             "b1_beamsurf": with_beam_fibers(base),
             "b2_newball": with_new_ball(base, pts, hexes),
             "b3_both": with_new_ball(with_beam_fibers(base), pts, hexes),
             "b4_d4fix": with_steel(base, d4="0.002"),
             "b5_steelA": with_steel(base, card=STEEL_A),
             "b6_316L": with_steel(base, card=STEEL_316L)}
    for name, ls in decks.items():
        d = OUT / name
        d.mkdir(exist_ok=True)
        (d / (name + ".inp")).write_text("\n".join(ls), newline="\n")
        print(name, len(ls), "lines")


if __name__ == "__main__":
    main()
