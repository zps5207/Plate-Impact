"""Generate synthetic .npz test data for ODB viewer.

Matches the key schema, types, and element conventions of
verification/roar/export_odb_viewer.py:
- roles: host, ball, fiber
- times: (frames,) float64
- meta: JSON string
- <role>_coords0: (N, 3) float32
- <role>_pos: (frames, N, 3) float32
- <role>_conn_<TYPE>: (E, k) int32
- host_status: (frames, E_host) uint8 (1 = alive, 0 = dead)

Scene geometry:
- Host plate: 14x14x2 hex grid (392 C3D8R elements, 675 nodes), dimensions 30x30x2 mm,
  centered on Z in [0, 2] mm, X/Y in [-15, 15] mm.
- Ball: spherical hex mesh (64 C3D8R elements, 125 nodes), radius 2.5 mm,
  traveling along -Z from Z = +7.5 mm to Z = -7.0 mm.
- Fibers: cross-ply lines of T3D2 truss elements (10 lines x 14 segments = 140 elements,
  150 nodes) embedded at Z = 1.0 mm.
- Progressive host element erosion: host elements within r < 2.8 mm of the impact axis
  erode (STATUS -> 0) as the ball passes through the plate.
"""
from __future__ import annotations

import argparse
import json
import os
import numpy as np


def build_hex_mesh(
    nx: int, ny: int, nz: int,
    x_range: tuple[float, float],
    y_range: tuple[float, float],
    z_range: tuple[float, float],
) -> tuple[np.ndarray, np.ndarray]:
    """Build a structured hexahedral mesh with standard Abaqus C3D8 node numbering."""
    xs = np.linspace(x_range[0], x_range[1], nx + 1, dtype=np.float32)
    ys = np.linspace(y_range[0], y_range[1], ny + 1, dtype=np.float32)
    zs = np.linspace(z_range[0], z_range[1], nz + 1, dtype=np.float32)

    # Grid of coordinates
    # node_idx(ix, iy, iz) = iz * (ny + 1) * (nx + 1) + iy * (nx + 1) + ix
    coords = []
    for z in zs:
        for y in ys:
            for x in xs:
                coords.append([x, y, z])
    coords0 = np.array(coords, dtype=np.float32)

    def node_idx(ix: int, iy: int, iz: int) -> int:
        return iz * (ny + 1) * (nx + 1) + iy * (nx + 1) + ix

    elements = []
    for iz in range(nz):
        for iy in range(ny):
            for ix in range(nx):
                n0 = node_idx(ix, iy, iz)
                n1 = node_idx(ix + 1, iy, iz)
                n2 = node_idx(ix + 1, iy + 1, iz)
                n3 = node_idx(ix, iy + 1, iz)
                n4 = node_idx(ix, iy, iz + 1)
                n5 = node_idx(ix + 1, iy, iz + 1)
                n6 = node_idx(ix + 1, iy + 1, iz + 1)
                n7 = node_idx(ix, iy + 1, iz + 1)
                elements.append([n0, n1, n2, n3, n4, n5, n6, n7])

    conn = np.array(elements, dtype=np.int32)
    return coords0, conn


def build_ball_mesh(
    radius: float, center_z0: float, n_sub: int = 4
) -> tuple[np.ndarray, np.ndarray]:
    """Build a spherical hex mesh by projecting a subdivided cube onto a sphere."""
    # Box from -1 to 1 in each dimension
    coords0, conn = build_hex_mesh(n_sub, n_sub, n_sub, (-1.0, 1.0), (-1.0, 1.0), (-1.0, 1.0))

    # Spherify points: project onto sphere surface while preserving radial layers
    max_coords = np.max(np.abs(coords0), axis=1, keepdims=True)
    max_coords[max_coords == 0] = 1.0
    r = np.linalg.norm(coords0, axis=1, keepdims=True)
    scale = np.where(r > 0, (coords0 / (r + 1e-12)) * (max_coords * radius), coords0)
    coords_spherical = scale.astype(np.float32)
    coords_spherical[:, 2] += center_z0

    return coords_spherical, conn


