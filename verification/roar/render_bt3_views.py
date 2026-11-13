"""Static pyvista renders of the bt2 viewer npz files: symmetry plane (y = 0 flat side), solid, zoomed on the impact.

Usage: python render_bt3_views.py [times_us comma list]  (default 4,8,12)
Writes reports/bt3_renders/<deck>_t<us>.png. vp5 is rendered from its own npz for comparison.
"""
import json
import os
import sys
import numpy as np
import pyvista as pv

pv.OFF_SCREEN = True
R = "Meshing/vals-plywise-balltests2/results"
R3 = "Meshing/vals-plywise-balltests3/results"
R5 = "Meshing/vals-plywise-erode/results"
OUT = "reports/bt3_renders"
os.makedirs(OUT, exist_ok=True)
DECKS = ["c2_truss_d4_md80", "d1_fullfix", "d2_elastic"]
want = [float(x) for x in (sys.argv[1].split(",") if len(sys.argv) > 1 else "4,8,12".split(","))]


def grid(pos, parts, alive=None):
    cells, types = [], []
    for conn, n, ct in parts:
        c = conn if alive is None else conn[alive]
        cells.append(np.hstack([np.full((len(c), 1), n), c]).ravel())
        types += [ct] * len(c)
    return pv.UnstructuredGrid(np.concatenate(cells).astype(np.int64), np.array(types, dtype=np.uint8),
                               pos.astype(np.float64))


def ball_parts(d):
    parts = []
    if "ball_conn_C3D8R" in d.files and len(d["ball_conn_C3D8R"]):
        parts.append((d["ball_conn_C3D8R"], 8, pv.CellType.HEXAHEDRON))
    if "ball_conn_C3D6R" in d.files and len(d["ball_conn_C3D6R"]):
        parts.append((d["ball_conn_C3D6R"], 6, pv.CellType.WEDGE))
    return parts


for name in DECKS:
    npz = f"{R3}/{name}_viewer.npz" if name.startswith("d") else f"{R}/{name}_viewer.npz"
    mandir = f"{R}/viewer_c2_truss_d4_md80"  # camera presets: same plate geometry for all three
    d = np.load(npz)
    sym = json.load(open(f"{mandir}/manifest.json"))["camera_presets"]["symmetry"]
    t_us = d["times"] * 1e6
    host_conn = d["host_conn_C3D8R"]
    for w in want:
        i = int(np.argmin(abs(t_us - w)))
        pl = pv.Plotter(off_screen=True, window_size=(720, 800))
        pl.set_background("white")
        alive = d["host_status"][i] > 0.5
        hg = grid(d["host_pos"][i], [(host_conn, 8, pv.CellType.HEXAHEDRON)], alive=alive)
        bg = grid(d["ball_pos"][i], ball_parts(d))
        pl.add_mesh(hg.extract_surface(algorithm="dataset_surface"), color="#9aa5b1", show_edges=False)
        pl.add_mesh(bg.extract_surface(algorithm="dataset_surface"), color="#c0392b", show_edges=False)
        fpt = np.array(sym["focal_point"], dtype=float)
        fpt[0], fpt[2] = 0.008, -0.006
        pl.camera.focal_point = fpt
        pl.camera.position = fpt + (np.array(sym["position"]) - np.array(sym["focal_point"]))
        pl.camera.up = sym["up"]
        pl.camera.parallel_projection = True
        pl.camera.parallel_scale = 0.022
        pl.add_text("%s   t = %.1f us" % (name, t_us[i]), font_size=9, color="black")
        pl.reset_camera_clipping_range()
        fn = f"{OUT}/{name}_t{int(round(w)):02d}.png"
        pl.screenshot(fn)
        pl.close()
        print(fn, flush=True)
