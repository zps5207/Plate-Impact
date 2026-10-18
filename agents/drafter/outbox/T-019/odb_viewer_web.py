"""Trame Web Front-End for Abaqus ODB Impact Visualizations.

Provides a browser-based user interface using Trame (Vue 3 / Vuetify 3) and VTK/PyVista
for interactive playback, scrubbing, camera manipulation, and styling of exported
Abaqus ODB impact simulation datasets (.npz).

Usage:
    python odb_viewer_web.py file.npz [--port 8080] [--no-browser]
"""
from __future__ import annotations

import argparse
import asyncio
import math
import os
import sys
import time
from pathlib import Path
from typing import Any

import imageio.v2 as imageio
import numpy as np
import pyvista as pv

if sys.platform == "win32":
    import ctypes
    try:
        ctypes.windll.winmm.timeBeginPeriod(1)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Dynamic Path Resolution & Import of verification/roar/odb_viewer.py
# ---------------------------------------------------------------------------
def setup_viewer_import(viewer_dir: str | None = None) -> None:
    """Locate and add verification/roar to sys.path, then import odb_viewer.

    Resolution strategy:
    1. If --viewer-dir is provided, verify odb_viewer.py exists there and use it.
    2. Otherwise, check candidate paths relative to this script and cwd.
    3. If not found, raise an informative ImportError.
    """
    candidates: list[Path] = []
    if viewer_dir:
        candidates.append(Path(viewer_dir).resolve())

    script_path = Path(__file__).resolve()
    # Check upward traversal from script location:
    candidates.extend([
        (script_path.parent / "../../../../verification/roar").resolve(),
        (script_path.parent / "../../../verification/roar").resolve(),
        (script_path.parent / "../../verification/roar").resolve(),
        (script_path.parent / "../verification/roar").resolve(),
        (Path.cwd() / "verification/roar").resolve(),
        (Path.cwd() / "../verification/roar").resolve(),
        (Path.cwd() / "../../verification/roar").resolve(),
    ])

    found: Path | None = None
    for cand in candidates:
        if (cand / "odb_viewer.py").is_file():
            found = cand
            break

    if found is None:
        searched_str = "\n  - ".join(str(p) for p in candidates)
        raise ImportError(
            f"Could not locate odb_viewer.py in candidate locations:\n  - {searched_str}\n"
            f"Please specify the directory containing odb_viewer.py using --viewer-dir <path>."
        )

    sys.path.insert(0, str(found))


# Perform path setup before importing odb_viewer
_temp_parser = argparse.ArgumentParser(add_help=False)
_temp_parser.add_argument("--viewer-dir", default=None)
_temp_args, _ = _temp_parser.parse_known_args()
setup_viewer_import(_temp_args.viewer_dir)

import odb_viewer  # type: ignore[import-not-found]
from trame.app import get_server
from trame.ui.vuetify3 import SinglePageWithDrawerLayout
from trame.widgets import html
from trame.widgets import vtk as vtk_widgets
from trame.widgets import vuetify3 as v3




# ---------------------------------------------------------------------------
# Web Viewer Controller wrapping ODBViewer
# ---------------------------------------------------------------------------
class ODBWebViewer(odb_viewer.ODBViewer):
    """Subclass of desktop ODBViewer adapted for headless server-side web rendering."""

    def __init__(self, data: odb_viewer.ODBData, args: argparse.Namespace):
        # Force off_screen=True so PyVista initializes headless OpenGL context
        args.off_screen = True
        super().__init__(data, args)
        self.view_update_fn = None

    def set_host_mode(self, mode: str) -> None:
        """Update host display mode (wireframe, solid, hidden)."""
        if mode not in ("wireframe", "solid", "hidden"):
            return
        self.host_mode = mode
        self.fibers_only = False
        self._update_host_style()
        if self.host_mesh is not None and self.host_mode != "hidden":
            self.host_mesh.faces = self.data.get_host_faces(self.current_frame)
            self.host_mesh.Modified()
        self._update_time_label()
        self.plotter.render()
        if self.view_update_fn:
            self.view_update_fn()

    def set_fibers_only(self, enabled: bool) -> None:
        """Toggle fibers-only mode (hiding host mesh)."""
        self.fibers_only = bool(enabled)
        self._update_host_style()
        if self.host_mesh is not None and not self.fibers_only and self.host_mode != "hidden":
            self.host_mesh.faces = self.data.get_host_faces(self.current_frame)
            self.host_mesh.Modified()
        self._update_time_label()
        self.plotter.render()
        if self.view_update_fn:
            self.view_update_fn()

    def set_ball_mode(self, mode: str) -> None:
        """Update ball display mode (wireframe, solid, hidden)."""
        if mode not in ("wireframe", "solid", "hidden"):
            return
        self.ball_mode = mode
        self._update_ball_style()
        self._update_time_label()
        self.plotter.render()
        if self.view_update_fn:
            self.view_update_fn()

    def set_host_opacity(self, opacity: float) -> None:
        """Set solid host opacity."""
        self.host_opacity = float(opacity)
        if self.host_mode == "solid":
            self._update_host_style()
            self.plotter.render()
            if self.view_update_fn:
                self.view_update_fn()

    def set_host_edges(self, edges: bool) -> None:
        """Toggle element edges on solid host."""
        self.host_edges = bool(edges)
        if self.host_mode == "solid":
            self._update_host_style()
            self.plotter.render()
            if self.view_update_fn:
                self.view_update_fn()

    def set_color(self, target: str, color_hex: str) -> None:
        """Set color for host, fiber, ball, or background."""
        if target == "host" and self.host_actor is not None:
            self.host_color = color_hex
            self.host_actor.prop.color = color_hex
        elif target == "fiber" and self.fiber_actor is not None:
            self.fiber_color = color_hex
            self.fiber_actor.prop.color = color_hex
        elif target == "ball" and self.ball_actor is not None:
            self.ball_color = color_hex
            self.ball_actor.prop.color = color_hex
        elif target == "bg":
            self.bg_color = color_hex
            self.plotter.set_background(color_hex)
            self._update_time_label()
        self.plotter.render()
        if self.view_update_fn:
            self.view_update_fn()

    def set_line_width(self, target: str, width: float) -> None:
        """Set wireframe / fiber line width."""
        w = max(0.5, min(10.0, float(width)))
        if target == "fiber" and self.fiber_actor is not None:
            self.fiber_line_width = w
            self.fiber_actor.prop.line_width = w
        elif target == "host" and self.host_actor is not None:
            self.host_line_width = w
            self.host_actor.prop.line_width = w
        elif target == "ball" and self.ball_actor is not None:
            self.ball_line_width = w
            self.ball_actor.prop.line_width = w
        self.plotter.render()
        if self.view_update_fn:
            self.view_update_fn()

    def apply_preset(self, preset: str) -> None:
        """Apply camera preset (iso, symmetry, reset) and push view update."""
        self.apply_camera_preset(preset)
        if self.view_update_fn:
            self.view_update_fn()


