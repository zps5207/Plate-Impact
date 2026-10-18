# T-019: Web Viewer Video Recording & Snapshot Export Feature

## 1. Executive Summary

Task **T-019** adds an offscreen video recording and snapshot export capability to the Trame web-based ODB impact viewer (`odb_viewer_web.py`). Users can record animation sequences into high-definition MP4 videos directly from their current viewport (preserving user-applied orbit, zoom, pan, styling, and frame overlays) without interrupting the live session or compromising the smooth 30 FPS playback introduced in T-018.

### Key Capabilities Added
1. **Interactive Record Controls**:
   - Dedicated **Record** button in the top toolbar and side drawer.
   - Modal configuration dialog (`v3.VDialog`) allowing user selection of:
     - **Resolution**: 1280x720 (720p HD, default), 1920x1080 (1080p FHD), Current Aspect (Window Size), and 854x480 (480p SD).
     - **Framerate (FPS)**: 15, 24, 30 (default), or 60 FPS.
     - **Frame Range**: Start frame and End frame (default: 1 to $N$).
     - **Output Filename**: Default `v500_viewer_<timestamp>.mp4` saved to `recordings/` folder in current working directory.
     - **Time & Frame Overlay**: Toggle switch to burn microsecond timestamp HUD into video frames.
2. **Camera Preservation & Aspect Ratio Compensation**:
   - Exact transfer of live camera parameters (`position`, `focal_point`, `view_up`, `view_angle`, `parallel_scale`, `clipping_range`).
   - Mathematical field-of-view compensation when output aspect ratio differs from client browser window to prevent horizontal cropping of the model.
3. **Full Styling Fidelity**:
   - Renders directly with active PyVista/VTK scene state: host display mode (`wireframe`, `solid`, `hidden`), fibers-only toggle, ball display mode, custom colors (host, fiber, ball, background), line widths, solid opacity, and element edges.
4. **Non-Disruptive Live View Lifecycle**:
   - Live playback automatically pauses during recording.
   - Offscreen frame loop yields periodically (`await asyncio.sleep(0.001)`) to maintain WebSocket responsiveness and render a live striped progress bar.
   - Comprehensive state restoration in `finally` block: window dimensions, camera settings, frame index, stream quality (95, ratio 1.0), and playback state are fully restored.
   - Interactive **Cancel** button immediately stops recording and deletes partial files from disk.
5. **Direct File Download & Server Console Logging**:
   - Output directory `recordings/` registered with Trame static server (`server.serve["recordings"]`).
   - Browser displays a direct **Download File** button upon completion.
   - Server prints the resolved absolute file path to the console.
6. **Snapshot PNG Export**:
   - Quick **Snapshot** button in toolbar and dialog to export the current view as a high-resolution PNG image at the selected resolution.

---

## 2. Technical Architecture & Design

### 2.1 Offscreen Rendering Pipeline
In desktop `odb_viewer.py`, headless movie export relied on PyVista's `plotter.open_movie(...)` followed by `plotter.close()`. In a live web application, calling `plotter.close()` destroys the underlying VTK OpenGL context and terminates remote streaming.

To ensure non-destructive export, `odb_viewer_web.py` uses `imageio.v2` with `libx264` and `yuv420p` pixel format:
1. Temporarily resize the VTK render window: `viewer.plotter.render_window.SetSize(target_w, target_h)`.
2. Apply aspect ratio compensation to the active camera.
3. For each frame in `range(start_idx, end_idx + 1)`:
   - Call `viewer.set_frame(frame_idx)`.
   - Update text actor overlay if enabled.
   - Render offscreen: `viewer.plotter.render()`.
   - Capture framebuffer image: `img = viewer.plotter.screenshot(return_img=True)`.
   - Append to video stream: `writer.append_data(img)`.
   - Update progress state and yield to event loop: `await asyncio.sleep(0.001)`.
4. Close video writer.
5. In `finally`, restore original window size, camera, frame index, and stream quality.

### 2.2 Camera Math: Aspect Ratio Compensation
VTK cameras maintain a constant **vertical** field of view (`view_angle`, $\theta_y$) in perspective mode, and a constant vertical half-height (`parallel_scale`, $s_y$) in parallel projection.

When rendering offscreen at a resolution whose aspect ratio $AR_{out} = W_{out} / H_{out}$ differs from the live browser viewport aspect ratio $AR_{in} = W_{in} / H_{in}$:

#### Perspective Projection
The horizontal field of view half-angle $\theta_x / 2$ is related to the vertical FOV by:
$$\tan\left(\frac{\theta_x}{2}\right) = \tan\left(\frac{\theta_y}{2}\right) \cdot AR$$

If $AR_{out} < AR_{in}$ (the export is narrower or taller than the live viewport), keeping the same vertical FOV would cause horizontal cropping of the model at the left and right boundaries. To guarantee that the entire horizontal scene visible in the browser remains visible in the recorded video:
$$\tan\left(\frac{\theta_{y,out}}{2}\right) = \tan\left(\frac{\theta_{y,in}}{2}\right) \cdot \frac{AR_{in}}{AR_{out}}$$
$$\theta_{y,out} = 2 \cdot \arctan\left(\tan\left(\frac{\theta_{y,in}}{2}\right) \cdot \frac{AR_{in}}{AR_{out}}\right)$$