def build_fiber_grid(
    nx: int, ny: int,
    x_range: tuple[float, float],
    y_range: tuple[float, float],
    z_pos: float,
    y_lines: list[float],
    x_lines: list[float],
) -> tuple[np.ndarray, np.ndarray]:
    """Build cross-ply fiber lines (T3D2) embedded in the plate."""
    coords = []
    conn = []
    node_offset = 0

    # Lines along X (constant Y)
    xs = np.linspace(x_range[0], x_range[1], nx + 1, dtype=np.float32)
    for y in y_lines:
        line_nodes = []
        for x in xs:
            coords.append([x, y, z_pos])
            line_nodes.append(node_offset)
            node_offset += 1
        for i in range(len(line_nodes) - 1):
            conn.append([line_nodes[i], line_nodes[i + 1]])

    # Lines along Y (constant X)
    ys = np.linspace(y_range[0], y_range[1], ny + 1, dtype=np.float32)
    for x in x_lines:
        line_nodes = []
        for y in ys:
            coords.append([x, y, z_pos])
            line_nodes.append(node_offset)
            node_offset += 1
        for i in range(len(line_nodes) - 1):
            conn.append([line_nodes[i], line_nodes[i + 1]])

    return np.array(coords, dtype=np.float32), np.array(conn, dtype=np.int32)