# ---------------------------------------------------------------------------
# Trame Application & UI Builder
# ---------------------------------------------------------------------------
def format_time_label(times: np.ndarray, frame: int, n_frames: int) -> str:
    """Format time in microseconds and frame counter."""
    t_sec = float(times[frame]) if frame < len(times) else 0.0
    t_us = t_sec * 1.0e6
    return f"{t_us:6.2f} \u03bcs (Frame {frame + 1}/{n_frames})"


def create_app(data: odb_viewer.ODBData, args: argparse.Namespace):
    """Instantiate the Trame application, UI layout, and animation task."""
    viewer = ODBWebViewer(data, args)
    server = get_server(client_type="vue3")
    state, ctrl = server.state, server.controller

    # Initial state
    state.frame = 0
    state.n_frames = data.n_frames
    state.time_label = format_time_label(data.times, 0, data.n_frames)
    state.playing = False
    state.speed = float(args.speed)
    state.speed_options = [0.25, 0.5, 1.0, 2.0, 4.0, 8.0]
    state.loop = not args.no_loop

    # Display options
    state.host_mode = args.host_mode
    state.host_mode_options = ["wireframe", "solid", "hidden"]
    state.fibers_only = args.fibers_only
    state.ball_mode = args.ball_mode
    state.ball_mode_options = ["wireframe", "solid", "hidden"]
    state.host_opacity = float(args.host_opacity)
    state.host_edges = bool(args.host_edges)

    # Colors
    state.host_color = args.host_color
    state.fiber_color = args.fiber_color
    state.ball_color = args.ball_color
    state.bg_color = args.bg_color

    # Palettes for quick pick
    state.host_palette = odb_viewer.COLOR_PALETTES.get("host", ["#8C8C8C", "#B0B0B0", "#E0E0E0", "#4A6B82", "#D28B47"])
    state.fiber_palette = odb_viewer.COLOR_PALETTES.get("fiber", ["#0033CC", "#D00000", "#008800", "#FFCC00", "#FFFFFF"])
    state.ball_palette = odb_viewer.COLOR_PALETTES.get("ball", ["#606060", "#909090", "#C0C0C0", "#802020", "#202020"])
    state.bg_palette = odb_viewer.COLOR_PALETTES.get("bg", ["#FFFFFF", "#1E1E1E", "#303030", "#D6E4F0", "#000000"])

    # Line widths
    state.host_line_width = float(args.host_line_width)
    state.fiber_line_width = float(args.fiber_line_width)
    state.ball_line_width = float(args.ball_line_width)

    # Recording configuration and state
    recordings_dir = Path.cwd() / "recordings"
    recordings_dir.mkdir(parents=True, exist_ok=True)
    server.serve["recordings"] = str(recordings_dir)

    stem = Path(args.npz_file).stem if hasattr(args, "npz_file") and args.npz_file else "animation"
    timestamp_default = time.strftime("%Y%m%d_%H%M%S")
    default_rec_filename = f"{stem}_{timestamp_default}.mp4"

    state.record_dialog = False
    state.record_resolution = "1280x720 (720p HD)"
    state.record_resolution_options = [
        "1280x720 (720p HD)",
        "1920x1080 (1080p FHD)",
        "Current Aspect (Window Size)",
        "854x480 (480p SD)",
    ]
    state.record_fps = 30
    state.record_fps_options = [15, 24, 30, 60]
    state.record_start_frame = 1
    state.record_end_frame = data.n_frames
    state.record_filename = default_rec_filename
    state.record_include_time_overlay = True

    state.is_recording = False
    state.record_cancelled = False
    state.record_progress = 0
    state.record_status = ""
    state.record_download_ready = False
    state.record_download_url = ""
    state.record_download_name = ""

    html_view = None

    def set_stream_quality(quality: int, ratio: float = 1.0):
        if html_view is not None and hasattr(html_view, "_helper") and html_view._helper:
            try:
                html_view._helper.set_image_quality(viewer.plotter.render_window, quality, ratio)
            except Exception:
                pass

    # Control functions
    def toggle_play():
        viewer.is_playing = not state.playing
        if not viewer.is_playing:
            set_stream_quality(95, 1.0)
            ctrl.view_update()
        else:
            set_stream_quality(75, 0.5)
        with state:
            state.playing = not state.playing
            if state.playing and viewer.current_frame >= data.n_frames - 1 and not state.loop:
                viewer.set_frame(0)
                state.frame = 0
                state.time_label = format_time_label(data.times, 0, data.n_frames)
                viewer.plotter.render()
                ctrl.view_update()

    def step_back():
        viewer.is_playing = False
        set_stream_quality(95, 1.0)
        new_frame = (viewer.current_frame - 1) % data.n_frames
        viewer.set_frame(new_frame)
        with state:
            state.playing = False
            state.frame = new_frame
            state.time_label = format_time_label(data.times, new_frame, data.n_frames)
        viewer.plotter.render()
        ctrl.view_update()

    def step_forward():
        viewer.is_playing = False
        set_stream_quality(95, 1.0)
        new_frame = (viewer.current_frame + 1) % data.n_frames
        viewer.set_frame(new_frame)
        with state:
            state.playing = False
            state.frame = new_frame
            state.time_label = format_time_label(data.times, new_frame, data.n_frames)
        viewer.plotter.render()
        ctrl.view_update()

    def cam_iso():
        viewer.apply_preset("iso")

    def cam_symmetry():
        viewer.apply_preset("symmetry")

    def cam_reset():
        viewer.apply_preset("reset")

    # Helper functions for Recording & Aspect Ratio Compensation
    def parse_resolution(choice: str, current_w: int, current_h: int) -> tuple[int, int]:
        if "1920x1080" in choice:
            return 1920, 1080
        elif "1280x720" in choice:
            return 1280, 720
        elif "854x480" in choice:
            return 854, 480
        elif "Current" in choice:
            w = current_w - (current_w % 2)
            h = current_h - (current_h % 2)
            return max(320, w), max(240, h)
        else:
            try:
                parts = choice.split()[0].split("x")
                w = int(parts[0])
                h = int(parts[1])
                return max(320, w - (w % 2)), max(240, h - (h % 2))
            except Exception:
                return 1280, 720

    def compute_compensated_camera(orig_w: int, orig_h: int, target_w: int, target_h: int) -> dict[str, Any]:
        """Calculate aspect-ratio compensated camera parameters.

        VTK maintains a constant vertical field of view (view_angle for perspective)
        or constant parallel_scale (for parallel projection).
        If the target aspect ratio (target_w / target_h) is narrower than the original
        window aspect ratio (orig_w / orig_h), keeping the same vertical FOV would cause
        the left and right sides of the scene to be cropped.
        To ensure the subject remains fully visible without horizontal cropping:
            tan(theta_y_out / 2) = tan(theta_y_in / 2) * (ar_in / ar_out)
        For parallel projection:
            parallel_scale_out = parallel_scale_in * (ar_in / ar_out)
        """
        ar_in = float(orig_w) / float(orig_h) if orig_h > 0 else 1.0
        ar_out = float(target_w) / float(target_h) if target_h > 0 else 1.0

        is_parallel = viewer.plotter.camera.parallel_projection
        orig_angle = viewer.plotter.camera.view_angle
        orig_scale = viewer.plotter.camera.parallel_scale

        if is_parallel:
            if ar_out < ar_in:
                new_scale = orig_scale * (ar_in / ar_out)
            else:
                new_scale = orig_scale
            return {"parallel": True, "scale": new_scale, "angle": orig_angle}
        else:
            if ar_out < ar_in:
                half_angle_rad = math.radians(orig_angle / 2.0)
                tan_half_out = math.tan(half_angle_rad) * (ar_in / ar_out)
                new_angle = 2.0 * math.degrees(math.atan(tan_half_out))
                new_angle = min(170.0, new_angle)
            else:
                new_angle = orig_angle
            return {"parallel": False, "scale": orig_scale, "angle": new_angle}

    async def run_recording_task():
        if state.is_recording:
            return

        with state:
            state.is_recording = True
            state.record_cancelled = False
            state.record_download_ready = False
            state.record_progress = 0
            state.record_status = "Initializing offscreen recorder..."

        # 1. Capture live playback and camera state
        was_playing = state.playing
        state.playing = False
        viewer.is_playing = False

        orig_frame = viewer.current_frame
        orig_w, orig_h = viewer.plotter.render_window.GetSize()
        orig_pos = list(viewer.plotter.camera.position)
        orig_focal = list(viewer.plotter.camera.focal_point)
        orig_up = list(viewer.plotter.camera.up)
        orig_clipping = list(viewer.plotter.camera.clipping_range)
        orig_angle = viewer.plotter.camera.view_angle
        orig_parallel = viewer.plotter.camera.parallel_projection
        orig_scale = viewer.plotter.camera.parallel_scale

        # 2. Determine output path and resolution
        target_w, target_h = parse_resolution(state.record_resolution, orig_w, orig_h)
        fps = int(state.record_fps) if int(state.record_fps) > 0 else 30

        raw_filename = (state.record_filename or "").strip()
        if not raw_filename:
            raw_filename = f"{stem}_{time.strftime('%Y%m%d_%H%M%S')}.mp4"
        if not raw_filename.lower().endswith(".mp4"):
            raw_filename += ".mp4"
        raw_filename = Path(raw_filename).name
        out_path = recordings_dir / raw_filename

        try:
            start_frame_user = int(state.record_start_frame)
        except Exception:
            start_frame_user = 1
        try:
            end_frame_user = int(state.record_end_frame)
        except Exception:
            end_frame_user = data.n_frames

        start_idx = max(0, min(data.n_frames - 1, start_frame_user - 1))
        end_idx = max(0, min(data.n_frames - 1, end_frame_user - 1))
        if start_idx > end_idx:
            start_idx, end_idx = end_idx, start_idx

        total_frames = end_idx - start_idx + 1
        with state:
            state.record_status = f"Rendering {total_frames} frames ({target_w}x{target_h} @ {fps} fps)..."
        await asyncio.sleep(0.001)

        # 3. Setup offscreen window & camera compensation
        viewer.plotter.render_window.SetSize(target_w, target_h)
        cam_comp = compute_compensated_camera(orig_w, orig_h, target_w, target_h)
        viewer.plotter.camera.position = orig_pos
        viewer.plotter.camera.focal_point = orig_focal
        viewer.plotter.camera.up = orig_up
        viewer.plotter.camera.clipping_range = orig_clipping
        if cam_comp["parallel"]:
            viewer.plotter.enable_parallel_projection()
            viewer.plotter.camera.parallel_scale = cam_comp["scale"]
        else:
            viewer.plotter.disable_parallel_projection()
            viewer.plotter.camera.view_angle = cam_comp["angle"]

        writer = None
        cancelled = False
        rendered_count = 0
        text_color = "black" if viewer._is_bg_light() else "white"

        try:
            writer = imageio.get_writer(
                str(out_path),
                fps=fps,
                format="mp4",
                codec="libx264",
                pixelformat="yuv420p",
            )

            for f_idx in range(start_idx, end_idx + 1):
                if state.record_cancelled:
                    cancelled = True
                    break

                viewer.set_frame(f_idx)

                if state.record_include_time_overlay:
                    t_sec = float(data.times[f_idx]) if f_idx < len(data.times) else 0.0
                    t_us = t_sec * 1.0e6
                    overlay_str = f"Time: {t_us:6.2f} \u03bcs  |  Frame: {f_idx + 1:3d}/{data.n_frames}"
                    viewer.plotter.add_text(
                        overlay_str,
                        name="record_time_label",
                        position="upper_left",
                        font_size=11,
                        font="courier",
                        color=text_color,
                    )
                else:
                    viewer.plotter.remove_actor("record_time_label")

                viewer.plotter.render()
                frame_img = viewer.plotter.screenshot(return_img=True)
                writer.append_data(frame_img)
                rendered_count += 1

                progress_pct = int(round((rendered_count / total_frames) * 100))
                state.record_progress = progress_pct
                state.record_status = (
                    f"Frame {f_idx + 1}/{end_idx + 1} rendered ({progress_pct}%)"
                )
                await asyncio.sleep(0.001)

        except Exception as e:
            print(f"[Record] Error during recording: {e}", file=sys.stderr)
            state.record_status = f"Error during recording: {e}"
            cancelled = True
        finally:
            if writer is not None:
                try:
                    writer.close()
                except Exception:
                    pass

            try:
                viewer.plotter.remove_actor("record_time_label")
            except Exception:
                pass

            viewer.plotter.render_window.SetSize(orig_w, orig_h)
            viewer.plotter.camera.position = orig_pos
            viewer.plotter.camera.focal_point = orig_focal
            viewer.plotter.camera.up = orig_up
            viewer.plotter.camera.clipping_range = orig_clipping
            if orig_parallel:
                viewer.plotter.enable_parallel_projection()
                viewer.plotter.camera.parallel_scale = orig_scale
            else:
                viewer.plotter.disable_parallel_projection()
                viewer.plotter.camera.view_angle = orig_angle

            viewer.set_frame(orig_frame)
            with state:
                state.frame = orig_frame
                state.time_label = format_time_label(data.times, orig_frame, data.n_frames)
                state.is_recording = False

                if cancelled:
                    state.record_status = "Recording cancelled."
                    state.record_progress = 0
                    state.record_download_ready = False
                else:
                    state.record_status = f"Saved: {raw_filename} ({total_frames} frames)"
                    state.record_progress = 100
                    state.record_download_ready = True
                    state.record_download_url = f"/recordings/{raw_filename}"
                    state.record_download_name = raw_filename

            if cancelled:
                if out_path.exists():
                    try:
                        out_path.unlink()
                    except Exception:
                        pass
                print(f"[Record] Cancelled by user. Cleaned up {out_path.name}", flush=True)
            else:
                abs_saved = out_path.resolve()
                print(f"[Record] Video successfully saved to: {abs_saved}", flush=True)

            if was_playing and not cancelled:
                state.playing = True
                viewer.is_playing = True

            set_stream_quality(95, 1.0)
            viewer.plotter.render()
            ctrl.view_update()

    async def run_screenshot_task():
        orig_w, orig_h = viewer.plotter.render_window.GetSize()
        orig_pos = list(viewer.plotter.camera.position)
        orig_focal = list(viewer.plotter.camera.focal_point)
        orig_up = list(viewer.plotter.camera.up)
        orig_clipping = list(viewer.plotter.camera.clipping_range)
        orig_angle = viewer.plotter.camera.view_angle
        orig_parallel = viewer.plotter.camera.parallel_projection
        orig_scale = viewer.plotter.camera.parallel_scale

        target_w, target_h = parse_resolution(state.record_resolution, orig_w, orig_h)
        f_idx = viewer.current_frame
        snap_filename = f"{stem}_frame_{f_idx + 1:03d}_{time.strftime('%Y%m%d_%H%M%S')}.png"
        snap_path = recordings_dir / snap_filename

        state.record_status = f"Saving screenshot to {snap_filename}..."
        await asyncio.sleep(0.001)

        try:
            viewer.plotter.render_window.SetSize(target_w, target_h)
            cam_comp = compute_compensated_camera(orig_w, orig_h, target_w, target_h)
            viewer.plotter.camera.position = orig_pos
            viewer.plotter.camera.focal_point = orig_focal
            viewer.plotter.camera.up = orig_up
            viewer.plotter.camera.clipping_range = orig_clipping
            if cam_comp["parallel"]:
                viewer.plotter.enable_parallel_projection()
                viewer.plotter.camera.parallel_scale = cam_comp["scale"]
            else:
                viewer.plotter.disable_parallel_projection()
                viewer.plotter.camera.view_angle = cam_comp["angle"]

            text_color = "black" if viewer._is_bg_light() else "white"
            if state.record_include_time_overlay:
                t_sec = float(data.times[f_idx]) if f_idx < len(data.times) else 0.0
                t_us = t_sec * 1.0e6
                overlay_str = f"Time: {t_us:6.2f} \u03bcs  |  Frame: {f_idx + 1:3d}/{data.n_frames}"
                viewer.plotter.add_text(
                    overlay_str,
                    name="record_time_label",
                    position="upper_left",
                    font_size=11,
                    font="courier",
                    color=text_color,
                )
            else:
                viewer.plotter.remove_actor("record_time_label")

            viewer.plotter.render()
            viewer.plotter.screenshot(str(snap_path))
            abs_snap = snap_path.resolve()
            print(f"[Snapshot] Image saved to: {abs_snap}", flush=True)
            with state:
                state.record_status = f"Snapshot saved: {snap_filename}"
                state.record_download_ready = True
                state.record_download_url = f"/recordings/{snap_filename}"
                state.record_download_name = snap_filename
                state.record_dialog = True
        except Exception as e:
            print(f"[Snapshot] Error taking screenshot: {e}", file=sys.stderr, flush=True)
            state.record_status = f"Snapshot error: {e}"
        finally:
            try:
                viewer.plotter.remove_actor("record_time_label")
            except Exception:
                pass
            viewer.plotter.render_window.SetSize(orig_w, orig_h)
            viewer.plotter.camera.position = orig_pos
            viewer.plotter.camera.focal_point = orig_focal
            viewer.plotter.camera.up = orig_up
            viewer.plotter.camera.clipping_range = orig_clipping
            if orig_parallel:
                viewer.plotter.enable_parallel_projection()
                viewer.plotter.camera.parallel_scale = orig_scale
            else:
                viewer.plotter.disable_parallel_projection()
                viewer.plotter.camera.view_angle = orig_angle
            set_stream_quality(95, 1.0)
            viewer.plotter.render()
            ctrl.view_update()

    def on_start_recording():
        if state.is_recording:
            return
        asyncio.create_task(run_recording_task())

    def on_cancel_recording():
        if state.is_recording:
            state.record_cancelled = True
            state.record_status = "Cancelling recording..."

    ctrl.toggle_play = toggle_play
    ctrl.step_back = step_back
    ctrl.step_forward = step_forward
    ctrl.cam_iso = cam_iso
    ctrl.cam_symmetry = cam_symmetry
    ctrl.cam_reset = cam_reset
    ctrl.start_recording = on_start_recording
    ctrl.cancel_recording = on_cancel_recording
    ctrl.take_screenshot = lambda: asyncio.create_task(run_screenshot_task())

    # Build Layout
    with SinglePageWithDrawerLayout(server, width=340, show_drawer=True) as layout:
        layout.title.set_text("ODB Impact Web Viewer")

        # Top Control Bar (Playback & Presets)
        with layout.toolbar:
            # Play / Pause
            with v3.VBtn(
                click=ctrl.toggle_play,
                variant="elevated",
                color="primary",
                density="comfortable",
                classes="mx-1",
            ):
                v3.VIcon(
                    "mdi-pause",
                    v_if="playing",
                    classes="mr-1",
                )
                v3.VIcon(
                    "mdi-play",
                    v_if="!playing",
                    classes="mr-1",
                )
                html.Span("Pause", v_if="playing")
                html.Span("Play", v_if="!playing")

            # Step Backward / Forward
            with v3.VBtn(
                click=ctrl.step_back,
                icon=True,
                variant="text",
                density="comfortable",
                classes="mx-1",
            ):
                v3.VIcon("mdi-step-backward")

            with v3.VBtn(
                click=ctrl.step_forward,
                icon=True,
                variant="text",
                density="comfortable",
                classes="mx-1",
            ):
                v3.VIcon("mdi-step-forward")

            # Frame scrub slider
            with html.Div(style="width: 280px; min-width: 180px;", classes="mx-3 mt-4"):
                v3.VSlider(
                    v_model=("frame", 0),
                    min=0,
                    max=data.n_frames - 1,
                    step=1,
                    density="compact",
                    hide_details=True,
                )

            # Microsecond timestamp badge
            html.Span(
                "{{ time_label }}",
                classes="text-body-2 font-weight-bold mx-2 text-mono",
                style="white-space: nowrap; font-family: monospace;",
            )

            # Speed select
            with html.Div(style="width: 100px;", classes="mx-2 mt-4"):
                v3.VSelect(
                    v_model=("speed", 1.0),
                    items=("speed_options",),
                    label="Speed",
                    density="compact",
                    hide_details=True,
                    variant="outlined",
                )

            # Loop toggle button
            with v3.VBtn(
                click="loop = !loop",
                icon=True,
                variant="tonal",
                density="comfortable",
                classes="mx-1",
            ):
                v3.VIcon("mdi-repeat", v_if="loop", color="primary")
                v3.VIcon("mdi-repeat-off", v_if="!loop", color="grey")

            v3.VSpacer()

            # Camera Preset Buttons
            v3.VBtn(
                "Iso",
                click=ctrl.cam_iso,
                prepend_icon="mdi-cube-outline",
                variant="outlined",
                density="compact",
                classes="mx-1",
            )
            v3.VBtn(
                "Symmetry",
                click=ctrl.cam_symmetry,
                prepend_icon="mdi-axis-arrow",
                variant="outlined",
                density="compact",
                classes="mx-1",
            )
            v3.VBtn(
                "Reset",
                click=ctrl.cam_reset,
                prepend_icon="mdi-camera-retake-outline",
                variant="outlined",
                density="compact",
                classes="mx-1",
            )

            v3.VDivider(vertical=True, classes="mx-2")

            # Snapshot button
            v3.VBtn(
                "Snapshot",
                click=ctrl.take_screenshot,
                prepend_icon="mdi-camera",
                variant="outlined",
                density="compact",
                classes="mx-1",
            )

            # Record button
            v3.VBtn(
                "Record",
                click="record_dialog = true",
                prepend_icon="mdi-video",
                variant="elevated",
                color="error",
                density="compact",
                classes="mx-1",
            )

        # Side Drawer (Display Modes, Styling, Colors, Line Widths)
        with layout.drawer:
            with v3.VContainer(classes="pa-3"):
                html.H4("Display & Render Options", classes="font-weight-bold mb-3")

                # Section 1: Modes
                v3.VSelect(
                    v_model=("host_mode", "wireframe"),
                    items=("host_mode_options",),
                    label="Host Mode",
                    density="compact",
                    variant="outlined",
                    classes="mb-2",
                )

                v3.VSwitch(
                    v_model=("fibers_only", False),
                    label="Fibers Only",
                    density="compact",
                    color="primary",
                    hide_details=True,
                    classes="mb-2",
                )

                v3.VSelect(
                    v_model=("ball_mode", "wireframe"),
                    items=("ball_mode_options",),
                    label="Ball Mode",
                    density="compact",
                    variant="outlined",
                    classes="mb-3",
                )

                v3.VDivider(classes="my-3")
                html.H4("Host Solid Style", classes="font-weight-bold mb-2")

                html.Div("Host Opacity: {{ host_opacity }}", classes="text-caption mb-1")
                v3.VSlider(
                    v_model=("host_opacity", 1.0),
                    min=0.0,
                    max=1.0,
                    step=0.05,
                    density="compact",
                    hide_details=True,
                    classes="mb-3",
                )

                v3.VSwitch(
                    v_model=("host_edges", False),
                    label="Show Host Edges",
                    density="compact",
                    color="primary",
                    hide_details=True,
                    classes="mb-2",
                )

                v3.VDivider(classes="my-3")
                html.H4("Colors", classes="font-weight-bold mb-2")

                # Color Pickers
                for label, key in [
                    ("Host Color", "host_color"),
                    ("Fiber Color", "fiber_color"),
                    ("Ball Color", "ball_color"),
                    ("Background Color", "bg_color"),
                ]:
                    with html.Div(classes="d-flex align-center justify-space-between mb-2"):
                        html.Span(label, classes="text-caption font-weight-medium")
                        with v3.VMenu(location="bottom", close_on_content_click=False):
                            with v3.Template(v_slot_activator="{ props }"):
                                with v3.VBtn(
                                    v_bind="props",
                                    variant="outlined",
                                    density="compact",
                                    size="small",
                                    classes="px-2",
                                ):
                                    v3.VAvatar(size=16, color=(key,), classes="mr-2")
                                    html.Span(f"{{{{ {key} }}}}")
                            v3.VColorPicker(
                                v_model=(key,),
                                mode="hex",
                                hide_inputs=False,
                            )

                v3.VDivider(classes="my-3")
                html.H4("Line Widths", classes="font-weight-bold mb-2")

                html.Div("Fiber Line Width: {{ fiber_line_width }} px", classes="text-caption mb-1")
                v3.VSlider(
                    v_model=("fiber_line_width", 2.0),
                    min=0.5,
                    max=10.0,
                    step=0.5,
                    density="compact",
                    hide_details=True,
                    classes="mb-3",
                )

                html.Div("Host Line Width: {{ host_line_width }} px", classes="text-caption mb-1")
                v3.VSlider(
                    v_model=("host_line_width", 1.0),
                    min=0.5,
                    max=10.0,
                    step=0.5,
                    density="compact",
                    hide_details=True,
                    classes="mb-3",
                )

                html.Div("Ball Line Width: {{ ball_line_width }} px", classes="text-caption mb-1")
                v3.VSlider(
                    v_model=("ball_line_width", 1.0),
                    min=0.5,
                    max=10.0,
                    step=0.5,
                    density="compact",
                    hide_details=True,
                    classes="mb-2",
                )

                v3.VDivider(classes="my-3")
                html.H4("Recording & Export", classes="font-weight-bold mb-2")
                v3.VBtn(
                    "Record Animation Video",
                    click="record_dialog = true",
                    prepend_icon="mdi-video",
                    variant="tonal",
                    color="error",
                    block=True,
                    classes="mb-2",
                )
                v3.VBtn(
                    "Capture Snapshot (PNG)",
                    click=ctrl.take_screenshot,
                    prepend_icon="mdi-camera",
                    variant="tonal",
                    block=True,
                )

        # Main 3D Viewport
        with layout.content:
            with v3.VContainer(
                fluid=True,
                classes="fill-height pa-0",
                style="width: 100%; height: 100%; overflow: hidden; background: #000;",
            ):
                if args.rendering == "local":
                    html_view = vtk_widgets.VtkLocalView(viewer.plotter.render_window)
                else:
                    html_view = vtk_widgets.VtkRemoteView(
                        viewer.plotter.render_window,
                        interactive_ratio=0.5,
                        interactive_quality=75,
                        still_ratio=1.0,
                        still_quality=95,
                    )
                ctrl.view_update = html_view.update
                ctrl.view_reset_camera = html_view.reset_camera
                viewer.view_update_fn = html_view.update

            # Record Video Dialog
            with v3.VDialog(v_model=("record_dialog", False), max_width=500, persistent=("is_recording", False)):
                with v3.VCard():
                    with v3.VCardTitle(classes="d-flex align-center justify-space-between"):
                        html.Span("Record Animation Video", classes="text-h6 font-weight-bold")
                        with v3.VBtn(
                            icon=True,
                            variant="text",
                            density="compact",
                            click="record_dialog = false",
                            disabled=("is_recording", False),
                        ):
                            v3.VIcon("mdi-close")

                    with v3.VCardText(classes="pt-2"):
                        # Resolution
                        v3.VSelect(
                            v_model=("record_resolution", "1280x720 (720p HD)"),
                            items=("record_resolution_options",),
                            label="Resolution",
                            density="compact",
                            variant="outlined",
                            disabled=("is_recording", False),
                            classes="mb-2",
                        )

                        # Framerate and Frame Range
                        with html.Div(classes="d-flex align-center gap-2 mb-2"):
                            with html.Div(style="flex: 1;", classes="mr-2"):
                                v3.VSelect(
                                    v_model=("record_fps", 30),
                                    items=("record_fps_options",),
                                    label="FPS",
                                    density="compact",
                                    variant="outlined",
                                    disabled=("is_recording", False),
                                )
                            with html.Div(style="flex: 1;", classes="mr-2"):
                                v3.VTextField(
                                    v_model=("record_start_frame", 1),
                                    label="Start Frame",
                                    type="number",
                                    min=1,
                                    max=data.n_frames,
                                    density="compact",
                                    variant="outlined",
                                    disabled=("is_recording", False),
                                )
                            with html.Div(style="flex: 1;"):
                                v3.VTextField(
                                    v_model=("record_end_frame", data.n_frames),
                                    label="End Frame",
                                    type="number",
                                    min=1,
                                    max=data.n_frames,
                                    density="compact",
                                    variant="outlined",
                                    disabled=("is_recording", False),
                                )

                        # Output filename
                        v3.VTextField(
                            v_model=("record_filename", default_rec_filename),
                            label="Output Filename (saved to recordings/)",
                            density="compact",
                            variant="outlined",
                            disabled=("is_recording", False),
                            classes="mb-2",
                        )

                        # Time overlay toggle
                        v3.VSwitch(
                            v_model=("record_include_time_overlay", True),
                            label="Include Time & Frame Overlay in Video",
                            density="compact",
                            color="primary",
                            disabled=("is_recording", False),
                            hide_details=True,
                            classes="mb-2",
                        )

                        # Progress Bar (when recording)
                        with html.Div(v_if="is_recording", classes="my-3"):
                            v3.VProgressLinear(
                                model_value=("record_progress", 0),
                                color="error",
                                height=12,
                                striped=True,
                                rounded=True,
                            )

                        # Status message
                        html.Div(
                            "{{ record_status }}",
                            v_if="record_status",
                            classes="text-caption text-center font-weight-medium my-2 text-primary",
                        )

                        # Download button when ready
                        with v3.VBtn(
                            v_if="record_download_ready && !is_recording",
                            href=("record_download_url",),
                            download=("record_download_name",),
                            target="_blank",
                            color="success",
                            variant="elevated",
                            prepend_icon="mdi-download",
                            block=True,
                            classes="my-2",
                        ):
                            html.Span("Download File")

                    with v3.VCardActions(classes="pa-4 pt-0"):
                        v3.VBtn(
                            "Snapshot PNG",
                            click=ctrl.take_screenshot,
                            prepend_icon="mdi-camera",
                            variant="outlined",
                            color="secondary",
                            density="compact",
                            v_if="!is_recording",
                        )
                        v3.VSpacer()
                        v3.VBtn(
                            "Close",
                            click="record_dialog = false",
                            variant="text",
                            density="compact",
                            classes="mr-2",
                            v_if="!is_recording",
                        )
                        v3.VBtn(
                            "Start Recording",
                            click=ctrl.start_recording,
                            prepend_icon="mdi-record-rec",
                            variant="elevated",
                            color="error",
                            density="compact",
                            v_if="!is_recording",
                        )
                        v3.VBtn(
                            "Cancel Recording",
                            click=ctrl.cancel_recording,
                            prepend_icon="mdi-cancel",
                            variant="elevated",
                            color="error",
                            density="compact",
                            v_if="is_recording",
                        )



    # State change listeners
    @state.change("frame")
    def on_frame_change(frame, **kwargs):
        f = int(frame)
        if f != viewer.current_frame:
            viewer.set_frame(f)
            state.time_label = format_time_label(data.times, f, data.n_frames)
            viewer.plotter.render()
            ctrl.view_update()

    @state.change("speed")
    def on_speed_change(speed, **kwargs):
        viewer.speed = float(speed)

    @state.change("loop")
    def on_loop_change(loop, **kwargs):
        viewer.loop = bool(loop)

    @state.change("host_mode")
    def on_host_mode_change(host_mode, **kwargs):
        viewer.set_host_mode(host_mode)

    @state.change("fibers_only")
    def on_fibers_only_change(fibers_only, **kwargs):
        viewer.set_fibers_only(fibers_only)

    @state.change("ball_mode")
    def on_ball_mode_change(ball_mode, **kwargs):
        viewer.set_ball_mode(ball_mode)

    @state.change("host_opacity")
    def on_host_opacity_change(host_opacity, **kwargs):
        viewer.set_host_opacity(host_opacity)

    @state.change("host_edges")
    def on_host_edges_change(host_edges, **kwargs):
        viewer.set_host_edges(host_edges)

    @state.change("host_color")
    def on_host_color_change(host_color, **kwargs):
        viewer.set_color("host", host_color)

    @state.change("fiber_color")
    def on_fiber_color_change(fiber_color, **kwargs):
        viewer.set_color("fiber", fiber_color)

    @state.change("ball_color")
    def on_ball_color_change(ball_color, **kwargs):
        viewer.set_color("ball", ball_color)

    @state.change("bg_color")
    def on_bg_color_change(bg_color, **kwargs):
        viewer.set_color("bg", bg_color)

    @state.change("fiber_line_width")
    def on_fiber_line_width_change(fiber_line_width, **kwargs):
        viewer.set_line_width("fiber", fiber_line_width)

    @state.change("host_line_width")
    def on_host_line_width_change(host_line_width, **kwargs):
        viewer.set_line_width("host", host_line_width)

    @state.change("ball_line_width")
    def on_ball_line_width_change(ball_line_width, **kwargs):
        viewer.set_line_width("ball", ball_line_width)

    # Server-Side Animation Loop
    async def animation_loop():
        # Short startup delay to allow client connection
        await asyncio.sleep(0.1)
        set_stream_quality(95, 1.0)

        while True:
            if state.playing and data.n_frames > 1:
                set_stream_quality(75, 0.5)
                base_fps = float(viewer.fps) if viewer.fps > 0 else 30.0
                speed = max(0.1, float(viewer.speed))

                effective_rate = base_fps * speed
                if effective_rate <= 60.0:
                    frames_to_advance = 1
                    target_interval = 1.0 / effective_rate
                else:
                    target_interval = 1.0 / 60.0
                    frames_to_advance = max(1, int(round(speed / 2.0)))

                next_frame = viewer.current_frame + frames_to_advance
                if next_frame >= data.n_frames:
                    if state.loop:
                        next_frame = next_frame % data.n_frames
                    else:
                        next_frame = data.n_frames - 1
                        state.playing = False
                        viewer.is_playing = False
                        set_stream_quality(95, 1.0)
                        ctrl.view_update()

                t_tick_start = time.perf_counter()
                viewer.set_frame(next_frame)
                with state:
                    state.frame = next_frame
                    state.time_label = format_time_label(data.times, next_frame, data.n_frames)
                viewer.plotter.render()
                ctrl.view_update()

                t_elapsed = time.perf_counter() - t_tick_start
                sleep_time = max(0.001, target_interval - t_elapsed)
                await asyncio.sleep(sleep_time)
            else:
                await asyncio.sleep(0.03)

    def on_server_ready_cb(**kwargs):
        asyncio.create_task(animation_loop())

    ctrl.on_server_ready.add(on_server_ready_cb)

    return server, viewer


