#!/usr/bin/env python3
"""serve_viewer.py - Local HTTP server for the client-side WebGL ODB viewer.

Binds strictly to 127.0.0.1. Serves viewer assets (HTML, JS, three.js) and maps
the specified dataset directory to /data/. Opens the default web browser.

Usage:
    python serve_viewer.py <data_folder> [--port 8800] [--no-browser]
"""

from __future__ import annotations

import argparse
import http.server
import mimetypes
import os
import socket
import sys
import threading
import urllib.parse
import webbrowser
from pathlib import Path


def find_free_port(preferred: int = 8800) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", preferred))
            return preferred
        except OSError:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]


def make_request_handler(viewer_dir: Path, data_dir: Path):
    class ViewerHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(viewer_dir), **kwargs)

        def translate_path(self, path: str) -> str:
            # Parse URL path
            parsed = urllib.parse.urlparse(path)
            clean_path = urllib.parse.unquote(parsed.path)

            if clean_path.startswith("/data/"):
                sub_path = clean_path[len("/data/"):]
                target = (data_dir / sub_path).resolve()
                return str(target)
            elif clean_path == "/data":
                return str(data_dir.resolve())
            else:
                target = (viewer_dir / clean_path.lstrip("/")).resolve()
                return str(target)

        def end_headers(self):
            # Disable caching for local development
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Access-Control-Allow-Origin", "*")
            super().end_headers()

        def guess_type(self, path: str) -> str:
            p = path.lower()
            if p.endswith(".f32") or p.endswith(".u32") or p.endswith(".i32") or p.endswith(".u8"):
                return "application/octet-stream"
            if p.endswith(".json"):
                return "application/json"
            if p.endswith(".js"):
                return "application/javascript"
            if p.endswith(".html"):
                return "text/html; charset=utf-8"
            if p.endswith(".css"):
                return "text/css"
            return super().guess_type(path)

        def log_message(self, format: str, *args):
            # Suppress noisy logging for binary chunks
            if len(args) >= 1 and any(ext in str(args[0]) for ext in (".f32", ".u32", ".i32", ".u8")):
                return
            super().log_message(format, *args)

    return ViewerHandler


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve client-side WebGL ODB viewer locally.")
    parser.add_argument("data_folder", help="Path to packed data directory containing manifest.json")
    parser.add_argument("--port", "-p", type=int, default=8800, help="Port to listen on (default: 8800)")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically open the web browser")
    args = parser.parse_args()

    data_path = Path(args.data_folder).resolve()
    if not data_path.is_dir():
        sys.exit(f"Error: Data folder does not exist: {data_path}")

    manifest_file = data_path / "manifest.json"
    if not manifest_file.is_file():
        print(f"Warning: No manifest.json found directly in {data_path}")

    viewer_dir = Path(__file__).resolve().parent

    port = find_free_port(args.port)
    server_address = ("127.0.0.1", port)
    handler_class = make_request_handler(viewer_dir, data_path)

    httpd = http.server.ThreadingHTTPServer(server_address, handler_class)
    url = f"http://127.0.0.1:{port}/viewer.html"

    print("=" * 70)
    print("  Plate Impact 3D Client-Side WebGL Viewer")
    print("=" * 70)
    print(f"  Viewer directory : {viewer_dir}")
    print(f"  Data directory   : {data_path}")
    print(f"  URL              : {url}")
    print("  Host             : 127.0.0.1 (local loopback only)")
    print("=" * 70)
    print("Press Ctrl+C to stop the server.")

    if not args.no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
