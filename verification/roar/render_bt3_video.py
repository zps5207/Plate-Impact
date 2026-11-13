"""Side-by-side symmetry-plane video of the bt3 decks (c2 reference, d1 full fixes, d2 elastic ball), 0-12 us.

Plate grey (deleted host elements hidden), ball red, fibers not drawn. Camera as in render_bt3_views.py.
Usage: python verification/roar/render_bt3_video.py [frame_step, default 2] -> reports/bt3_compare.mp4
"""
import json
import sys
import numpy as np
import pyvista as pv
import imageio

pv.OFF_SCREEN = True
R2 = "Meshing/vals-plywise-balltests2/results"
R3 = "Meshing/vals-plywise-balltests3/results"
RUNS = [("c2 reference (steel ball)", f"{R2}/c2_truss_d4_md80_viewer.npz"),
        ("d1 full fixes", f"{R3}/d1_fullfix_viewer.npz"),
        ("d2 elastic ball", f"{R3}/d2_elastic_viewer.npz")]
STEP = int(sys.argv[1]) if len(sys.argv) > 1 else 2
SIZE = (540, 600)
sym = json.load(open(f"{R2}/viewer_c2_truss_d4_md80/manifest.json"))["camera_presets"]["symmetry"]


def grid(pos, parts, alive=None):
    cells, types = [], []
    for conn, n, ct in parts:
        c = conn if alive is None else conn[alive]
        cells.append(np.hstack([np.full((len(c), 1), n), c]).ravel())
        types += [ct] * len(c)
    return pv.UnstructuredGrid(np.concatenate(cells).astype(np.int64), np.array(types, dtype=np.uint8), pos.astype(np.float64))


def ball_parts(d):
    parts = []
    if "ball_conn_C3D8R" in d.files and len(d["ball_conn_C3D8R"]):
        parts.append((d["ball_conn_C3D8R"], 8, pv.CellType.HEXAHEDRON))
    if "ball_conn_C3D6R" in d.files and len(d["ball_conn_C3D6R"]):
        parts.append((d["ball_conn_C3D6R"], 6, pv.CellType.WEDGE))
    return parts


panels = []
for label, npz in RUNS:
    d = np.load(npz)
    t_us = d["times"] * 1e6
    host_conn = d["host_conn_C3D8R"]
    bp = ball_parts(d)
    pl = pv.Plotter(off_screen=True, window_size=SIZE)
    pl.set_background("white")
    fpt = np.array(sym["focal_point"], dtype=float)
    fpt[0], fpt[2] = 0.008, -0.006
    frames = []
    for i in range(0, len(t_us), STEP):
        pl.clear()
        hg = grid(d["host_pos"][i], [(host_conn, 8, pv.CellType.HEXAHEDRON)], alive=d["host_status"][i] > 0.5)
        bg = grid(d["ball_pos"][i], bp)
        pl.add_mesh(hg.extract_surface(algorithm="dataset_surface"), color="#9aa5b1", show_edges=False)
        pl.add_mesh(bg.extract_surface(algorithm="dataset_surface"), color="#c0392b", show_edges=False)
        pl.camera.focal_point = fpt
        pl.camera.position = fpt + (np.array(sym["position"]) - np.array(sym["focal_point"]))
        pl.camera.up = sym["up"]
        pl.camera.parallel_projection = True
        pl.camera.parallel_scale = 0.022
        pl.add_text("%s   t = %.1f us" % (label, t_us[i]), font_size=9, color="black", name="t")
        pl.reset_camera_clipping_range()
        frames.append(pl.screenshot(return_img=True))
    pl.close()
    panels.append(frames)
    print(label, len(frames), "frames", flush=True)

n = min(len(p) for p in panels)
video = [np.hstack([p[i] for p in panels]) for i in range(n)]
imageio.mimwrite("reports/bt3_compare.mp4", video, fps=10, macro_block_size=None, quality=7)
print("wrote reports/bt3_compare.mp4", n, "frames", video[0].shape)
