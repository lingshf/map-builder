# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""Style frame-time proxy runner (headless Chromium + SwiftShader, fixed preset camera).

It supports:
1) single-package repeated runs (`--viewer-dir`);
2) alternating base/head runs plus AC3 repeats (`--base-viewer-dir` + `--head-viewer-dir`).
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
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, cast

from demo_bundle import Preset, PresetCamera, load_preset


@dataclass(frozen=True)
class RunResult:
    median_ms: float
    renderer: str


def _http_serve(directory: str, host: str, port: int) -> socketserver.TCPServer:
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
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
                    data = cast("dict[str, object]", json.loads(r.read().decode("utf-8")))
                    return data
        except OSError:
            pass
        time.sleep(0.2)
    raise TimeoutError("frame-time proxy did not publish results before timeout")


def _run_once(chrome: str, url: str, timeout_s: float) -> RunResult:
    parsed = urllib.parse.urlparse(url)
    result_url = urllib.parse.urlunparse(parsed._replace(path="/frame_time_proxy_result.json", query=""))
    p = subprocess.Popen(
        [
            chrome,
            "--headless=new",
            "--disable-gpu",
            "--use-gl=swiftshader",
            "--enable-unsafe-swiftshader",
            "--window-size=1280,720",
            "--run-all-compositor-stages-before-draw",
            url,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        out = _wait_result(result_url, timeout_s)
        renderer = str(out.get("renderer", "unknown"))
        median_raw = out.get("median_ms")
        if not isinstance(median_raw, (int, float)):
            raise SystemExit("frame_time_proxy_result.json missing numeric median_ms")
        return RunResult(median_ms=float(median_raw), renderer=renderer)
    finally:
        p.terminate()
        p.wait(timeout=5)


def _camera_from_preset(preset: Preset, camera_name: str | None) -> PresetCamera:
    if camera_name is None:
        return preset["cameras"][0]
    for c in preset["cameras"]:
        if c["name"] == camera_name:
            return c
    raise SystemExit(f"camera not found in preset: {camera_name}")


def _make_url(host: str, port: int, camera: PresetCamera) -> str:
    eye = camera["eye"]
    target = camera["target"]
    qs = urllib.parse.urlencode(
        {
            "warmup": 60,
            "frames": 300,
            "eye_x": eye[0],
            "eye_y": eye[1],
            "eye_z": eye[2],
            "target_x": target[0],
            "target_y": target[1],
            "target_z": target[2],
            "lens_mm": camera.get("lens_mm", 35),
        }
    )
    return f"http://{host}:{port}/frame_time_proxy.html?{qs}"


def _single_mode(args: argparse.Namespace, camera: PresetCamera) -> dict[str, object]:
    viewer = os.path.abspath(args.viewer_dir)
    if not os.path.isfile(os.path.join(viewer, "map.glb")):
        raise SystemExit("viewer-dir must contain map.glb")
    if not os.path.isfile(os.path.join(viewer, "frame_time_proxy.html")):
        raise SystemExit("viewer-dir must contain frame_time_proxy.html")
    httpd = _http_serve(viewer, args.host, args.port)
    try:
        url = _make_url(args.host, args.port, camera)
        result_file = os.path.join(viewer, "frame_time_proxy_result.json")
        vals: list[float] = []
        renderer = "unknown"
        for _ in range(args.runs):
            if os.path.exists(result_file):
                os.remove(result_file)
            out = _run_once(args.chrome, url, args.timeout)
            vals.append(out.median_ms)
            renderer = out.renderer
        if "swiftshader" not in renderer.lower():
            raise SystemExit(f"renderer is not SwiftShader: {renderer}")
        median = sorted(vals)[len(vals) // 2]
        spread_pct = 0.0 if median == 0 else (max(vals) - min(vals)) / median * 100.0
        return {"mode": "single", "runs_ms": vals, "median_ms": median, "spread_pct": spread_pct, "renderer": renderer}
    finally:
        httpd.shutdown()
        httpd.server_close()


def _alt_mode(args: argparse.Namespace, camera: PresetCamera) -> dict[str, object]:
    base = os.path.abspath(args.base_viewer_dir)
    head = os.path.abspath(args.head_viewer_dir)
    for viewer in (base, head):
        if not os.path.isfile(os.path.join(viewer, "map.glb")):
            raise SystemExit(f"viewer dir must contain map.glb: {viewer}")
    base_port = int(args.port)
    head_port = base_port + 1
    base_httpd = _http_serve(base, args.host, base_port)
    head_httpd = _http_serve(head, args.host, head_port)
    try:
        base_url = _make_url(args.host, base_port, camera)
        head_url = _make_url(args.host, head_port, camera)
        base_runs: list[float] = []
        head_runs: list[float] = []
        renderer = "unknown"
        for _ in range(args.alternating_pairs):
            out_b = _run_once(args.chrome, base_url, args.timeout)
            out_h = _run_once(args.chrome, head_url, args.timeout)
            base_runs.append(out_b.median_ms)
            head_runs.append(out_h.median_ms)
            renderer = out_h.renderer
        repeat_url = head_url if args.repeat_target == "head" else base_url
        repeat_runs: list[float] = []
        for _ in range(args.repeats):
            out = _run_once(args.chrome, repeat_url, args.timeout)
            repeat_runs.append(out.median_ms)
            renderer = out.renderer
        if "swiftshader" not in renderer.lower():
            raise SystemExit(f"renderer is not SwiftShader: {renderer}")
        repeat_median = sorted(repeat_runs)[len(repeat_runs) // 2]
        repeat_spread_pct = 0.0 if repeat_median == 0 else (max(repeat_runs) - min(repeat_runs)) / repeat_median * 100.0
        return {
            "mode": "alternating",
            "base_runs_ms": base_runs,
            "head_runs_ms": head_runs,
            "base_median_ms": sorted(base_runs)[len(base_runs) // 2],
            "head_median_ms": sorted(head_runs)[len(head_runs) // 2],
            "repeat_target": args.repeat_target,
            "repeat_runs_ms": repeat_runs,
            "repeat_spread_pct": repeat_spread_pct,
            "renderer": renderer,
        }
    finally:
        base_httpd.shutdown()
        head_httpd.shutdown()
        base_httpd.server_close()
        head_httpd.server_close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--viewer-dir", help="directory containing map.glb and frame_time_proxy.html")
    ap.add_argument("--base-viewer-dir", help="base viewer dir for alternating runs")
    ap.add_argument("--head-viewer-dir", help="head viewer dir for alternating runs")
    ap.add_argument("--chrome", required=True, help="Chromium/Chrome executable")
    ap.add_argument("--preset", required=True, help="preset name or preset json path")
    ap.add_argument("--camera", default=None, help="fixed camera name from preset (default first camera)")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--alternating-pairs", type=int, default=3)
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--repeat-target", choices=("base", "head"), default="head")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8781)
    ap.add_argument("--timeout", type=float, default=60.0)
    args = ap.parse_args()

    if args.viewer_dir and (args.base_viewer_dir or args.head_viewer_dir):
        raise SystemExit("use either --viewer-dir or --base-viewer-dir/--head-viewer-dir")
    if not args.viewer_dir and not (args.base_viewer_dir and args.head_viewer_dir):
        raise SystemExit("provide --viewer-dir, or both --base-viewer-dir and --head-viewer-dir")

    preset = load_preset(args.preset)
    camera = _camera_from_preset(preset, args.camera)
    result = _single_mode(args, camera) if args.viewer_dir else _alt_mode(args, camera)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