If $AR_{out} \ge AR_{in}$ (the export is wider than the live viewport), the vertical FOV is preserved ($\theta_{y,out} = \theta_{y,in}$), and horizontal FOV naturally expands without any cropping.

#### Parallel Projection
Similarly, for parallel projection (used in the Symmetry plane preset):
$$s_{y,out} = \begin{cases} s_{y,in} \cdot \dfrac{AR_{in}}{AR_{out}} & \text{if } AR_{out} < AR_{in} \\ s_{y,in} & \text{if } AR_{out} \ge AR_{in} \end{cases}$$

This math guarantees the subject is never cropped, regardless of viewport aspect ratio differences.

### 2.3 User Interface Integration
- **Toolbar**: Added a camera icon button ("Snapshot") and red video button ("Record") adjacent to camera presets.
- **Drawer**: Added a "Recording & Export" section with quick action buttons.
- **Dialog (`v3.VDialog`)**:
  - Modal card featuring resolution selector, FPS selector, frame range numeric inputs, filename field, and HUD toggle.
  - Vuetify striped progress bar displaying rendering percentage in real-time.
  - Dynamic button states: "Cancel Recording" replaces dialog actions during active rendering.
  - Green "Download File" button appears upon completion.

---

## 3. Verification & Empirical Results

The implementation was verified using Microsoft Edge in headless mode via Chrome DevTools Protocol (CDP) on the 58 MB simulation file `agents/drafter/inbox/T-012/v500_viewer.npz` (150 frames, 0 to 70 µs).

The automated test script (`scratch/test_t019_verification.py`) executed 6 verification phases:

| Phase | Test Description | Observed Result | Status |
| :--- | :--- | :--- | :--- |
| **1. Custom Viewport** | Applied free mouse drag orbit across viewport (from (700, 400) to (500, 260)). | Camera rotated off-axis; screenshot captured (164,518 bytes). | **PASSED** |
| **2. MP4 Recording** | Configured 30 frames (1 to 30) at 1280x720 @ 30 FPS; clicked Start Recording. | Server rendered all 30 frames; live progress bar reached 100%; saved `test_v500_30f.mp4`. | **PASSED** |
| **3. MP4 Inspection** | Verified file existence, size, frame count, dimensions, and visual content. | Exists (55,717 bytes); 30 frames; 1280x720 resolution; frame 0 has 54,611 foreground pixels. | **PASSED** |
| **4. Cancellation** | Started 150-frame recording; clicked Cancel Recording mid-render. | Render loop aborted; status set to "Recording cancelled."; partial MP4 deleted from disk. | **PASSED** |
| **5. Snapshot PNG** | Triggered Snapshot export of current frame at 1280x720. | PNG exported (117,708 bytes); valid 1280x720x3 image; download link generated. | **PASSED** |
| **6. Live State Restoration** | Restored viewport camera/size; clicked Play in live web viewer. | Playback resumed smoothly; frames advanced sequentially from Frame 0 to Frame 60. | **PASSED** |

### Visual Match Comparison
- **On-Screen Canvas Viewport**: Bounds `[x=340, y=64, w=901, h=624]` ($AR_{in} \approx 1.444$).
- **Exported Video Frame 0**: Resolution `1280x720` ($AR_{out} \approx 1.778$).
- Because $AR_{out} > AR_{in}$, the vertical FOV was preserved and horizontal coverage was widened to fill 16:9 framing without cropping.
- Extracted frame 0 (`verification_mp4_frame0.png`) and canvas screenshot (`verification_screen_canvas.png`) confirm identical orientation, styling, line widths, and HUD time badge format.

---

## 4. Deliverables Summary

All deliverables reside inside `agents/drafter/outbox/T-019/`:
1. `odb_viewer_web.py`: Complete updated Trame web viewer script with recording, snapshot, camera compensation, and smooth playback support.
2. `RESULT-NOTES.md`: This comprehensive implementation and verification report.
3. Artifacts:
   - `test_v500_30f.mp4`: Sample 30-frame MP4 recorded from custom orbit view.
   - `verification_mp4_frame0.png`: Frame 0 extracted from recorded MP4.
   - `verification_screen_canvas.png`: Live viewport screenshot before export.
   - `verification_screen_before.png`: Full-page browser screenshot before export.
   - `v500_viewer_frame_001_20261016_134803.png`: Exported PNG snapshot.

---

## 5. Scope & Limitations

1. **Audio**: Simulation videos are silent animations; no audio stream is multiplexed.
2. **Codec Requirements**: Export utilizes `imageio` with the `libx264` codec. Width and height are automatically rounded to even integers to satisfy H.264 macroblock constraints.
3. **Headless Environment**: Automated CDP testing was performed using Microsoft Edge headless on Windows 11.
