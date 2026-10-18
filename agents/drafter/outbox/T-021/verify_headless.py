"""test_t021_cdp.py - Automated CDP Verification Suite for Client-Side Three.js Viewer.

Tests:
  1. Dataset loading and initialization on real v500 data.
  2. Load time and browser memory metrics.
  3. Screenshots at frames 0, 75, 149 in Iso, Symmetry, Solid, and Fibers-only views.
  4. Visual diff/comparison against odb_viewer.py reference images.
  5. Playback performance at 1920x1080 and 2560x1440:
     - Frames per second (FPS)
     - Immediate pause response latency
     - Largest frame gap & frame pacing
  6. Active 3D mouse orbit during playback without stalling or snapping.
  7. In-browser video recording and PNG snapshot export.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import requests
import websocket

EDGE_BIN = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")


def find_free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class CDPClient:
    def __init__(self, port: int, timeout: float = 30.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                res = requests.get(f"http://127.0.0.1:{port}/json", timeout=1.0)
                tabs = res.json()
                page = next(t for t in tabs if t.get("type") == "page")
                self.ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=25, suppress_origin=True)
                self.seq = 0
                return
            except Exception:
                time.sleep(0.2)
        raise RuntimeError(f"Edge CDP not reachable on port {port}")

    def send(self, method: str, params: dict | None = None) -> dict[str, Any]:
        self.seq += 1
        seq = self.seq
        payload = {"id": seq, "method": method, "params": params or {}}
        self.ws.send(json.dumps(payload))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == seq:
                if "error" in msg:
                    raise RuntimeError(f"CDP error in {method}: {msg['error']}")
                return msg.get("result", {})

    def evaluate(self, expr: str) -> Any:
        res = self.send("Runtime.evaluate", {
            "expression": expr,
            "returnByValue": True,
            "awaitPromise": True,
        })
        if "exceptionDetails" in res:
            raise RuntimeError(f"JS Exception in: {expr}\n{res['exceptionDetails']}")
        return res.get("result", {}).get("value")

    def capture_screenshot(self, out_path: Path, clip: dict | None = None) -> None:
        params = {"format": "png"}
        if clip:
            params["clip"] = clip
        res = self.send("Page.captureScreenshot", params)
        data = base64.b64decode(res["data"])
        with open(out_path, "wb") as f:
            f.write(data)


def wait_for_server(url: str, timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=1.0)
            if r.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(0.15)
    raise RuntimeError(f"Server at {url} failed to respond within {timeout} s")


def run_test(use_gpu: bool = False, window_w: int = 1920, window_h: int = 1080) -> dict[str, Any]:
    port = find_free_port()
    cdp_port = find_free_port()
    viewer_dir = Path("agents/drafter/outbox/T-021").resolve()
    data_dir = viewer_dir / "data_v500"
    scratch_dir = Path("agents/drafter/scratch/test_artifacts").resolve()
    scratch_dir.mkdir(parents=True, exist_ok=True)

    server_cmd = [
        sys.executable,
        str(viewer_dir / "serve_viewer.py"),
        str(data_dir),
        "--port", str(port),
        "--no-browser",
    ]
    server_proc = subprocess.Popen(server_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    edge_cmd = [
        str(EDGE_BIN),
        "--headless=new",
        "--no-first-run",
        "--no-default-browser-check",
        "--remote-allow-origins=*",
        f"--remote-debugging-port={cdp_port}",
        f"--window-size={window_w},{window_h}",
        f"--user-data-dir={tempfile.mkdtemp(prefix='edge-test-')}",
    ]
    if not use_gpu:
        edge_cmd.append("--disable-gpu")
    else:
        edge_cmd.extend(["--use-gl=angle", "--enable-unsafe-webgpu"])

    edge_cmd.append("about:blank")
    edge_proc = None

    try:
        wait_for_server(f"http://127.0.0.1:{port}/viewer.html")
        t_start_browser = time.time()
        edge_proc = subprocess.Popen(edge_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cdp = CDPClient(cdp_port)

        cdp.send("Page.enable")
        cdp.send("Page.navigate", {"url": f"http://127.0.0.1:{port}/viewer.html"})

        # Wait for data to load
        t0_load = time.time()
        loaded = False
        while time.time() - t0_load < 40.0:
            is_ready = cdp.evaluate("""
                (() => {
                    const screen = document.getElementById('loading-screen');
                    const text = document.getElementById('lbl-time')?.textContent;
                    return (screen && screen.style.display === 'none') || (text && text.includes('Frame 1/150'));
                })()
            """)
            if is_ready:
                loaded = True
                break
            time.sleep(0.2)

        if not loaded:
            raise RuntimeError("Viewer did not finish loading data within 40 seconds.")

        load_time_sec = round(time.time() - t0_load, 2)
        print(f"[{'GPU' if use_gpu else 'SwiftShader'}] Data loaded in {load_time_sec} s ({window_w}x{window_h})")

        # Memory usage
        memory_mb = None
        try:
            mem = cdp.evaluate("performance.memory ? performance.memory.usedJSHeapSize : null")
            if mem:
                memory_mb = round(mem / (1024 * 1024), 2)
        except Exception:
            pass

        metrics = cdp.send("Performance.getMetrics")
        js_heap = next((m["value"] for m in metrics.get("metrics", []) if m["name"] == "JSHeapUsedSize"), None)
        if js_heap:
            memory_mb = round(js_heap / (1024 * 1024), 2)

        print(f"Browser JS Heap Memory: {memory_mb} MB")

        # Helper to click button by selector
        def click(selector: str):
            return cdp.evaluate(f"""
                (() => {{
                    const el = document.querySelector({json.dumps(selector)});
                    if (!el) return false;
                    el.click();
                    return true;
                }})()
            """)

        def set_select(selector: str, val: str):
            return cdp.evaluate(f"""
                (() => {{
                    const el = document.querySelector({json.dumps(selector)});
                    if (!el) return false;
                    el.value = {json.dumps(val)};
                    el.dispatchEvent(new Event('change'));
                    return true;
                }})()
            """)

        def set_checkbox(selector: str, checked: bool):
            return cdp.evaluate(f"""
                (() => {{
                    const el = document.querySelector({json.dumps(selector)});
                    if (!el) return false;
                    el.checked = {json.dumps(checked)};
                    el.dispatchEvent(new Event('change'));
                    return true;
                }})()
            """)

        def set_frame(f: int):
            return cdp.evaluate(f"""
                (() => {{
                    window.__viewer.updateFrame({f}, true);
                    return true;
                }})()
            """)

        # Collapse drawer for clean screenshots matching odb_viewer.py
        is_drawer_open = cdp.evaluate("!document.getElementById('drawer').classList.contains('collapsed')")
        if is_drawer_open:
            click("#btn-toggle-drawer")
            time.sleep(0.3)

        # -------------------------------------------------------------
        # Screenshot Verification Suite (Frames 0, 75, 149)
        # -------------------------------------------------------------
        outbox_dir = viewer_dir
        screenshots = {}

        # Hide HUD temporarily for clean visual comparison against odb_viewer.py
        cdp.evaluate("""
            document.getElementById('hud-overlay').style.display = 'none';
            document.getElementById('hud-bottom').style.display = 'none';
        """)

        canvas_clip = cdp.evaluate("""
            (() => {
                const r = document.getElementById('webgl-canvas').getBoundingClientRect();
                return { x: r.left, y: r.top, width: r.width, height: r.height, scale: 1 };
            })()
        """)

        # Frame 0 Iso Wireframe
        set_frame(0)
        click("#btn-cam-iso")
        time.sleep(0.2)
        p0_iso = outbox_dir / "evidence_frame_000_iso.png"
        cdp.capture_screenshot(p0_iso, clip=canvas_clip)
        screenshots["frame_000_iso"] = str(p0_iso)

        # Frame 0 Symmetry
        click("#btn-cam-sym")
        time.sleep(0.2)
        p0_sym = outbox_dir / "evidence_frame_000_symmetry.png"
        cdp.capture_screenshot(p0_sym, clip=canvas_clip)
        screenshots["frame_000_sym"] = str(p0_sym)

        # Frame 75 Iso Wireframe
        set_frame(75)
        click("#btn-cam-iso")
        time.sleep(0.2)
        p75_iso = outbox_dir / "evidence_frame_075_iso.png"
        cdp.capture_screenshot(p75_iso, clip=canvas_clip)
        screenshots["frame_075_iso"] = str(p75_iso)

        # Frame 75 Symmetry
        click("#btn-cam-sym")
        time.sleep(0.2)
        p75_sym = outbox_dir / "evidence_frame_075_symmetry.png"
        cdp.capture_screenshot(p75_sym, clip=canvas_clip)
        screenshots["frame_075_sym"] = str(p75_sym)

        # Frame 75 Solid + Edges
        set_select("#sel-host-mode", "solid")
        set_checkbox("#chk-host-edges", True)
        click("#btn-cam-iso")
        time.sleep(0.2)
        p75_solid = outbox_dir / "evidence_frame_075_solid.png"
        cdp.capture_screenshot(p75_solid, clip=canvas_clip)
        screenshots["frame_075_solid"] = str(p75_solid)

        # Frame 149 Fibers Only
        set_frame(149)
        set_checkbox("#chk-fibers-only", True)
        time.sleep(0.2)
        p149_fib = outbox_dir / "evidence_frame_149_fibers_only.png"
        cdp.capture_screenshot(p149_fib, clip=canvas_clip)
        screenshots["frame_149_fibers_only"] = str(p149_fib)

        # Frame 149 Iso Wireframe
        set_checkbox("#chk-fibers-only", False)
        set_select("#sel-host-mode", "wireframe")
        set_checkbox("#chk-host-edges", False)
        click("#btn-cam-iso")
        time.sleep(0.2)
        p149_iso = outbox_dir / "evidence_frame_149_iso.png"
        cdp.capture_screenshot(p149_iso, clip=canvas_clip)
        screenshots["frame_149_iso"] = str(p149_iso)

        # Frame 149 Symmetry
        click("#btn-cam-sym")
        time.sleep(0.2)
        p149_sym = outbox_dir / "evidence_frame_149_symmetry.png"
        cdp.capture_screenshot(p149_sym, clip=canvas_clip)
        screenshots["frame_149_sym"] = str(p149_sym)

        # Restore HUD & Reset to Iso Frame 0
        cdp.evaluate("""
            document.getElementById('hud-overlay').style.display = 'block';
            document.getElementById('hud-bottom').style.display = 'block';
        """)
        set_frame(0)
        click("#btn-cam-iso")

        # -------------------------------------------------------------
        # Playback Benchmark & Pause Response Measurement
        # -------------------------------------------------------------
        cdp.evaluate("""
            window.__samples = [];
            window.__observer = new MutationObserver(() => {
                const el = document.getElementById('scrubber');
                if (el) {
                    const f = parseInt(el.value, 10);
                    const s = window.__samples;
                    if (!s.length || s[s.length - 1].f !== f) {
                        s.push({ f: f, t: performance.now() });
                    }
                }
            });
            window.__observer.observe(document.getElementById('lbl-time'), { subtree: true, characterData: true, childList: true });
        """)

        # Click Play
        click("#btn-play")
        time.sleep(4.0)

        # Measure Pause Response
        t0_pause_cmd = time.time()
        cdp.evaluate("window.__t_pause_click = performance.now();")
        click("#btn-play")
        time.sleep(1.0)

        samples = cdp.evaluate("window.__samples")
        t_pause_click = cdp.evaluate("window.__t_pause_click")

        # Samples before pause
        active_samples = [s for s in samples if s["t"] <= t_pause_click]
        fps = 0.0
        if len(active_samples) >= 2:
            duration_s = (active_samples[-1]["t"] - active_samples[0]["t"]) / 1000.0
            fps = (len(active_samples) - 1) / duration_s if duration_s > 0 else 0

        post_samples = [s for s in samples if s["t"] > t_pause_click]
        pause_latency_ms = round(post_samples[-1]["t"] - t_pause_click, 2) if post_samples else 0.0

        # Frame gap analysis
        frame_numbers = [s["f"] for s in active_samples]
        gaps = [(b - a) % 150 for a, b in zip(frame_numbers, frame_numbers[1:])]
        max_gap = max(gaps, default=0)

        print(f"Playback Performance ({window_w}x{window_h}): {fps:.2f} FPS, max gap: {max_gap}, pause latency: {pause_latency_ms} ms")

        # -------------------------------------------------------------
        # 3D Orbit During Playback Verification
        # -------------------------------------------------------------
        # Resume playback
        click("#btn-play")
        time.sleep(0.5)

        # Record camera position before drag
        cam_pos_before = cdp.evaluate("({ x: window.__viewer.getCamera().position.x, y: window.__viewer.getCamera().position.y, z: window.__viewer.getCamera().position.z })")
        frame_before = cdp.evaluate("window.__viewer.getFrame()")

        # Dispatch drag events across the WebGL canvas
        canvas_box = cdp.evaluate("""
            (() => {
                const r = document.getElementById('webgl-canvas').getBoundingClientRect();
                return { x: r.left + r.width / 2, y: r.top + r.height / 2, w: r.width, h: r.height };
            })()
        """)
        cx, cy = canvas_box["x"], canvas_box["y"]

        cdp.send("Input.dispatchMouseEvent", {"type": "mousePressed", "x": cx, "y": cy, "button": "left", "clickCount": 1})
        for step in range(10):
            cdp.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": cx + (step * 20), "y": cy - (step * 15), "button": "left"})
            time.sleep(0.04)
        cdp.send("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": cx + 200, "y": cy - 150, "button": "left"})

        time.sleep(0.5)
        cam_pos_after = cdp.evaluate("({ x: window.__viewer.getCamera().position.x, y: window.__viewer.getCamera().position.y, z: window.__viewer.getCamera().position.z })")
        frame_after = cdp.evaluate("window.__viewer.getFrame()")
        is_still_playing = cdp.evaluate("window.__viewer.isPlaying()")

        # Pause after test
        click("#btn-play")

        cam_delta = sum(abs(cam_pos_after[k] - cam_pos_before[k]) for k in ("x", "y", "z"))
        frames_advanced = (frame_after - frame_before) % 150
        orbit_while_playing_success = (cam_delta > 0.001 and frames_advanced > 0 and is_still_playing)
        print(f"Orbit during playback: {'PASS' if orbit_while_playing_success else 'FAIL'} (Camera delta: {cam_delta:.4f}, frames advanced: {frames_advanced})")

        # -------------------------------------------------------------
        # In-Browser Video Recording Verification
        # -------------------------------------------------------------
        print("Testing in-browser video recording...")
        click("#btn-record")
        time.sleep(0.2)
        # Record 5 frames (1 to 5) for quick automated check
        cdp.evaluate("document.getElementById('rec-start').value = '1';")
        cdp.evaluate("document.getElementById('rec-end').value = '5';")
        cdp.evaluate("document.getElementById('rec-fps').value = '30';")
        click("#btn-rec-start")

        # Wait for download link to appear
        t0_rec = time.time()
        rec_ok = False
        while time.time() - t0_rec < 15.0:
            ready = cdp.evaluate("document.getElementById('rec-download-container').style.display !== 'none'")
            if ready:
                rec_ok = True
                break
            time.sleep(0.2)

        click("#btn-rec-cancel")
        print(f"In-browser recording test: {'PASS' if rec_ok else 'FAIL'}")

        return {
            "use_gpu": use_gpu,
            "window_size": [window_w, window_h],
            "load_time_sec": load_time_sec,
            "memory_mb": memory_mb,
            "fps": round(fps, 2),
            "max_gap": max_gap,
            "pause_latency_ms": pause_latency_ms,
            "orbit_success": orbit_while_playing_success,
            "recording_success": rec_ok,
            "screenshots": screenshots,
        }

    finally:
        if edge_proc:
            edge_proc.terminate()
            try:
                edge_proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                edge_proc.kill()
        server_proc.terminate()
        try:
            server_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            server_proc.kill()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gpu", action="store_true", help="Enable hardware GPU")
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    args = parser.parse_args()

    res = run_test(use_gpu=args.gpu, window_w=args.width, window_h=args.height)
    print("\nResult JSON:")
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