def generate_synthetic_data(
    n_frames: int = 30,
    total_time: float = 6.0e-5,
) -> dict[str, np.ndarray]:
    """Generate complete dictionary of synthetic ODB export arrays."""
    times = np.linspace(0.0, total_time, n_frames, dtype=np.float64)

    # 1. Host Plate
    # 14x14x2 hex elements = 392 C3D8R elements, 675 nodes
    # Dimensions: 30 mm x 30 mm x 2 mm
    h_coords0, h_conn = build_hex_mesh(14, 14, 2, (-15.0, 15.0), (-15.0, 15.0), (0.0, 2.0))
    n_host_nodes = len(h_coords0)
    n_host_elems = len(h_conn)

    # 2. Impactor Ball
    # Radius 2.5 mm, initial center at (0, 0, 7.5 mm)
    b_radius = 2.5
    b_center0_z = 7.5
    b_coords0, b_conn = build_ball_mesh(b_radius, b_center0_z, n_sub=4)
    n_ball_nodes = len(b_coords0)

    # 3. Fibers
    # Cross-ply lines at Z = 1.0 mm
    fiber_y = [-6.0, -3.0, 0.0, 3.0, 6.0]
    fiber_x = [-6.0, -3.0, 0.0, 3.0, 6.0]
    f_coords0, f_conn = build_fiber_grid(14, 14, (-15.0, 15.0), (-15.0, 15.0), 1.0, fiber_y, fiber_x)
    n_fiber_nodes = len(f_coords0)

    # Calculate trajectories over time
    # Ball moves from Z = +7.5 mm to Z = -7.0 mm (speed = 14.5 mm / 60 us = ~241 m/s)
    ball_z_centers = np.linspace(7.5, -7.0, n_frames, dtype=np.float32)

    h_pos = np.zeros((n_frames, n_host_nodes, 3), dtype=np.float32)
    b_pos = np.zeros((n_frames, n_ball_nodes, 3), dtype=np.float32)
    f_pos = np.zeros((n_frames, n_fiber_nodes, 3), dtype=np.float32)
    h_status = np.ones((n_frames, n_host_elems), dtype=np.uint8)

    # Compute element centroids in host to determine erosion timing
    elem_centroids = np.mean(h_coords0[h_conn], axis=1)  # (392, 3)
    elem_r = np.linalg.norm(elem_centroids[:, :2], axis=1)  # distance from Z axis
    elem_z = elem_centroids[:, 2]

    # Erosion radius (3.8 mm erodes 12 elements per layer = 24 total elements)
    erosion_radius = 3.8

    for f_idx in range(n_frames):
        bz = ball_z_centers[f_idx]
        delta_bz = bz - b_center0_z

        # Ball rigid translation
        b_pos[f_idx] = b_coords0.copy()
        b_pos[f_idx, :, 2] += delta_bz

        # Host position deformation and status
        # Deflection occurs as ball presses into the plate
        h_pos[f_idx] = h_coords0.copy()
        for i in range(n_host_nodes):
            nx, ny, nz = h_coords0[i]
            nr = np.sqrt(nx * nx + ny * ny)
            if nr < 5.0 and bz < 4.0:
                # Downward bulge proportional to proximity to ball
                factor = max(0.0, 1.0 - nr / 5.0)
                penetration = max(0.0, 2.5 - bz)
                h_pos[f_idx, i, 2] -= float(factor * min(penetration * 0.4, 1.2))

        # Host status deletion:
        # If ball has penetrated past top of element and element is within erosion radius:
        for e_idx in range(n_host_elems):
            ez = elem_z[e_idx]
            er = elem_r[e_idx]
            if er <= erosion_radius:
                # Top layer (ez ~ 1.5) erodes when ball bottom (bz - b_radius) reaches 1.8
                # Bottom layer (ez ~ 0.5) erodes when ball bottom reaches 0.8
                ball_bottom = bz - b_radius
                trigger_z = ez + 0.3
                if ball_bottom < trigger_z:
                    h_status[f_idx:, e_idx] = 0

        # Fiber deformation
        f_pos[f_idx] = f_coords0.copy()
        for i in range(n_fiber_nodes):
            fx, fy, fz = f_coords0[i]
            fr = np.sqrt(fx * fx + fy * fy)
            if bz < 3.5:
                # Pushed downward and slightly outward by ball
                penetration = max(0.0, 3.5 - bz)
                if fr < 4.5:
                    w = max(0.0, 1.0 - fr / 4.5)
                    f_pos[f_idx, i, 2] -= float(w * min(penetration * 0.6, 2.5))
                    # Outward radial push
                    if fr > 1e-4:
                        radial_push = w * 0.3
                        f_pos[f_idx, i, 0] += float((fx / fr) * radial_push)
                        f_pos[f_idx, i, 1] += float((fy / fr) * radial_push)

    meta = {
        "odb": "synthetic_impact.odb",
        "step": "Step-1",
        "frames": list(range(n_frames)),
        "roles": ["host", "ball", "fiber"],
        "types": {
            "host": ["C3D8R"],
            "ball": ["C3D8R"],
            "fiber": ["T3D2"],
        },
    }

    data = {
        "times": times,
        "meta": np.array(json.dumps(meta)),
        "host_coords0": h_coords0,
        "host_pos": h_pos,
        "host_conn_C3D8R": h_conn,
        "host_status": h_status,
        "ball_coords0": b_coords0,
        "ball_pos": b_pos,
        "ball_conn_C3D8R": b_conn,
        "fiber_coords0": f_coords0,
        "fiber_pos": f_pos,
        "fiber_conn_T3D2": f_conn,
    }
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic .npz test dataset for ODB viewer")
    parser.add_argument("--output", "-o", default="synthetic_viewer.npz", help="Output .npz path")
    parser.add_argument("--frames", "-f", type=int, default=30, help="Number of animation frames")
    parser.add_argument("--time", "-t", type=float, default=6.0e-5, help="Total simulation duration (s)")
    args = parser.parse_args()

    data = generate_synthetic_data(n_frames=args.frames, total_time=args.time)
    np.savez_compressed(args.output, **data)

    print(f"Successfully generated synthetic dataset: {args.output}")
    print(f"  Frames: {len(data['times'])}, Timespan: 0 to {data['times'][-1]*1e6:.1f} us")
    print(f"  Host:   {len(data['host_coords0'])} nodes, {len(data['host_conn_C3D8R'])} C3D8R hex elements")
    print(f"  Ball:   {len(data['ball_coords0'])} nodes, {len(data['ball_conn_C3D8R'])} C3D8R hex elements")
    print(f"  Fiber:  {len(data['fiber_coords0'])} nodes, {len(data['fiber_conn_T3D2'])} T3D2 line elements")
    eroded_final = np.sum(data['host_status'][-1] == 0)
    print(f"  Host eroded elements at final frame: {eroded_final}/{len(data['host_conn_C3D8R'])}")


if __name__ == "__main__":
    main()
