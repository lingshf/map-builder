# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""Style frame-time proxy runner (headless Chromium + SwiftShader).

This runner serves tools/demo/viewer/, opens frame_time_proxy.html, and records the median of
300 measured frames after 60 warm-up frames. It is intended for S5 style budget evidence.
"""

from __future__ import annotations

import argparse
import http.server
import json
import os
import socketserver
import subprocess
import threading
import time
import urllib.parse
import urllib.request


def _http_serve(directory: str, host: str, port: int) -> socketserver.TCPServer:
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=directory, **kwargs)

        def do_POST(self) -> None:  # noqa: N802 - stdlib handler name
            if self.path != "/frame_time_proxy_result.json":
                self.send_error(404)
                return
            length = int(self.headers.get("content-length", "0"))
            data = self.rfile.read(length)
            with open(os.path.join(directory, "frame_time_proxy_result.json"), "wb") as f:
                f.write(data)
            self.send_response(200)
            self.end_headers()

    httpd = socketserver.TCPServer((host, port), Handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd


def _wait_result(url: str, timeout_s: float) -> dict[str, object]:
    end = time.time() + timeout_s
    while time.time() < end:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status == 200:
                    return json.loads(r.read().decode("utf-8"))
        except OSError:
            pass
        time.sleep(0.2)
    raise TimeoutError("frame-time proxy did not publish results before timeout")


def _run_once(chrome: str, url: str, timeout_s: float) -> dict[str, object]:
    result_url = url.replace("frame_time_proxy.html", "frame_time_proxy_result.json")
    p = subprocess.Popen(
        [
            chrome,
            "--headless=new",
            "--disable-gpu",
            "--use-gl=swiftshader",
            "--window-size=1280,720",
            "--run-all-compositor-stages-before-draw",
            url,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        return _wait_result(result_url, timeout_s)
    finally:
        p.terminate()
        p.wait(timeout=5)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--viewer-dir", required=True, help="directory containing map.glb and frame_time_proxy.html")
    ap.add_argument("--chrome", required=True, help="Chromium/Chrome executable")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8781)
    ap.add_argument("--timeout", type=float, default=60.0)
    args = ap.parse_args()

    viewer = os.path.abspath(args.viewer_dir)
    if not os.path.isfile(os.path.join(viewer, "map.glb")):
        raise SystemExit("viewer-dir must contain map.glb")
    if not os.path.isfile(os.path.join(viewer, "frame_time_proxy.html")):
        raise SystemExit("viewer-dir must contain frame_time_proxy.html")

    httpd = _http_serve(viewer, args.host, args.port)
    try:
        qs = urllib.parse.urlencode({"warmup": 60, "frames": 300})
        url = f"http://{args.host}:{args.port}/frame_time_proxy.html?{qs}"
        result_file = os.path.join(viewer, "frame_time_proxy_result.json")
        vals: list[float] = []
        for _ in range(args.runs):
            if os.path.exists(result_file):
                os.remove(result_file)
            out = _run_once(args.chrome, url, args.timeout)
            vals.append(float(out["median_ms"]))
        vals_sorted = sorted(vals)
        median = vals_sorted[len(vals_sorted) // 2]
        spread_pct = 0.0 if median == 0 else (max(vals) - min(vals)) / median * 100.0
        print(json.dumps({"runs_ms": vals, "median_ms": median, "spread_pct": spread_pct}, indent=2))
        return 0
    finally:
        httpd.shutdown()
        httpd.server_close()


if __name__ == "__main__":
    raise SystemExit(main())
