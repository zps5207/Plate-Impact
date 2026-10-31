"""Symmetry-plane video of d4_weldox_100us (Weldox 460E JC ball, 0-100 us): wide view following the ball path, plus a plate close-up.

Plate grey (deleted host elements hidden), ball red (the viewer file has no ball STATUS, so ball elements stretched beyond 1.5x their initial longest edge are hidden as deleted), fibers not drawn.
Usage: python verification/roar/render_d4_video.py [frame_step, default 2] -> reports/d4_weldox_100us.mp4
"""
import json
import sys
import numpy as np
import pyvista as pv
import imageio

pv.OFF_SCREEN = True
R2 = "Meshing/vals-plywise-balltests2/results"
NPZ = "Meshing/vals-plywise-balltests3/results/d4_weldox_100us_viewer.npz"
STEP = int(sys.argv[1]) if len(sys.argv) > 1 else 2
SIZE = (560, 840)
sym = json.load(open(f"{R2}/viewer_c2_truss_d4_md80/manifest.json"))["camera_presets"]["symmetry"]
VIEWS = [("wide", (0.008, -0.035), 0.075), ("plate close-up", (0.008, -0.0127), 0.022)]  # (x, z) focal point, parallel scale (half height, m)


def grid(pos, parts, alive=None):
    cells, types = [], []
    for conn, n, ct in parts:
        c = conn if alive is None else conn[alive]
        cells.append(np.hstack([np.full((len(c), 1), n), c]).ravel())
        types += [ct] * len(c)
    return pv.UnstructuredGrid(np.concatenate(cells).astype(np.int64), np.array(types, dtype=np.uint8), pos.astype(np.float64))


HEX_EDGES = [(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4), (0, 4), (1, 5), (2, 6), (3, 7)]
WEDGE_EDGES = [(0, 1), (1, 2), (2, 0), (3, 4), (4, 5), (5, 3), (0, 3), (1, 4), (2, 5)]
STRETCH = 1.5  # ball element is treated as deleted (ghost) when its longest edge exceeds this x its initial longest edge


def max_edge(pos, conn, edges):
    return np.max([np.linalg.norm(pos[conn[:, a]] - pos[conn[:, b]], axis=1) for a, b in edges], axis=0)


d = np.load(NPZ)
t_us = d["times"] * 1e6
host_conn = d["host_conn_C3D8R"]
bp = [(d["ball_conn_C3D8R"], 8, pv.CellType.HEXAHEDRON, HEX_EDGES), (d["ball_conn_C3D6R"], 6, pv.CellType.WEDGE, WEDGE_EDGES)]
ball0 = d["ball_coords0"].astype(np.float64)
edge0 = [max_edge(ball0, c, e) for c, n, ct, e in bp]


def ball_alive_parts(pos):
    pos = pos.astype(np.float64)
    return [(c[max_edge(pos, c, e) < STRETCH * e0], n, ct) for (c, n, ct, e), e0 in zip(bp, edge0)]
panels = []
for label, (fx, fz), scale in VIEWS:
    pl = pv.Plotter(off_screen=True, window_size=SIZE)
    pl.set_background("white")
    fpt = np.array(sym["focal_point"], dtype=float)
    fpt[0], fpt[2] = fx, fz
    frames = []
    for i in range(0, len(t_us), STEP):
        pl.clear()
        hg = grid(d["host_pos"][i], [(host_conn, 8, pv.CellType.HEXAHEDRON)], alive=d["host_status"][i] > 0.5)
        bg = grid(d["ball_pos"][i], ball_alive_parts(d["ball_pos"][i]))
        pl.add_mesh(hg.extract_surface(algorithm="dataset_surface"), color="#9aa5b1", show_edges=False)
        pl.add_mesh(bg.extract_surface(algorithm="dataset_surface"), color="#c0392b", show_edges=False)
        pl.camera.focal_point = fpt
        pl.camera.position = fpt + (np.array(sym["position"]) - np.array(sym["focal_point"]))
        pl.camera.up = sym["up"]
        pl.camera.parallel_projection = True
        pl.camera.parallel_scale = scale
        pl.add_text("d4 Weldox ball, %s   t = %.1f us" % (label, t_us[i]), font_size=9, color="black", name="t")
        pl.reset_camera_clipping_range()
        frames.append(pl.screenshot(return_img=True))
    pl.close()
    panels.append(frames)
    print(label, len(frames), "frames", flush=True)

video = [np.hstack([p[i] for p in panels]) for i in range(min(len(p) for p in panels))]
imageio.mimwrite("reports/d4_weldox_100us.mp4", video, fps=10, macro_block_size=None, quality=7)
print("wrote reports/d4_weldox_100us.mp4", len(video), "frames", video[0].shape)
