"""Static pyvista renders of the vp5 viewer npz: iso + symmetry (flat side), solid + wireframe."""
import json
import sys
import numpy as np
import pyvista as pv

pv.OFF_SCREEN = True
R = "Meshing/vals-plywise-erode/results"
OUT = "reports/vp5_renders"
d = np.load(f"{R}/vals_native_er_viewer.npz")
man = json.load(open(f"{R}/viewer_vp5/manifest.json"))
t_us = d["times"] * 1e6
want = [float(x) for x in (sys.argv[1].split(",") if len(sys.argv) > 1 else "0,5,15,30,70".split(","))]
frames = [int(np.argmin(abs(t_us - w))) for w in want]
conn = d["host_conn_C3D8R"]
bc8, bc6 = d["ball_conn_C3D8R"], d["ball_conn_C3D6R"]
fib = d["fiber_conn_T3D2"]
cam = man["camera_presets"]
sym = cam["symmetry"]
iso = cam["iso"]
s = sym["parallel_scale"]


def grid(pos, cells8, cells6=None, alive=None):
    c8 = cells8 if alive is None else cells8[alive]
    cells = np.hstack([np.full((len(c8), 1), 8), c8]).ravel()
    types = [pv.CellType.HEXAHEDRON] * len(c8)
    if cells6 is not None and len(cells6):
        cells = np.concatenate([cells, np.hstack([np.full((len(cells6), 1), 6), cells6]).ravel()])
        types += [pv.CellType.WEDGE] * len(cells6)
    return pv.UnstructuredGrid(cells.astype(np.int64), np.array(types, dtype=np.uint8), pos.astype(np.float64))


def plot(i, view, style):
    pl = pv.Plotter(off_screen=True, window_size=((1000, 700) if view == 'iso' else (720, 800)))
    pl.set_background("white")
    alive = d["host_status"][i] > 0.5
    hg = grid(d["host_pos"][i], conn, alive=alive)
    bg = grid(d["ball_pos"][i], bc8, bc6)
    kw = dict(show_edges=False)
    if style == "solid":
        pl.add_mesh(hg.extract_surface(algorithm='dataset_surface'), color="#9aa5b1", smooth_shading=False, **kw)
        pl.add_mesh(bg.extract_surface(algorithm='dataset_surface'), color="#c0392b", **kw)
    else:
        pl.add_mesh(hg.extract_surface(algorithm='dataset_surface').extract_all_edges(), color="#4a5560", line_width=0.5)
        pl.add_mesh(bg.extract_surface(algorithm='dataset_surface').extract_all_edges(), color="#c0392b", line_width=0.6)
    if view == "iso":
        fpt = np.array([0.02, 0.02, -0.008])
        dirv = np.array([-1.0, -1.0, 0.8])
        pl.camera.focal_point = fpt
        pl.camera.position = fpt + 0.16 * dirv / np.linalg.norm(dirv)
        pl.camera.up = (0, 0, 1)
        pl.camera.view_angle = 30.0
    else:
        fpt = np.array(sym["focal_point"], dtype=float)
        fpt[2] = -0.002
        fpt[0] = 0.027      # zoom on the impact zone (plate is a 0.1 m quarter disc)
        pl.camera.focal_point = fpt
        pl.camera.position = fpt + (np.array(sym["position"]) - np.array(sym["focal_point"]))
        pl.camera.up = sym["up"]
        if style == "wire":
            fp = d["fiber_pos"][i].astype(np.float64)
            near = d["fiber_coords0"][:, 1] < 0.002
            sel = near[fib[:, 0]] & near[fib[:, 1]]
            lines = np.hstack([np.full((int(sel.sum()), 1), 2), fib[sel]]).ravel()
            pl.add_mesh(pv.PolyData(fp, lines=lines), color="#0033cc", line_width=0.8)
        pl.camera.parallel_projection = True
        pl.camera.parallel_scale = 0.03
    pl.add_text("t = %.1f us   %s %s" % (t_us[i], view, style), font_size=9, color="black")
    pl.reset_camera_clipping_range()
    fn = f"{OUT}/f{i:03d}_{view}_{style}.png"
    pl.screenshot(fn)
    pl.close()
    return fn


if __name__ == "__main__":
    for i in frames:
        for view in ("iso", "sym"):
            for style in ("solid", "wire"):
                print(plot(i, view, style), flush=True)