# ---------------------------------------------------------------------------
# CLI Argument Parsing
# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Trame Web Front-End for Abaqus ODB Impact Visualizations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("npz_file", help="Path to exported .npz simulation file")

    # Server configuration
    parser.add_argument("--port", type=int, default=8080, help="Web server port (default: 8080)")
    parser.add_argument("--host", default="127.0.0.1", help="Binding host (default: 127.0.0.1)")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically launch web browser")
    parser.add_argument("--viewer-dir", default=None, help="Directory containing verification/roar/odb_viewer.py")
    parser.add_argument(
        "--rendering",
        choices=["remote", "local"],
        default="remote",
        help="Rendering backend: remote (server OpenGL streamed image) or local (vtk.js) (default: remote)",
    )

    # Initial display options matching desktop viewer
    parser.add_argument(
        "--host-mode",
        choices=["wireframe", "solid", "hidden"],
        default="wireframe",
        help="Initial host render mode (default: wireframe)",
    )
    parser.add_argument(
        "--ball-mode",
        choices=["wireframe", "solid", "hidden"],
        default="wireframe",
        help="Initial ball render mode (default: wireframe)",
    )
    parser.add_argument(
        "--fibers-only",
        action="store_true",
        help="Start with host hidden and fibers & ball visible",
    )
    parser.add_argument(
        "--host-opacity",
        type=float,
        default=1.0,
        help="Host opacity in solid mode (0.0 to 1.0, default: 1.0)",
    )
    parser.add_argument(
        "--host-edges",
        action="store_true",
        help="Overlay element edges on solid host",
    )

    # Colors & Line Widths
    parser.add_argument(
        "--host-color",
        default=odb_viewer.DEFAULT_HOST_COLOR,
        help=f"Host color hex code (default: {odb_viewer.DEFAULT_HOST_COLOR})",
    )
    parser.add_argument(
        "--fiber-color",
        default=odb_viewer.DEFAULT_FIBER_COLOR,
        help=f"Fiber color hex code (default: {odb_viewer.DEFAULT_FIBER_COLOR})",
    )
    parser.add_argument(
        "--ball-color",
        default=odb_viewer.DEFAULT_BALL_COLOR,
        help=f"Ball color hex code (default: {odb_viewer.DEFAULT_BALL_COLOR})",
    )
    parser.add_argument(
        "--bg-color",
        "--background",
        default=odb_viewer.DEFAULT_BG_COLOR,
        help=f"Background color hex code (default: {odb_viewer.DEFAULT_BG_COLOR})",
    )
    parser.add_argument(
        "--host-line-width",
        type=float,
        default=1.0,
        help="Host wireframe line width in pixels (default: 1.0)",
    )
    parser.add_argument(
        "--fiber-line-width",
        type=float,
        default=2.0,
        help="Fiber line width in pixels (default: 2.0)",
    )
    parser.add_argument(
        "--ball-line-width",
        type=float,
        default=1.0,
        help="Ball wireframe line width in pixels (default: 1.0)",
    )

    # Camera & Playback
    parser.add_argument(
        "--camera-preset",
        "--view",
        choices=["iso", "symmetry", "reset"],
        default="iso",
        help="Initial camera preset (default: iso)",
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="Initial playback speed multiplier (default: 1.0)",
    )
    parser.add_argument(
        "--fps",
        type=float,
        default=30.0,
        help="Target animation frame rate (default: 30.0)",
    )
    parser.add_argument(
        "--no-loop",
        action="store_true",
        help="Disable continuous animation looping",
    )

    return parser.parse_args()


# ---------------------------------------------------------------------------
# Main Execution Entry Point
# ---------------------------------------------------------------------------
def main() -> None:
    args = parse_args()

    # Load data
    data = odb_viewer.ODBData(args.npz_file)

    # Initialize app
    server, viewer = create_app(data, args)

    # Launch server
    open_browser = not args.no_browser
    print(f"Starting ODB Web Viewer server on http://{args.host}:{args.port}")
    if open_browser:
        print("Launching default web browser...")

    server.start(
        host=args.host,
        port=args.port,
        open_browser=open_browser,
    )


if __name__ == "__main__":
    main()
