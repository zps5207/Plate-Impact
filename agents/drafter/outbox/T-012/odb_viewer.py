"""Interactive PyVista viewer for exported Abaqus ODB (.npz) impact animations.

================================================================================
README / KEYBOARD AND MOUSE CONTROLS
================================================================================

Playback Controls:
  Space, p       : Play / Pause toggle
  Left, [        : Step backward one frame (pauses if playing)
  Right, ]       : Step forward one frame (pauses if playing)
  Home, 0        : Jump to first frame (frame 0)
  End, 9, $      : Jump to last frame
  +, =           : Increase playback speed (0.25x -> 0.5x -> 1x -> 2x -> 4x -> 8x)
  -, _           : Decrease playback speed
  l              : Toggle loop on / off

Camera Presets (playback continues uninterrupted):
  1              : Isometric view preset
  2              : Symmetry plane preset (plate vertical, ball travels left to right)
  r, 3           : Reset camera (fit scene bounding box)

Render and Display Modes:
  h              : Cycle host render mode (wireframe -> solid -> hidden)
  f              : Toggle fibers-only mode (hides host, shows fibers and ball)
  b              : Cycle ball mode (wireframe -> solid -> hidden)
  o              : Cycle solid host opacity (1.0 -> 0.75 -> 0.50 -> 0.25)
  e              : Toggle edge overlay on solid host

Colors and Line Widths:
  c              : Cycle host color (Grey -> White -> Steel -> Amber)
  g              : Cycle fiber color (Blue -> Red -> Green -> Yellow -> White)
  k              : Cycle ball color (Dark Grey -> Silver -> Red -> Orange)
  C              : Cycle background color (White <-> Black <-> Dark Grey <-> Light Blue)
  w              : Increase fiber line width (+0.5 px)
  W              : Decrease fiber line width (-0.5 px)

Off-screen / Utilities:
  s              : Save screenshot of current frame (screenshot_frame_###.png)
  ?, /           : Toggle this on-screen help reference overlay

Mouse Interaction (active at all times, including during animation):
  Left Click + Drag  : Free 3D orbit around focal point
  Shift + Left Drag   : Pan view
  Middle Click + Drag : Pan view
  Right Click + Drag  : Zoom in / out
  Mouse Wheel Scroll  : Zoom in / out

================================================================================
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any

import numpy as np
import pyvista as pv


# ---------------------------------------------------------------------------
# Default Colors and Styling matching Abaqus Renders
# ---------------------------------------------------------------------------
DEFAULT_HOST_COLOR = "#8C8C8C"
DEFAULT_FIBER_COLOR = "#0033CC"
DEFAULT_BALL_COLOR = "#606060"
DEFAULT_BG_COLOR = "#FFFFFF"

COLOR_PALETTES = {
    "host": ["#8C8C8C", "#B0B0B0", "#E0E0E0", "#4A6B82", "#D28B47"],
    "fiber": ["#0033CC", "#D00000", "#008800", "#FFCC00", "#FFFFFF", "#FF00FF"],
    "ball": ["#606060", "#909090", "#C0C0C0", "#802020", "#202020"],
    "bg": ["#FFFFFF", "#1E1E1E", "#303030", "#D6E4F0", "#000000"],
}


# ---------------------------------------------------------------------------
# Element Face Definitions for Conformal Topology
# ---------------------------------------------------------------------------
# Local face node index definitions for standard solid 3D elements
FACE_DEFS: dict[str, list[list[int]]] = {
    # 8-node hexahedron (C3D8, C3D8R)
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
    # 6-node wedge / triangular prism (C3D6, C3D6R)
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
    # 4-node tetrahedron (C3D4)
    "C3D4": [
        [0, 1, 2],
        [0, 2, 3],
        [0, 3, 1],
        [1, 3, 2],
    ],
}


# ---------------------------------------------------------------------------
# ODB Data Loader and Precomputed Topology
# ---------------------------------------------------------------------------
class ODBData:
    """Loads and precomputes topology tables from an exported ODB .npz file."""

    def __init__(self, npz_path: str):
        if not os.path.isfile(npz_path):
            raise FileNotFoundError(f"ODB export file not found: {npz_path}")

        print(f"Loading {npz_path} into memory...")
        t0 = time.time()
        self.raw = np.load(npz_path, allow_pickle=True)
        print(f"Loaded in {time.time() - t0:.2f} s")

        # Parse times
        if "times" in self.raw:
            self.times = np.asarray(self.raw["times"], dtype=np.float64)
        else:
            self.times = np.array([0.0], dtype=np.float64)
        self.n_frames = len(self.times)

        # Parse metadata
        self.meta = {}
        if "meta" in self.raw:
            try:
                meta_item = self.raw["meta"].item() if hasattr(self.raw["meta"], "item") else str(self.raw["meta"])
                self.meta = json.loads(meta_item)
            except Exception:
                pass

        # Roles
        self.has_host = "host_coords0" in self.raw and "host_pos" in self.raw
        self.has_ball = "ball_coords0" in self.raw and "ball_pos" in self.raw
        self.has_fiber = "fiber_coords0" in self.raw and "fiber_pos" in self.raw

        # 1. Host Setup
        if self.has_host:
            self.host_coords0 = np.asarray(self.raw["host_coords0"], dtype=np.float32)
            self.host_pos = np.asarray(self.raw["host_pos"], dtype=np.float32)
            self._precompute_host_topology()
        else:
            self.host_coords0 = np.zeros((0, 3), dtype=np.float32)
            self.host_pos = np.zeros((self.n_frames, 0, 3), dtype=np.float32)

        # 2. Ball Setup
        if self.has_ball:
            self.ball_coords0 = np.asarray(self.raw["ball_coords0"], dtype=np.float32)
            self.ball_pos = np.asarray(self.raw["ball_pos"], dtype=np.float32)
            self._precompute_ball_topology()
        else:
            self.ball_coords0 = np.zeros((0, 3), dtype=np.float32)
            self.ball_pos = np.zeros((self.n_frames, 0, 3), dtype=np.float32)
            self.ball_faces = np.empty(0, dtype=np.int32)

        # 3. Fiber Setup
        if self.has_fiber:
            self.fiber_coords0 = np.asarray(self.raw["fiber_coords0"], dtype=np.float32)
            self.fiber_pos = np.asarray(self.raw["fiber_pos"], dtype=np.float32)
            self._precompute_fiber_topology()
        else:
            self.fiber_coords0 = np.zeros((0, 3), dtype=np.float32)
            self.fiber_pos = np.zeros((self.n_frames, 0, 3), dtype=np.float32)
            self.fiber_lines = np.empty(0, dtype=np.int32)

    def _precompute_host_topology(self) -> None:
        """Precompute face tables and element neighborhood for the host mesh."""
        # Find all host connectivity keys
        host_conn_keys = sorted([
            k for k in self.raw.files if k.startswith("host_conn_")
        ])

        elem_offset = 0
        face_dict: dict[tuple[int, ...], list[tuple[int, list[int]]]] = {}

        for k in host_conn_keys:
            elem_type = k.replace("host_conn_", "")
            face_def = FACE_DEFS.get(elem_type, FACE_DEFS["C3D8R"])
            conn = np.asarray(self.raw[k], dtype=np.int32)
            n_elems = len(conn)

            for i in range(n_elems):
                elem_id = elem_offset + i
                elem_nodes = conn[i]
                for f_indices in face_def:
                    f_nodes = [int(elem_nodes[idx]) for idx in f_indices]
                    canonical_key = tuple(sorted(f_nodes))
                    face_dict.setdefault(canonical_key, []).append((elem_id, f_nodes))

            elem_offset += n_elems

        self.total_host_elements = elem_offset

        # Parse or default host_status
        if "host_status" in self.raw:
            self.host_status = np.asarray(self.raw["host_status"], dtype=np.uint8)
        else:
            print("Notice: 'host_status' not found in file; defaulting all elements to alive (1)")
            self.host_status = np.ones((self.n_frames, self.total_host_elements), dtype=np.uint8)

        # Separate faces into quads (4 nodes) and triangles (3 nodes)
        quad_nodes_list = []
        quad_e1_list = []
        quad_e2_list = []

        tri_nodes_list = []
        tri_e1_list = []
        tri_e2_list = []

        for occ in face_dict.values():
            e1 = occ[0][0]
            e2 = occ[1][0] if len(occ) > 1 else -1
            nodes = occ[0][1]

            if len(nodes) == 4:
                quad_nodes_list.append(nodes)
                quad_e1_list.append(e1)
                quad_e2_list.append(e2)
            elif len(nodes) == 3:
                tri_nodes_list.append(nodes)
                tri_e1_list.append(e1)
                tri_e2_list.append(e2)

        # Pre-build NumPy arrays for fast array-masking
        self.n_quads = len(quad_nodes_list)
        if self.n_quads > 0:
            quad_nodes = np.array(quad_nodes_list, dtype=np.int32)
            self.quad_pv_cells = np.empty((self.n_quads, 5), dtype=np.int32)
            self.quad_pv_cells[:, 0] = 4
            self.quad_pv_cells[:, 1:] = quad_nodes

            self.quad_e1 = np.array(quad_e1_list, dtype=np.int32)
            self.quad_e2 = np.array(quad_e2_list, dtype=np.int32)
            self.quad_is_bnd = (self.quad_e2 == -1)
            self.quad_e2_safe = np.where(self.quad_is_bnd, 0, self.quad_e2)
        else:
            self.quad_pv_cells = np.empty((0, 5), dtype=np.int32)
            self.quad_e1 = np.empty(0, dtype=np.int32)
            self.quad_e2_safe = np.empty(0, dtype=np.int32)
            self.quad_is_bnd = np.empty(0, dtype=bool)

        self.n_tris = len(tri_nodes_list)
        if self.n_tris > 0:
            tri_nodes = np.array(tri_nodes_list, dtype=np.int32)
            self.tri_pv_cells = np.empty((self.n_tris, 4), dtype=np.int32)
            self.tri_pv_cells[:, 0] = 3
            self.tri_pv_cells[:, 1:] = tri_nodes

            self.tri_e1 = np.array(tri_e1_list, dtype=np.int32)
            self.tri_e2 = np.array(tri_e2_list, dtype=np.int32)
            self.tri_is_bnd = (self.tri_e2 == -1)
            self.tri_e2_safe = np.where(self.tri_is_bnd, 0, self.tri_e2)
        else:
            self.tri_pv_cells = np.empty((0, 4), dtype=np.int32)
            self.tri_e1 = np.empty(0, dtype=np.int32)
            self.tri_e2_safe = np.empty(0, dtype=np.int32)
            self.tri_is_bnd = np.empty(0, dtype=bool)

        print(f"Host mesh: {len(self.host_coords0)} nodes, {self.total_host_elements} elements, "
              f"{self.n_quads + self.n_tris} unique faces precomputed")

    def get_host_faces(self, frame_idx: int) -> np.ndarray:
        """Return PyVista face array representing exposed exterior faces for the frame.

        Performs fast vectorized array masking only:
        - Boundary face (e2 == -1): drawn iff status[e1] == 1
        - Interior face (e2 != -1): drawn iff status[e1] != status[e2]
        """
        if not self.has_host or self.total_host_elements == 0:
            return np.empty(0, dtype=np.int32)

        status = self.host_status[frame_idx]
        pieces = []

        if self.n_quads > 0:
            s1 = status[self.quad_e1]
            s2 = status[self.quad_e2_safe]
            vis_quad = np.where(self.quad_is_bnd, s1 == 1, s1 != s2)
            if np.any(vis_quad):
                pieces.append(self.quad_pv_cells[vis_quad].ravel())

        if self.n_tris > 0:
            s1 = status[self.tri_e1]
            s2 = status[self.tri_e2_safe]
            vis_tri = np.where(self.tri_is_bnd, s1 == 1, s1 != s2)
            if np.any(vis_tri):
                pieces.append(self.tri_pv_cells[vis_tri].ravel())

        if pieces:
            return np.concatenate(pieces)
        return np.empty(0, dtype=np.int32)

    def _precompute_ball_topology(self) -> None:
        """Precompute exterior boundary faces for the ball (static topology)."""
        ball_conn_keys = sorted([
            k for k in self.raw.files if k.startswith("ball_conn_")
        ])

        face_dict: dict[tuple[int, ...], list[list[int]]] = {}
        for k in ball_conn_keys:
            elem_type = k.replace("ball_conn_", "")
            face_def = FACE_DEFS.get(elem_type, FACE_DEFS["C3D8R"])
            conn = np.asarray(self.raw[k], dtype=np.int32)
            for elem_nodes in conn:
                for f_indices in face_def:
                    f_nodes = [int(elem_nodes[idx]) for idx in f_indices]
                    canonical_key = tuple(sorted(f_nodes))
                    face_dict.setdefault(canonical_key, []).append(f_nodes)

        # Exterior faces only (shared by exactly 1 element)
        exterior_cells = []
        for occ in face_dict.values():
            if len(occ) == 1:
                nodes = occ[0]
                exterior_cells.append([len(nodes)] + nodes)

        if exterior_cells:
            # Flatten into 1D array
            flat_faces = []
            for cell in exterior_cells:
                flat_faces.extend(cell)
            self.ball_faces = np.array(flat_faces, dtype=np.int32)
        else:
            self.ball_faces = np.empty(0, dtype=np.int32)

        print(f"Ball mesh: {len(self.ball_coords0)} nodes, "
              f"{len(exterior_cells)} exterior faces precomputed")

    def _precompute_fiber_topology(self) -> None:
        """Precompute line segments for fiber truss elements (T3D2)."""
        fiber_conn_keys = sorted([
            k for k in self.raw.files if k.startswith("fiber_conn_")
        ])

        segments = []
        for k in fiber_conn_keys:
            conn = np.asarray(self.raw[k], dtype=np.int32)
            if conn.ndim == 2 and conn.shape[1] >= 2:
                for row in conn:
                    segments.append([2, int(row[0]), int(row[1])])

        if segments:
            flat_lines = []
            for seg in segments:
                flat_lines.extend(seg)
            self.fiber_lines = np.array(flat_lines, dtype=np.int32)
        else:
            self.fiber_lines = np.empty(0, dtype=np.int32)

        print(f"Fiber mesh: {len(self.fiber_coords0)} nodes, "
              f"{len(segments)} line segments precomputed")


# ---------------------------------------------------------------------------
# Camera Presets Logic
# ---------------------------------------------------------------------------
def cross_product(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return np.array([
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ], dtype=np.float64)


def compute_symmetry_camera(
    data: ODBData, aspect: float = 16.0 / 9.0, scale: float = 1.0
) -> dict[str, Any]:
    """Calculate the symmetry plane camera framing.

    Orchestrates the view such that the plate is a vertical band and the ball
    travels left to right across the screen, matching verification/roar/render_ghost_failure.py.
    """
    if not data.has_host or not data.has_ball or len(data.host_coords0) == 0 or len(data.ball_coords0) == 0:
        # Fallback to standard side view
        return {
            "position": [0.0, -100.0, 0.0],
            "focal_point": [0.0, 0.0, 0.0],
            "up": [0.0, 0.0, 1.0],
            "parallel_scale": 15.0,
        }

    pmin = np.min(data.host_coords0, axis=0).astype(np.float64)
    pmax = np.max(data.host_coords0, axis=0).astype(np.float64)
    bmin = np.min(data.ball_coords0, axis=0).astype(np.float64)
    bmax = np.max(data.ball_coords0, axis=0).astype(np.float64)

    thick = int(np.argmin(pmax - pmin))
    center = (bmin + bmax) / 2.0
    radius = float(np.max(bmax - bmin) / 2.0)
    lateral = [a for a in range(3) if a != thick]
    up_sign = 1.0 if center[thick] > (pmin[thick] + pmax[thick]) / 2.0 else -1.0
    far_face = pmin[thick] if up_sign > 0 else pmax[thick]
    top = center[thick] + up_sign * radius
    low = far_face - up_sign * radius

    width = 1.15 * abs(top - low) * scale
    height = width / aspect
    extent = float(np.max(pmax - pmin))
    distance = 3.0 * extent
    travel = np.zeros(3, dtype=np.float64)
    travel[thick] = -up_sign

    options = []
    for normal in sorted(lateral, key=lambda a: min(abs(center[a] - pmin[a]), abs(center[a] - pmax[a]))):
        other = [a for a in lateral if a != normal][0]
        at_min = abs(center[normal] - pmin[normal]) <= abs(center[normal] - pmax[normal])
        side = -1.0 if at_min else 1.0
        plate_dir = 1.0 if (center[other] - pmin[other]) <= (pmax[other] - center[other]) else -1.0
        view_dir = np.zeros(3, dtype=np.float64)
        view_dir[normal] = -side

        for up_along in (1.0, -1.0):
            up = np.zeros(3, dtype=np.float64)
            up[other] = up_along
            right = cross_product(view_dir, up)
            if right[thick] * travel[thick] > 0:
                plate_up = (up_along == plate_dir)
                options.append((not plate_up, len(options), normal, other, at_min, side, plate_dir, up))

    if not options:
        # Fallback
        return {
            "position": [float(center[0]), float(center[1] - distance), float(center[2])],
            "focal_point": [float(center[0]), float(center[1]), float(center[2])],
            "up": [0.0, 0.0, 1.0],
            "parallel_scale": float(height / 2.0),
        }

    options.sort(key=lambda o: (o[0], o[1]))
    _, _, normal, other, at_min, side, plate_dir, up = options[0]

    target = np.zeros(3, dtype=np.float64)
    target[thick] = (low + top) / 2.0
    target[other] = center[other] + plate_dir * (height / 2.0 - 1.5 * radius)
    target[normal] = pmin[normal] if at_min else pmax[normal]

    position = target.copy()
    position[normal] += side * distance

    return {
        "position": [float(v) for v in position],
        "focal_point": [float(v) for v in target],
        "up": [float(v) for v in up],
        "parallel_scale": float(height / 2.0),
    }


# ---------------------------------------------------------------------------
# Interactive PyVista Plotter / Animation Controller
# ---------------------------------------------------------------------------
class ODBViewer:
    """Manages PyVista Plotter, interactive animation loop, and controls."""

    def __init__(self, data: ODBData, args: argparse.Namespace):
        self.data = data
        self.args = args

        # State
        self.current_frame = 0
        self.is_playing = True
        self.speed = float(args.speed)
        self.loop = not args.no_loop
        self.fps = float(args.fps)
        self.last_step_time = time.time()
        self.show_help = False

        # Display settings
        self.host_mode = args.host_mode  # 'wireframe', 'solid', 'hidden'
        self.fibers_only = args.fibers_only
        self.ball_mode = args.ball_mode    # 'wireframe', 'solid', 'hidden'
        self.host_opacity = float(args.host_opacity)
        self.host_edges = args.host_edges

        # Colors & line widths
        self.host_color = args.host_color
        self.fiber_color = args.fiber_color
        self.ball_color = args.ball_color
        self.bg_color = args.bg_color
        self.host_line_width = float(args.host_line_width)
        self.fiber_line_width = float(args.fiber_line_width)
        self.ball_line_width = float(args.ball_line_width)

        self._updating_slider = False

        # Create Plotter
        self.plotter = pv.Plotter(off_screen=args.off_screen, window_size=(1280, 720))
        self.plotter.set_background(self.bg_color)

        # Build PyVista meshes
        self._init_meshes()

        # Add actors
        self._init_actors()

        # Set initial frame
        self.set_frame(0)

        # Apply initial camera preset
        self.apply_camera_preset(args.camera_preset)

        # Setup Widgets & Keys
        if not args.off_screen:
            self._setup_ui()
            self._setup_keys()
            self._setup_timer()

    def _init_meshes(self) -> None:
        """Create PyVista PolyData meshes."""
        # Host
        if self.data.has_host and len(self.data.host_coords0) > 0:
            init_faces = self.data.get_host_faces(0)
            self.host_mesh = pv.PolyData(self.data.host_coords0.copy(), faces=init_faces)
        else:
            self.host_mesh = None

        # Ball
        if self.data.has_ball and len(self.data.ball_coords0) > 0:
            self.ball_mesh = pv.PolyData(self.data.ball_coords0.copy(), faces=self.data.ball_faces)
        else:
            self.ball_mesh = None

        # Fiber
        if self.data.has_fiber and len(self.data.fiber_coords0) > 0:
            self.fiber_mesh = pv.PolyData(self.data.fiber_coords0.copy(), lines=self.data.fiber_lines)
        else:
            self.fiber_mesh = None

    def _init_actors(self) -> None:
        """Add meshes to Plotter with initial styles and line widths."""
        # Host
        if self.host_mesh is not None:
            self.host_actor = self.plotter.add_mesh(
                self.host_mesh,
                color=self.host_color,
                style="wireframe" if self.host_mode == "wireframe" else "surface",
                line_width=self.host_line_width,
                opacity=self.host_opacity if self.host_mode == "solid" else 1.0,
                show_edges=self.host_edges,
                edge_color="#303030",
                reset_camera=False,
            )
            self._update_host_style()
        else:
            self.host_actor = None

        # Ball
        if self.ball_mesh is not None:
            self.ball_actor = self.plotter.add_mesh(
                self.ball_mesh,
                color=self.ball_color,
                style="wireframe" if self.ball_mode == "wireframe" else "surface",
                line_width=self.ball_line_width,
                reset_camera=False,
            )
            self._update_ball_style()
        else:
            self.ball_actor = None

        # Fiber
        if self.fiber_mesh is not None:
            self.fiber_actor = self.plotter.add_mesh(
                self.fiber_mesh,
                color=self.fiber_color,
                line_width=self.fiber_line_width,
                reset_camera=False,
            )
        else:
            self.fiber_actor = None

    def _setup_ui(self) -> None:
        """Add time label, hint bar, and slider widget."""
        # Top-left time label
        self._update_time_label()

        # Bottom hint banner
        hint_text = "[Space] Play/Pause | [1] Iso | [2] Symmetry | [h] Host mode | [f] Fibers | [?] Help"
        text_color = "black" if self._is_bg_light() else "white"
        self.plotter.add_text(
            hint_text,
            name="hint_banner",
            position="lower_right",
            font_size=9,
            color=text_color,
        )

        # Frame scrub slider along bottom
        if self.data.n_frames > 1:
            self.slider = self.plotter.add_slider_widget(
                callback=self._on_slider_change,
                rng=[0, self.data.n_frames - 1],
                value=0,
                title="Frame",
                pointa=(0.20, 0.05),
                pointb=(0.80, 0.05),
                style="modern",
                slider_width=0.02,
                tube_width=0.005,
                title_height=0.025,
            )
        else:
            self.slider = None

    def _setup_keys(self) -> None:
        """Bind interactive keyboard controls."""
        p = self.plotter
        # Playback
        p.add_key_event("space", self.toggle_play)
        p.add_key_event("p", self.toggle_play)
        p.add_key_event("Left", lambda: self.step_frame(-1))
        p.add_key_event("bracketleft", lambda: self.step_frame(-1))
        p.add_key_event("Right", lambda: self.step_frame(1))
        p.add_key_event("bracketright", lambda: self.step_frame(1))
        p.add_key_event("Home", lambda: self.set_frame(0))
        p.add_key_event("0", lambda: self.set_frame(0))
        p.add_key_event("End", lambda: self.set_frame(self.data.n_frames - 1))
        p.add_key_event("9", lambda: self.set_frame(self.data.n_frames - 1))
        p.add_key_event("plus", lambda: self.adjust_speed(2.0))
        p.add_key_event("equal", lambda: self.adjust_speed(2.0))
        p.add_key_event("minus", lambda: self.adjust_speed(0.5))
        p.add_key_event("l", self.toggle_loop)

        # Camera
        p.add_key_event("1", lambda: self.apply_camera_preset("iso"))
        p.add_key_event("2", lambda: self.apply_camera_preset("symmetry"))
        p.add_key_event("3", lambda: self.apply_camera_preset("reset"))
        p.add_key_event("r", lambda: self.apply_camera_preset("reset"))

        # Render Modes
        p.add_key_event("h", self.cycle_host_mode)
        p.add_key_event("f", self.toggle_fibers_only)
        p.add_key_event("b", self.cycle_ball_mode)
        p.add_key_event("o", self.cycle_host_opacity)
        p.add_key_event("e", self.toggle_host_edges)

        # Styling
        p.add_key_event("c", lambda: self.cycle_color("host"))
        p.add_key_event("g", lambda: self.cycle_color("fiber"))
        p.add_key_event("k", lambda: self.cycle_color("ball"))
        p.add_key_event("C", lambda: self.cycle_color("bg"))
        p.add_key_event("w", lambda: self.adjust_fiber_line_width(0.5))
        p.add_key_event("W", lambda: self.adjust_fiber_line_width(-0.5))

        # Utilities
        p.add_key_event("s", self.save_interactive_screenshot)
        p.add_key_event("question", self.toggle_help_overlay)
        p.add_key_event("slash", self.toggle_help_overlay)

    def _setup_timer(self) -> None:
        """Register the high-frequency playback timer."""
        # 15 ms tick rate allows up to 60+ fps smooth playback
        self.plotter.add_timer_event(max_steps=1_000_000_000, duration=15, callback=self._on_timer)

    def _is_bg_light(self) -> bool:
        """Check if background color is light or dark for contrasting text."""
        try:
            c = pv.Color(self.bg_color)
            lum = 0.299 * c.red + 0.587 * c.green + 0.114 * c.blue
            return lum > 128
        except Exception:
            return True

    def _update_time_label(self) -> None:
        """Update top-left HUD label with current time in microseconds."""
        t_sec = float(self.data.times[self.current_frame])
        t_us = t_sec * 1.0e6
        status_str = "PLAYING" if self.is_playing else "PAUSED"
        host_str = "hidden" if (self.fibers_only or self.host_mode == "hidden") else self.host_mode
        fib_str = "ONLY" if self.fibers_only else "ON"

        text = (
            f"Time: {t_us:6.2f} \u03bcs  |  Frame: {self.current_frame + 1:3d}/{self.data.n_frames}  "
            f"|  Speed: {self.speed:.2f}x  [{status_str}]\n"
            f"Host: {host_str:<9} |  Fibers: {fib_str:<4} |  Ball: {self.ball_mode:<9}"
        )
        text_color = "black" if self._is_bg_light() else "white"
        self.plotter.add_text(
            text,
            name="time_label",
            position="upper_left",
            font_size=10,
            font="courier",
            color=text_color,
        )

    def _update_host_style(self) -> None:
        """Update host actor visibility, wireframe/surface style, opacity and edges."""
        if self.host_actor is None:
            return
        if self.fibers_only or self.host_mode == "hidden":
            self.host_actor.SetVisibility(False)
        else:
            self.host_actor.SetVisibility(True)
            if self.host_mode == "wireframe":
                self.host_actor.prop.style = "wireframe"
                self.host_actor.prop.line_width = self.host_line_width
                self.host_actor.prop.opacity = 1.0
                self.host_actor.prop.show_edges = False
            elif self.host_mode == "solid":
                self.host_actor.prop.style = "surface"
                self.host_actor.prop.opacity = self.host_opacity
                self.host_actor.prop.show_edges = self.host_edges

    def _update_ball_style(self) -> None:
        """Update ball actor visibility and style."""
        if self.ball_actor is None:
            return
        if self.ball_mode == "hidden":
            self.ball_actor.SetVisibility(False)
        else:
            self.ball_actor.SetVisibility(True)
            self.ball_actor.prop.style = "wireframe" if self.ball_mode == "wireframe" else "surface"
            self.ball_actor.prop.line_width = self.ball_line_width

    def set_frame(self, frame_idx: int) -> None:
        """Update all meshes and UI to the specified frame index in place."""
        self.current_frame = max(0, min(frame_idx, self.data.n_frames - 1))

        # 1. Update Host Mesh
        if self.host_mesh is not None:
            self.host_mesh.points[:] = self.data.host_pos[self.current_frame]
            # Update exterior face visibility (array masking only)
            if not (self.fibers_only or self.host_mode == "hidden"):
                self.host_mesh.faces = self.data.get_host_faces(self.current_frame)
            self.host_mesh.Modified()

        # 2. Update Ball Mesh
        if self.ball_mesh is not None:
            self.ball_mesh.points[:] = self.data.ball_pos[self.current_frame]
            self.ball_mesh.Modified()

        # 3. Update Fiber Mesh
        if self.fiber_mesh is not None:
            self.fiber_mesh.points[:] = self.data.fiber_pos[self.current_frame]
            self.fiber_mesh.Modified()

        # 4. Update Slider
        if hasattr(self, "slider") and self.slider is not None:
            self._updating_slider = True
            try:
                self.slider.GetRepresentation().SetValue(self.current_frame)
            finally:
                self._updating_slider = False

        # 5. Update Time Label
        self._update_time_label()

    def _on_slider_change(self, value: float) -> None:
        """Callback for slider widget interaction."""
        if self._updating_slider:
            return
        frame = int(round(value))
        if frame != self.current_frame:
            self.set_frame(frame)
            self.plotter.render()

    def _on_timer(self, _step: int) -> None:
        """Animation timer step."""
        if not self.is_playing or self.data.n_frames <= 1:
            return

        now = time.time()
        dt = now - self.last_step_time
        target_interval = 1.0 / (self.fps * self.speed)

        if dt >= target_interval:
            frames_to_advance = max(1, int(dt / target_interval))
            next_frame = self.current_frame + frames_to_advance

            if next_frame >= self.data.n_frames:
                if self.loop:
                    next_frame = next_frame % self.data.n_frames
                else:
                    next_frame = self.data.n_frames - 1
                    self.is_playing = False

            self.set_frame(next_frame)
            self.last_step_time = now

    # -----------------------------------------------------------------------
    # Interactive Actions & Key Handlers
    # -----------------------------------------------------------------------
    def toggle_play(self) -> None:
        """Toggle animation playback."""
        self.is_playing = not self.is_playing
        self.last_step_time = time.time()
        self._update_time_label()
        self.plotter.render()

    def step_frame(self, delta: int) -> None:
        """Step animation forward or backward by delta frames."""
        self.is_playing = False
        target = (self.current_frame + delta) % self.data.n_frames
        self.set_frame(target)
        self.plotter.render()

    def adjust_speed(self, factor: float) -> None:
        """Scale playback speed."""
        new_speed = self.speed * factor
        if 0.1 <= new_speed <= 32.0:
            self.speed = new_speed
            self._update_time_label()
            self.plotter.render()

    def toggle_loop(self) -> None:
        """Toggle animation loop."""
        self.loop = not self.loop
        self.plotter.render()

    def apply_camera_preset(self, preset: str) -> None:
        """Switch camera to isometric, symmetry-plane, or scene reset."""
        p = self.plotter
        if preset == "iso":
            p.disable_parallel_projection()
            p.view_isometric()
        elif preset == "symmetry":
            aspect = float(p.window_size[0]) / float(p.window_size[1])
            cam = compute_symmetry_camera(self.data, aspect=aspect, scale=1.0)
            p.enable_parallel_projection()
            p.camera.parallel_scale = cam["parallel_scale"]
            p.camera.position = cam["position"]
            p.camera.focal_point = cam["focal_point"]
            p.camera.up = cam["up"]
        elif preset == "reset":
            p.disable_parallel_projection()
            p.reset_camera()
        p.render()

    def cycle_host_mode(self) -> None:
        """Cycle host render mode (wireframe -> solid -> hidden)."""
        modes = ["wireframe", "solid", "hidden"]
        idx = (modes.index(self.host_mode) + 1) % len(modes)
        self.host_mode = modes[idx]
        self.fibers_only = False
        self._update_host_style()
        # Refresh face masking if switching out of hidden
        if self.host_mesh is not None and self.host_mode != "hidden":
            self.host_mesh.faces = self.data.get_host_faces(self.current_frame)
            self.host_mesh.Modified()
        self._update_time_label()
        self.plotter.render()

    def toggle_fibers_only(self) -> None:
        """Toggle fibers only mode (hiding host)."""
        self.fibers_only = not self.fibers_only
        self._update_host_style()
        if self.host_mesh is not None and not self.fibers_only and self.host_mode != "hidden":
            self.host_mesh.faces = self.data.get_host_faces(self.current_frame)
            self.host_mesh.Modified()
        self._update_time_label()
        self.plotter.render()

    def cycle_ball_mode(self) -> None:
        """Cycle ball render mode (wireframe -> solid -> hidden)."""
        modes = ["wireframe", "solid", "hidden"]
        idx = (modes.index(self.ball_mode) + 1) % len(modes)
        self.ball_mode = modes[idx]
        self._update_ball_style()
        self._update_time_label()
        self.plotter.render()

    def cycle_host_opacity(self) -> None:
        """Cycle solid host opacity."""
        opacities = [1.0, 0.75, 0.50, 0.25]
        curr = round(self.host_opacity, 2)
        idx = 0
        for i, val in enumerate(opacities):
            if abs(curr - val) < 0.05:
                idx = (i + 1) % len(opacities)
                break
        self.host_opacity = opacities[idx]
        if self.host_mode == "solid":
            self._update_host_style()
            self.plotter.render()

    def toggle_host_edges(self) -> None:
        """Toggle edge overlay on solid host."""
        self.host_edges = not self.host_edges
        if self.host_mode == "solid":
            self._update_host_style()
            self.plotter.render()

    def cycle_color(self, target: str) -> None:
        """Cycle color for host, fiber, ball, or background."""
        palette = COLOR_PALETTES.get(target, [])
        if not palette:
            return

        if target == "host" and self.host_actor is not None:
            idx = (palette.index(self.host_color) + 1) % len(palette) if self.host_color in palette else 0
            self.host_color = palette[idx]
            self.host_actor.prop.color = self.host_color
        elif target == "fiber" and self.fiber_actor is not None:
            idx = (palette.index(self.fiber_color) + 1) % len(palette) if self.fiber_color in palette else 0
            self.fiber_color = palette[idx]
            self.fiber_actor.prop.color = self.fiber_color
        elif target == "ball" and self.ball_actor is not None:
            idx = (palette.index(self.ball_color) + 1) % len(palette) if self.ball_color in palette else 0
            self.ball_color = palette[idx]
            self.ball_actor.prop.color = self.ball_color
        elif target == "bg":
            idx = (palette.index(self.bg_color) + 1) % len(palette) if self.bg_color in palette else 0
            self.bg_color = palette[idx]
            self.plotter.set_background(self.bg_color)
            self._update_time_label()

        self.plotter.render()

    def adjust_fiber_line_width(self, delta: float) -> None:
        """Adjust fiber line width."""
        new_w = max(0.5, min(10.0, self.fiber_line_width + delta))
        self.fiber_line_width = new_w
        if self.fiber_actor is not None:
            self.fiber_actor.prop.line_width = new_w
            self.plotter.render()

    def save_interactive_screenshot(self) -> None:
        """Save screenshot from within the interactive viewer."""
        filename = f"screenshot_frame_{self.current_frame:03d}.png"
        self.plotter.screenshot(filename)
        print(f"Saved interactive screenshot: {filename}")

    def toggle_help_overlay(self) -> None:
        """Toggle on-screen keybindings help reference."""
        self.show_help = not self.show_help
        if self.show_help:
            help_box = (
                "+-------------------------------------------------------------+\n"
                "| KEYBOARD CONTROLS REFERENCE                                |\n"
                "+-------------------------------------------------------------+\n"
                "| Space / p  : Play / Pause animation                         |\n"
                "| Left / [   : Step backward 1 frame                          |\n"
                "| Right / ]  : Step forward 1 frame                           |\n"
                "| Home / 0   : Jump to frame 0                                |\n"
                "| End / 9    : Jump to last frame                             |\n"
                "| + / -      : Increase / decrease playback speed             |\n"
                "| l          : Toggle animation looping                       |\n"
                "| 1          : Preset: Isometric view                         |\n"
                "| 2          : Preset: Symmetry plane (plate vert, ball L->R) |\n"
                "| r / 3      : Preset: Reset camera view                      |\n"
                "| h          : Cycle host mode (wireframe -> solid -> hidden) |\n"
                "| f          : Toggle fibers-only mode                        |\n"
                "| b          : Cycle ball mode (wireframe -> solid -> hidden) |\n"
                "| o          : Cycle solid host opacity (1.0 -> 0.25)         |\n"
                "| e          : Toggle solid host edge overlay                 |\n"
                "| c / g / k  : Cycle color (host / fiber / ball)              |\n"
                "| C          : Cycle background color                         |\n"
                "| w / W      : Increase / decrease fiber line width           |\n"
                "| s          : Save screenshot of current frame               |\n"
                "| ? / /      : Close this help overlay                        |\n"
                "+-------------------------------------------------------------+"
            )
            text_color = "black" if self._is_bg_light() else "white"
            self.plotter.add_text(
                help_box,
                name="help_box",
                position="lower_left",
                font_size=9,
                font="courier",
                color=text_color,
            )
        else:
            self.plotter.remove_actor("help_box")
        self.plotter.render()

    # -----------------------------------------------------------------------
    # Headless Exports: MP4 and Screenshot
    # -----------------------------------------------------------------------
    def export_mp4(self, output_path: str) -> None:
        """Render all frames offscreen to an MP4 video file."""
        print(f"Exporting MP4 to {output_path} ({self.data.n_frames} frames at {self.fps} fps)...")
        # Ensure dimensions divisible by 16 for standard codec compatibility
        self.plotter.window_size = (1280, 720)
        self.plotter.open_movie(output_path, framerate=int(round(self.fps)))

        try:
            for idx in range(self.data.n_frames):
                self.set_frame(idx)
                self.plotter.render()
                self.plotter.write_frame()
                if (idx + 1) % 10 == 0 or idx + 1 == self.data.n_frames:
                    print(f"  Frame {idx + 1}/{self.data.n_frames} rendered")
        finally:
            self.plotter.close()
        print(f"Successfully wrote MP4 video: {output_path}")

    def export_screenshot(self, frame_idx: int, output_path: str) -> None:
        """Render single frame offscreen to a PNG image file."""
        self.set_frame(frame_idx)
        self.plotter.render()
        self.plotter.screenshot(output_path)
        print(f"Saved screenshot: {output_path} (Frame {frame_idx})")


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Interactive PyVista viewer for exported Abaqus ODB (.npz) impact animations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("npz_file", help="Path to exported .npz file")

    # Display & Modes
    parser.add_argument("--host-mode", choices=["wireframe", "solid", "hidden"], default="wireframe",
                        help="Initial host render mode (default: wireframe)")
    parser.add_argument("--ball-mode", choices=["wireframe", "solid", "hidden"], default="wireframe",
                        help="Initial ball render mode (default: wireframe)")
    parser.add_argument("--fibers-only", action="store_true",
                        help="Start with host hidden and fibers & ball visible")
    parser.add_argument("--host-opacity", type=float, default=1.0,
                        help="Host opacity in solid mode (0.0 to 1.0, default: 1.0)")
    parser.add_argument("--host-edges", action="store_true",
                        help="Overlay element edges on solid host")

    # Colors & Line Widths
    parser.add_argument("--host-color", default=DEFAULT_HOST_COLOR,
                        help=f"Host color hex code (default: {DEFAULT_HOST_COLOR})")
    parser.add_argument("--fiber-color", default=DEFAULT_FIBER_COLOR,
                        help=f"Fiber color hex code (default: {DEFAULT_FIBER_COLOR})")
    parser.add_argument("--ball-color", default=DEFAULT_BALL_COLOR,
                        help=f"Ball color hex code (default: {DEFAULT_BALL_COLOR})")
    parser.add_argument("--bg-color", "--background", default=DEFAULT_BG_COLOR,
                        help=f"Background color hex code (default: {DEFAULT_BG_COLOR})")
    parser.add_argument("--host-line-width", type=float, default=1.0,
                        help="Host wireframe line width in pixels (default: 1.0)")
    parser.add_argument("--fiber-line-width", type=float, default=2.0,
                        help="Fiber line width in pixels (default: 2.0)")
    parser.add_argument("--ball-line-width", type=float, default=1.0,
                        help="Ball wireframe line width in pixels (default: 1.0)")

    # Camera & Playback
    parser.add_argument("--camera-preset", "--view", choices=["iso", "symmetry", "reset"], default="iso",
                        help="Initial camera preset (default: iso)")
    parser.add_argument("--speed", type=float, default=1.0,
                        help="Initial playback speed multiplier (default: 1.0)")
    parser.add_argument("--fps", type=float, default=30.0,
                        help="Target playback and export frame rate (default: 30.0)")
    parser.add_argument("--no-loop", action="store_true",
                        help="Disable continuous animation looping")

    # Exports & Headless
    parser.add_argument("--save-mp4", metavar="OUT.MP4",
                        help="Render animation offscreen to MP4 video and exit")
    parser.add_argument("--screenshot", nargs="+", metavar=("FRAME", "OUT.PNG"),
                        help="Render single frame offscreen to PNG image: --screenshot FRAME OUT_FILE (or --screenshot OUT_FILE for frame 0)")
    parser.add_argument("--off-screen", action="store_true",
                        help="Run Plotter offscreen without opening interactive window")

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Load data
    data = ODBData(args.npz_file)

    # Check export options
    if args.save_mp4 or args.screenshot:
        args.off_screen = True

    viewer = ODBViewer(data, args)

    if args.save_mp4:
        viewer.export_mp4(args.save_mp4)
        return

    if args.screenshot:
        if len(args.screenshot) == 1:
            frame_idx = 0
            out_path = args.screenshot[0]
        else:
            frame_idx = int(args.screenshot[0])
            out_path = args.screenshot[1]
        viewer.export_screenshot(frame_idx, out_path)
        return

    if not args.off_screen:
        print("Launching PyVista interactive viewer. Orbit with mouse drag, press '?' for help.")
        viewer.plotter.show()


if __name__ == "__main__":
    main()
