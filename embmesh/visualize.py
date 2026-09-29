from __future__ import annotations

from pathlib import Path
import numpy as np

# The VTK writer used to be duplicated here; embmesh.hostvtk is the one real
# implementation (kept importable from here too so nothing that imported it
# from this module breaks).
from .hostvtk import HEX_EDGES, write_host_fiber_vtk  # noqa: F401


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

