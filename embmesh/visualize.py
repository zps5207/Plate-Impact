from __future__ import annotations

from pathlib import Path
import numpy as np


HEX_EDGES = ((0, 1), (1, 2), (2, 3), (3, 0),
             (4, 5), (5, 6), (6, 7), (7, 4),
             (0, 4), (1, 5), (2, 6), (3, 7))


def write_host_fiber_vtk(path, elements, nodes, fibers, fractions=None):
    """Write one legacy VTK file containing host hex wireframes and fibers."""
    points = []
    lines = []
    cell_fraction = []
    for label, element in elements.items():
        ids = []
        for node in element.connectivity[:8]:
            ids.append(len(points)); points.append(np.asarray(nodes[node], float))
        for a, b in HEX_EDGES:
            lines.append((ids[a], ids[b])); cell_fraction.append(float((fractions or {}).get(label, 0.0)))
    for fiber in fibers:
        start = len(points); points.extend(np.asarray(fiber.points, float).tolist())
        lines.append((start, start + 1)); cell_fraction.append(-1.0)
    with open(path, "w", encoding="utf-8") as stream:
        stream.write("# vtk DataFile Version 3.0\nembmesh host/fiber visualization\nASCII\nDATASET POLYDATA\n")
        stream.write(f"POINTS {len(points)} float\n")
        stream.write("\n".join("%.12g %.12g %.12g" % tuple(p) for p in points) + "\n")
        stream.write(f"LINES {len(lines)} {3 * len(lines)}\n")
        stream.write("\n".join(f"2 {a} {b}" for a, b in lines) + "\n")
        stream.write(f"CELL_DATA {len(lines)}\nSCALARS host_volume_fraction float 1\nLOOKUP_TABLE default\n")
        stream.write("\n".join("%.12g" % x for x in cell_fraction) + "\n")


def plot_host_fibers(path, elements, nodes, fibers, fractions=None):
    """Render a portable PNG preview; matplotlib is imported only on demand."""
    import matplotlib.pyplot as plt

    fig = plt.figure(figsize=(9, 7)); ax = fig.add_subplot(111, projection="3d")
    for label, element in elements.items():
        p = np.asarray([nodes[n] for n in element.connectivity[:8]], float)
        for a, b in HEX_EDGES:
            ax.plot([p[a, 0], p[b, 0]], [p[a, 1], p[b, 1]], [p[a, 2], p[b, 2]], color="0.65", linewidth=.6)
    for fiber in fibers:
        p = np.asarray(fiber.points)
        ax.plot(p[:, 0], p[:, 1], p[:, 2], color="crimson", linewidth=1.5)
    ax.set_xlabel("X"); ax.set_ylabel("Y"); ax.set_zlabel("Z"); ax.set_title("embmesh host elements and fibers")
    fig.tight_layout(); fig.savefig(path, dpi=160); plt.close(fig)

