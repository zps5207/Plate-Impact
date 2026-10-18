#!/usr/bin/env python3
"""pack_viewer_data.py - Convert Abaqus ODB export (.npz) to WebGL viewer assets.

Converts an animation .npz file (with host, ball, fiber roles) into:
  1. manifest.json: frame counts, timestamps, bounding boxes, topology counts, camera presets.
  2. Raw little-endian binary files:
     - host_pos.f32:        Float32 [n_frames, n_host_nodes, 3]
     - ball_pos.f32:        Float32 [n_frames, n_ball_nodes, 3]
     - fiber_pos.f32:       Float32 [n_frames, n_fiber_nodes, 3]
     - host_status.u8:      Uint8   [n_frames, n_host_elements] (1 = alive, 0 = dead)
     - host_faces_e1.u32:   Uint32  [n_host_faces] (owner element)
     - host_faces_e2.i32:   Int32   [n_host_faces] (neighbor element, -1 if exterior)
     - host_faces_tris.u32: Uint32  [n_host_faces, 6] (2 triangles per face)
     - host_faces_edges.u32:Uint32  [n_host_faces, 8] (4 perimeter edges per face)
     - ball_faces_tris.u32: Uint32  [n_ball_tris * 3] (static exterior triangles)
     - ball_faces_edges.u32:Uint32  [n_ball_edges * 2] (static exterior edges)
     - fiber_lines.u32:     Uint32  [n_fiber_segments, 2] (static line segments)

Usage:
  python pack_viewer_data.py <file.npz> [--output <dir>]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

# Standard face node definitions matching odb_viewer.py
FACE_DEFS: dict[str, list[list[int]]] = {
    "C3D8R": [
        [0, 3, 2, 1],  # Bottom (-Z)
        [4, 5, 6, 7],  # Top (+Z)
        [0, 1, 5, 4],  # Front (-Y)
        [1, 2, 6, 5],  # Right (+X)
        [2, 3, 7, 6],  # Back (+Y)
        [3, 0, 4, 7],  # Left (-X)
    ],
    "C3D8": [
        [0, 3, 2, 1],
        [4, 5, 6, 7],
        [0, 1, 5, 4],
        [1, 2, 6, 5],
        [2, 3, 7, 6],
        [3, 0, 4, 7],
    ],
    "C3D6R": [
        [0, 1, 2],     # Triangular bottom
        [3, 5, 4],     # Triangular top
        [0, 1, 4, 3],  # Quad side 1
        [1, 2, 5, 4],  # Quad side 2
        [2, 0, 3, 5],  # Quad side 3
    ],
    "C3D6": [
        [0, 1, 2],
        [3, 5, 4],
        [0, 1, 4, 3],
        [1, 2, 5, 4],
        [2, 0, 3, 5],
    ],
    "C3D4": [
        [0, 1, 2],
        [0, 2, 3],
        [0, 3, 1],
        [1, 3, 2],
    ],
}


def cross_product(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return np.array([
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ], dtype=np.float64)


def compute_symmetry_camera(
    bounds_min: np.ndarray,
    bounds_max: np.ndarray,
    host_coords0: np.ndarray | None,
    ball_pos: np.ndarray | None,
    aspect: float = 16.0 / 9.0,
    margin: float = 0.08,
) -> dict[str, Any]:
    """Calculate the symmetry plane camera framing matching odb_viewer.py."""
    # 1. Identify plate thickness axis
    if host_coords0 is not None and len(host_coords0) > 0:
        p_min = host_coords0.min(axis=0)
        p_max = host_coords0.max(axis=0)
        thick = int(np.argmin(p_max - p_min))
    else:
        thick = 2

    # 2. Identify ball travel direction along the thickness axis
    travel_sign = -1.0
    if ball_pos is not None and len(ball_pos) > 1:
        b0_z = float(np.mean(ball_pos[0, :, thick]))
        blast_z = float(np.mean(ball_pos[-1, :, thick]))
        if blast_z > b0_z:
            travel_sign = 1.0

    # 3. Horizontal screen direction R points along ball travel (screen right)
    R = np.zeros(3, dtype=np.float64)
    R[thick] = travel_sign

    # 4. Vertical screen direction U points along plate lateral axis
    lateral = [a for a in range(3) if a != thick]
    other = lateral[0]  # Vertical axis on screen (e.g. X)
    normal = lateral[1] # Axis facing into screen (e.g. Y)

    U = np.zeros(3, dtype=np.float64)
    U[other] = 1.0

    # 5. View direction into screen V = U x R (so R = V x U)
    V = cross_product(U, R)
    v_norm = np.linalg.norm(V)
    if v_norm > 1e-9:
        V /= v_norm

    # 6. Fit extents with margin
    v_min, v_max = bounds_min[other], bounds_max[other]
    v_span = v_max - v_min
    v_center = (v_min + v_max) / 2.0

    h_min, h_max = bounds_min[thick], bounds_max[thick]
    h_span = h_max - h_min
    h_center = (h_min + h_max) / 2.0

    req_scale_v = (v_span / 2.0) * (1.0 + margin)
    req_scale_h = (h_span / (2.0 * aspect)) * (1.0 + margin)
    parallel_scale = max(req_scale_v, req_scale_h)

    # 7. Target focal point and camera position
    target = np.zeros(3, dtype=np.float64)
    target[other] = v_center
    target[thick] = h_center
    target[normal] = 0.0

    extent = float(np.max(bounds_max - bounds_min))
    distance = 3.0 * extent
    pos = target - distance * V

    return {
        "position": [float(v) for v in pos],
        "focal_point": [float(v) for v in target],
        "up": [float(v) for v in U],
        "parallel_scale": float(parallel_scale),
    }


def compute_iso_camera(
    bounds_min: np.ndarray,
    bounds_max: np.ndarray,
    margin_3d: float = 0.06,
    fov_degrees: float = 30.0,
) -> dict[str, Any]:
    """Calculate isometric camera preset matching odb_viewer.py (PyVista iso view)."""
    center = (bounds_min + bounds_max) / 2.0
    span = bounds_max - bounds_min
    m_min = bounds_min - span * margin_3d
    m_max = bounds_max + span * margin_3d
    diag = float(np.linalg.norm(m_max - m_min))

    # In VTK/PyVista reset_camera with bounds:
    # bounding sphere radius R = diag / 2.0
    # distance = R / sin(fov/2)
    fov_rad = np.radians(fov_degrees)
    distance = (diag / 2.0) / np.sin(fov_rad / 2.0)
    iso_dir = np.array([1.0, 1.0, 1.0], dtype=np.float64)
    iso_dir /= np.linalg.norm(iso_dir)

    pos = center + distance * iso_dir
    return {
        "position": [float(v) for v in pos],
        "focal_point": [float(v) for v in center],
        "up": [0.0, 0.0, 1.0],
        "fov": float(fov_degrees),
    }


def compute_reset_camera(
    bounds_min: np.ndarray,
    bounds_max: np.ndarray,
    margin_3d: float = 0.06,
    fov_degrees: float = 30.0,
) -> dict[str, Any]:
    """Calculate reset camera preset (scene bounding box view)."""
    center = (bounds_min + bounds_max) / 2.0
    span = bounds_max - bounds_min
    m_min = bounds_min - span * margin_3d
    m_max = bounds_max + span * margin_3d
    diag = float(np.linalg.norm(m_max - m_min))

    fov_rad = np.radians(fov_degrees)
    distance = (diag / 2.0) / np.sin(fov_rad / 2.0)
    # Looking towards +Y
    pos = center - np.array([0.0, distance, 0.0], dtype=np.float64)
    return {
        "position": [float(v) for v in pos],
        "focal_point": [float(v) for v in center],
        "up": [1.0, 0.0, 0.0],
        "fov": float(fov_degrees),
    }


def pack_data(npz_path: str | Path, output_dir: str | Path) -> dict[str, Any]:
    npz_path = Path(npz_path).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading {npz_path}...")
    t0 = time.time()
    raw = np.load(npz_path, allow_pickle=True)
    print(f"Loaded in {time.time() - t0:.2f} s")

    # 1. Times & Metadata
    times = np.asarray(raw["times"], dtype=np.float64) if "times" in raw else np.array([0.0], dtype=np.float64)
    n_frames = len(times)
    times_us = (times * 1.0e6).tolist()

    meta = {}
    if "meta" in raw:
        try:
            m_item = raw["meta"].item() if hasattr(raw["meta"], "item") else str(raw["meta"])
            meta = json.loads(m_item)
        except Exception:
            pass

    # 2. Host positions and status
    has_host = "host_coords0" in raw and "host_pos" in raw
    if has_host:
        host_coords0 = np.asarray(raw["host_coords0"], dtype=np.float32)
        host_pos = np.asarray(raw["host_pos"], dtype=np.float32)
        n_host_nodes = len(host_coords0)
    else:
        host_coords0 = np.zeros((0, 3), dtype=np.float32)
        host_pos = np.zeros((n_frames, 0, 3), dtype=np.float32)
        n_host_nodes = 0

    # Precompute Host Topology
    host_conn_keys = sorted([k for k in raw.files if k.startswith("host_conn_")])
    elem_offset = 0
    face_dict: dict[tuple[int, ...], list[tuple[int, list[int]]]] = {}

    for k in host_conn_keys:
        elem_type = k.replace("host_conn_", "")
        face_def = FACE_DEFS.get(elem_type, FACE_DEFS["C3D8R"])
        conn = np.asarray(raw[k], dtype=np.int32)
        n_elems = len(conn)
        for i in range(n_elems):
            elem_id = elem_offset + i
            elem_nodes = conn[i]
            for f_indices in face_def:
                f_nodes = [int(elem_nodes[idx]) for idx in f_indices]
                canonical_key = tuple(sorted(f_nodes))
                face_dict.setdefault(canonical_key, []).append((elem_id, f_nodes))
        elem_offset += n_elems

    total_host_elements = elem_offset
    if "host_status" in raw:
        host_status = np.asarray(raw["host_status"], dtype=np.uint8)
    else:
        host_status = np.ones((n_frames, total_host_elements), dtype=np.uint8)

    # Build unique face arrays: e1, e2, tris (2 per face), edges (4 per face)
    n_host_faces = len(face_dict)
    host_e1 = np.empty(n_host_faces, dtype=np.uint32)
    host_e2 = np.empty(n_host_faces, dtype=np.int32)
    host_tris = np.empty((n_host_faces, 6), dtype=np.uint32)
    host_edges = np.empty((n_host_faces, 8), dtype=np.uint32)

    for idx, (canonical_key, occ) in enumerate(face_dict.items()):
        e1 = occ[0][0]
        e2 = occ[1][0] if len(occ) > 1 else -1
        nodes = occ[0][1]

        host_e1[idx] = e1
        host_e2[idx] = e2

        if len(nodes) == 4:
            n0, n1, n2, n3 = nodes
            # 2 triangles for solid
            host_tris[idx] = [n0, n1, n2, n0, n2, n3]
            # 4 edges for wireframe
            host_edges[idx] = [n0, n1, n1, n2, n2, n3, n3, n0]
        elif len(nodes) == 3:
            n0, n1, n2 = nodes
            # 1 triangle, repeat last to fill 6 slots (degenerate 2nd tri)
            host_tris[idx] = [n0, n1, n2, n0, n1, n2]
            # 3 edges, repeat edge 0 for 4th slot
            host_edges[idx] = [n0, n1, n1, n2, n2, n0, n0, n1]
        else:
            raise ValueError(f"Unsupported face node count: {len(nodes)}")

    # 3. Ball positions and exterior topology
    has_ball = "ball_coords0" in raw and "ball_pos" in raw
    if has_ball:
        ball_coords0 = np.asarray(raw["ball_coords0"], dtype=np.float32)
        ball_pos = np.asarray(raw["ball_pos"], dtype=np.float32)
        n_ball_nodes = len(ball_coords0)
    else:
        ball_coords0 = np.zeros((0, 3), dtype=np.float32)
        ball_pos = np.zeros((n_frames, 0, 3), dtype=np.float32)
        n_ball_nodes = 0

    ball_conn_keys = sorted([k for k in raw.files if k.startswith("ball_conn_")])
    ball_face_dict: dict[tuple[int, ...], list[list[int]]] = {}
    for k in ball_conn_keys:
        elem_type = k.replace("ball_conn_", "")
        face_def = FACE_DEFS.get(elem_type, FACE_DEFS["C3D8R"])
        conn = np.asarray(raw[k], dtype=np.int32)
        for elem_nodes in conn:
            for f_indices in face_def:
                f_nodes = [int(elem_nodes[idx]) for idx in f_indices]
                canonical_key = tuple(sorted(f_nodes))
                ball_face_dict.setdefault(canonical_key, []).append(f_nodes)

    ball_ext_faces = [occ[0] for occ in ball_face_dict.values() if len(occ) == 1]
    ball_tri_list: list[int] = []
    ball_edge_set: set[tuple[int, int]] = set()

    for nodes in ball_ext_faces:
        if len(nodes) == 4:
            n0, n1, n2, n3 = nodes
            ball_tri_list.extend([n0, n1, n2, n0, n2, n3])
            edges = [(n0, n1), (n1, n2), (n2, n3), (n3, n0)]
        elif len(nodes) == 3:
            n0, n1, n2 = nodes
            ball_tri_list.extend([n0, n1, n2])
            edges = [(n0, n1), (n1, n2), (n2, n0)]
        else:
            edges = []

        for u, v in edges:
            if (min(u, v), max(u, v)) not in ball_edge_set:
                ball_edge_set.add((min(u, v), max(u, v)))

    ball_tris = np.array(ball_tri_list, dtype=np.uint32)
    ball_edges_list: list[int] = []
    for u, v in ball_edge_set:
        ball_edges_list.extend([u, v])
    ball_edges = np.array(ball_edges_list, dtype=np.uint32)

    # 4. Fiber positions and topology
    has_fiber = "fiber_coords0" in raw and "fiber_pos" in raw
    if has_fiber:
        fiber_coords0 = np.asarray(raw["fiber_coords0"], dtype=np.float32)
        fiber_pos = np.asarray(raw["fiber_pos"], dtype=np.float32)
        n_fiber_nodes = len(fiber_coords0)
    else:
        fiber_coords0 = np.zeros((0, 3), dtype=np.float32)
        fiber_pos = np.zeros((n_frames, 0, 3), dtype=np.float32)
        n_fiber_nodes = 0

    fiber_conn_keys = sorted([k for k in raw.files if k.startswith("fiber_conn_")])
    fiber_segments_list: list[int] = []
    for k in fiber_conn_keys:
        conn = np.asarray(raw[k], dtype=np.int32)
        if conn.ndim == 2 and conn.shape[1] >= 2:
            for row in conn:
                fiber_segments_list.extend([int(row[0]), int(row[1])])
    fiber_lines = np.array(fiber_segments_list, dtype=np.uint32)

    # 5. Global Animation Bounds (excluding debris from deleted elements, matching odb_viewer.py)
    mins, maxs = [], []
    if has_ball and len(ball_pos) > 0:
        mins.append(ball_pos.min(axis=(0, 1)))
        maxs.append(ball_pos.max(axis=(0, 1)))
    if has_fiber and len(fiber_pos) > 0:
        mins.append(fiber_pos.min(axis=(0, 1)))
        maxs.append(fiber_pos.max(axis=(0, 1)))
    if has_host and len(host_coords0) > 0:
        mins.append(host_coords0.min(axis=0))
        maxs.append(host_coords0.max(axis=0))
        # Sample frames to include deformed host bounds without deleted flying debris
        sample = np.unique(np.linspace(0, n_frames - 1, min(n_frames, 15)).astype(int))
        is_bnd = (host_e2 == -1)
        e2_safe = np.where(is_bnd, 0, host_e2)
        for f_idx in sample:
            st = host_status[f_idx]
            s1 = st[host_e1]
            s2 = st[e2_safe]
            vis = np.where(is_bnd, s1 == 1, s1 != s2)
            if np.any(vis):
                vis_tris = host_tris[vis].ravel()
                used_nodes = np.unique(vis_tris)
                p_used = host_pos[f_idx, used_nodes]
                mins.append(p_used.min(axis=0))
                maxs.append(p_used.max(axis=0))

    if mins:
        bounds_min = np.min(mins, axis=0).astype(np.float64)
        bounds_max = np.max(maxs, axis=0).astype(np.float64)
    else:
        bounds_min = np.array([-1.0, -1.0, -1.0], dtype=np.float64)
        bounds_max = np.array([1.0, 1.0, 1.0], dtype=np.float64)

    # Thickness axis
    if has_host and len(host_coords0) > 0:
        p_min = host_coords0.min(axis=0)
        p_max = host_coords0.max(axis=0)
        thick_axis = int(np.argmin(p_max - p_min))
    else:
        thick_axis = 2

    # Camera presets
    cam_iso = compute_iso_camera(bounds_min, bounds_max)
    cam_sym = compute_symmetry_camera(bounds_min, bounds_max, host_coords0 if has_host else None, ball_pos if has_ball else None)
    cam_reset = compute_reset_camera(bounds_min, bounds_max)

    camera_presets = {
        "iso": cam_iso,
        "symmetry": cam_sym,
        "reset": cam_reset,
    }

    # 6. Save binary files (little-endian raw buffers)
    print("Writing binary files to", output_dir)
    binary_files = {
        "host_pos": ("host_pos.f32", host_pos.astype("<f4")),
        "ball_pos": ("ball_pos.f32", ball_pos.astype("<f4")),
        "fiber_pos": ("fiber_pos.f32", fiber_pos.astype("<f4")),
        "host_status": ("host_status.u8", host_status.astype("u1")),
        "host_faces_e1": ("host_faces_e1.u32", host_e1.astype("<u4")),
        "host_faces_e2": ("host_faces_e2.i32", host_e2.astype("<i4")),
        "host_faces_tris": ("host_faces_tris.u32", host_tris.astype("<u4")),
        "host_faces_edges": ("host_faces_edges.u32", host_edges.astype("<u4")),
        "ball_faces_tris": ("ball_faces_tris.u32", ball_tris.astype("<u4")),
        "ball_faces_edges": ("ball_faces_edges.u32", ball_edges.astype("<u4")),
        "fiber_lines": ("fiber_lines.u32", fiber_lines.astype("<u4")),
    }

    file_manifest: dict[str, dict[str, Any]] = {}
    total_bytes = 0
    for key, (filename, arr) in binary_files.items():
        file_path = output_dir / filename
        with open(file_path, "wb") as f:
            f.write(arr.tobytes())
        file_size = os.path.getsize(file_path)
        total_bytes += file_size
        file_manifest[key] = {
            "filename": filename,
            "bytes": file_size,
            "shape": list(arr.shape),
            "dtype": str(arr.dtype),
        }
        print(f"  {filename:<22} {file_size / (1024*1024):6.2f} MB  (shape: {arr.shape})")

    # 7. Manifest JSON
    manifest = {
        "format": "plate_impact_viewer_manifest_v1",
        "odb": meta.get("odb", npz_path.name),
        "step": meta.get("step", "Step-1"),
        "n_frames": n_frames,
        "times_us": times_us,
        "fps": 30.0,
        "plate_thickness_axis": thick_axis,
        "bounds_min": [float(v) for v in bounds_min],
        "bounds_max": [float(v) for v in bounds_max],
        "camera_presets": camera_presets,
        "counts": {
            "host_nodes": n_host_nodes,
            "host_elements": total_host_elements,
            "host_faces": n_host_faces,
            "ball_nodes": n_ball_nodes,
            "ball_exterior_faces": len(ball_ext_faces),
            "ball_exterior_tris": len(ball_tri_list) // 3,
            "ball_exterior_edges": len(ball_edge_set),
            "fiber_nodes": n_fiber_nodes,
            "fiber_segments": len(fiber_segments_list) // 2,
        },
        "default_colors": {
            "host": "#8C8C8C",
            "fiber": "#0033CC",
            "ball": "#606060",
            "bg": "#FFFFFF",
        },
        "color_palettes": {
            "host": ["#8C8C8C", "#B0B0B0", "#E0E0E0", "#4A6B82", "#D28B47"],
            "fiber": ["#0033CC", "#D00000", "#008800", "#FFCC00", "#FFFFFF", "#FF00FF"],
            "ball": ["#606060", "#909090", "#C0C0C0", "#802020", "#202020"],
            "bg": ["#FFFFFF", "#1E1E1E", "#303030", "#D6E4F0", "#000000"],
        },
        "files": file_manifest,
        "total_binary_bytes": total_bytes,
        "total_binary_mb": round(total_bytes / (1024 * 1024), 2),
    }

    manifest_path = output_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"Manifest written to {manifest_path}")
    print(f"Total packed dataset size: {manifest['total_binary_mb']} MB across {len(binary_files)} files")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Pack Abaqus ODB NPZ export into browser WebGL assets.")
    parser.add_argument("npz_file", help="Path to input .npz file (e.g. v500_viewer.npz)")
    parser.add_argument("--output", "-o", default=None, help="Output directory (default: <npz_stem>_data)")
    args = parser.parse_args()

    npz_path = Path(args.npz_file)
    if not npz_path.is_file():
        sys.exit(f"Error: input file {npz_path} does not exist.")

    out_dir = Path(args.output) if args.output else npz_path.parent / f"{npz_path.stem}_data"
    pack_data(npz_path, out_dir)


if __name__ == "__main__":
    main()
