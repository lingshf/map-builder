# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""Style frame-time proxy runner (headless Chromium + SwiftShader, fixed preset camera).

It supports:
1) single-package repeated runs (`--viewer-dir`);
2) alternating base/head runs plus AC3 repeats (`--base-viewer-dir` + `--head-viewer-dir`).
"""

from __future__ import annotations

import argparse
import hashlib
import http.server
import json
import os
import socketserver
import subprocess
import threading
import time
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from typing import Any, cast

from demo_bundle import Preset, PresetCamera, load_preset


@dataclass(frozen=True)
class RunResult:
    run_id: str
    glb_sha256: str
    median_ms: float
    renderer: str


def _http_serve(directory: str, host: str, port: int) -> socketserver.TCPServer:
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, directory=directory, **kwargs)

        def log_message(self, format: str, *args: object) -> None:
            return

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


def _wait_result(url: str, timeout_s: float, run_id: str, glb_sha256: str, warmup: int, frames: int) -> dict[str, object]:
    end = time.time() + timeout_s
    while time.time() < end:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status == 200:
                    data = cast("dict[str, object]", json.loads(r.read().decode("utf-8")))
                    if not _matches_expected_result(data, run_id, glb_sha256, warmup, frames):
                        time.sleep(0.2)
                        continue
                    return data
        except OSError:
            pass
        time.sleep(0.2)
    raise TimeoutError("frame-time proxy did not publish results before timeout")


def _matches_expected_result(data: dict[str, object], run_id: str, glb_sha256: str, warmup: int, frames: int) -> bool:
    if str(data.get("run_id", "")) != run_id:
        return False
    if str(data.get("glb_sha256", "")) != glb_sha256:
        return False
    warmup_raw = data.get("warmup_frames", -1)
    if not isinstance(warmup_raw, (int, float)) or int(warmup_raw) != warmup:
        return False
    frames_raw = data.get("measured_frames", -1)
    if not isinstance(frames_raw, (int, float)) or int(frames_raw) != frames:
        return False
    return isinstance(data.get("median_ms"), (int, float))


def _run_once(chrome_cmd: list[str], url: str, timeout_s: float, run_id: str, glb_sha256: str, warmup: int, frames: int) -> RunResult:
    parsed = urllib.parse.urlparse(url)
    result_url = urllib.parse.urlunparse(parsed._replace(path="/frame_time_proxy_result.json", query=""))
    p = subprocess.Popen(
        [
            *chrome_cmd,
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
        out = _wait_result(result_url, timeout_s, run_id, glb_sha256, warmup, frames)
        renderer = str(out.get("renderer", "unknown"))
        median_raw = out.get("median_ms")
        if not isinstance(median_raw, (int, float)):
            raise SystemExit("frame_time_proxy_result.json missing numeric median_ms")
        return RunResult(run_id=run_id, glb_sha256=glb_sha256, median_ms=float(median_raw), renderer=renderer)
    finally:
        p.terminate()
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait(timeout=5)


def _camera_from_preset(preset: Preset, camera_name: str | None) -> PresetCamera:
    if camera_name is None:
        return preset["cameras"][0]
    for c in preset["cameras"]:
        if c["name"] == camera_name:
            return c
    raise SystemExit(f"camera not found in preset: {camera_name}")


def _enu_to_gltf(v: list[float]) -> list[float]:
    return [float(v[0]), float(v[2]), float(-v[1])]


def _make_url(host: str, port: int, camera: PresetCamera, run_id: str, warmup: int, frames: int) -> str:
    eye = camera["eye"]
    target = camera["target"]
    eye_gltf = _enu_to_gltf(eye)
    target_gltf = _enu_to_gltf(target)
    qs = urllib.parse.urlencode(
        {
            "run_id": run_id,
            "warmup": warmup,
            "frames": frames,
            "eye_x": eye_gltf[0],
            "eye_y": eye_gltf[1],
            "eye_z": eye_gltf[2],
            "target_x": target_gltf[0],
            "target_y": target_gltf[1],
            "target_z": target_gltf[2],
            "lens_mm": camera.get("lens_mm", 35),
        }
    )
    return f"http://{host}:{port}/frame_time_proxy.html?{qs}"


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _ensure_swiftshader_renderer(renderer: str, run_id: str) -> None:
    if "swiftshader" not in renderer.lower():
        raise SystemExit(f"renderer is not SwiftShader for run {run_id}: {renderer}")


def _single_mode(args: argparse.Namespace, camera: PresetCamera) -> dict[str, object]:
    viewer = os.path.abspath(args.viewer_dir)
    if not os.path.isfile(os.path.join(viewer, "map.glb")):
        raise SystemExit("viewer-dir must contain map.glb")
    if not os.path.isfile(os.path.join(viewer, "frame_time_proxy.html")):
        raise SystemExit("viewer-dir must contain frame_time_proxy.html")
    httpd = _http_serve(viewer, args.host, args.port)
    try:
        warmup = int(args.warmup)
        frames = int(args.frames)
        result_file = os.path.join(viewer, "frame_time_proxy_result.json")
        glb_sha256 = _sha256_file(os.path.join(viewer, "map.glb"))
        vals: list[float] = []
        run_results: list[dict[str, object]] = []
        renderer = "unknown"
        for _ in range(args.runs):
            run_id = str(uuid.uuid4())
            url = _make_url(args.host, args.port, camera, run_id, warmup, frames)
            if os.path.exists(result_file):
                os.remove(result_file)
            out = _run_once(args.chrome_cmd, url, args.timeout, run_id, glb_sha256, warmup, frames)
            vals.append(out.median_ms)
            _ensure_swiftshader_renderer(out.renderer, out.run_id)
            renderer = out.renderer
            run_results.append(
                {
                    "run_id": out.run_id,
                    "glb_sha256": out.glb_sha256,
                    "median_ms": out.median_ms,
                    "renderer": out.renderer,
                }
            )
        median = sorted(vals)[len(vals) // 2]
        spread_pct = 0.0 if median == 0 else (max(vals) - min(vals)) / median * 100.0
        return {
            "mode": "single",
            "runs_ms": vals,
            "run_results": run_results,
            "median_ms": median,
            "spread_pct": spread_pct,
            "renderer": renderer,
            "execution_label": "swiftshader",
            "interpretation": "relative-only",
            "warmup_frames": warmup,
            "measured_frames": frames,
            "glb_sha256": glb_sha256,
        }
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
        warmup = int(args.warmup)
        frames = int(args.frames)
        base_glb_sha = _sha256_file(os.path.join(base, "map.glb"))
        head_glb_sha = _sha256_file(os.path.join(head, "map.glb"))
        base_runs: list[float] = []
        head_runs: list[float] = []
        base_run_results: list[dict[str, object]] = []
        head_run_results: list[dict[str, object]] = []
        renderer = "unknown"
        base_result_file = os.path.join(base, "frame_time_proxy_result.json")
        head_result_file = os.path.join(head, "frame_time_proxy_result.json")
        for _ in range(args.alternating_pairs):
            base_run_id = str(uuid.uuid4())
            base_url = _make_url(args.host, base_port, camera, base_run_id, warmup, frames)
            if os.path.exists(base_result_file):
                os.remove(base_result_file)
            out_b = _run_once(args.chrome_cmd, base_url, args.timeout, base_run_id, base_glb_sha, warmup, frames)
            _ensure_swiftshader_renderer(out_b.renderer, out_b.run_id)
            head_run_id = str(uuid.uuid4())
            head_url = _make_url(args.host, head_port, camera, head_run_id, warmup, frames)
            if os.path.exists(head_result_file):
                os.remove(head_result_file)
            out_h = _run_once(args.chrome_cmd, head_url, args.timeout, head_run_id, head_glb_sha, warmup, frames)
            _ensure_swiftshader_renderer(out_h.renderer, out_h.run_id)
            base_runs.append(out_b.median_ms)
            head_runs.append(out_h.median_ms)
            base_run_results.append(
                {
                    "run_id": out_b.run_id,
                    "glb_sha256": out_b.glb_sha256,
                    "median_ms": out_b.median_ms,
                    "renderer": out_b.renderer,
                }
            )
            head_run_results.append(
                {
                    "run_id": out_h.run_id,
                    "glb_sha256": out_h.glb_sha256,
                    "median_ms": out_h.median_ms,
                    "renderer": out_h.renderer,
                }
            )
            renderer = out_h.renderer
        repeat_runs: list[float] = []
        repeat_run_results: list[dict[str, object]] = []
        for _ in range(args.repeats):
            repeat_run_id = str(uuid.uuid4())
            if args.repeat_target == "head":
                repeat_url = _make_url(args.host, head_port, camera, repeat_run_id, warmup, frames)
                if os.path.exists(head_result_file):
                    os.remove(head_result_file)
                out = _run_once(args.chrome_cmd, repeat_url, args.timeout, repeat_run_id, head_glb_sha, warmup, frames)
            else:
                repeat_url = _make_url(args.host, base_port, camera, repeat_run_id, warmup, frames)
                if os.path.exists(base_result_file):
                    os.remove(base_result_file)
                out = _run_once(args.chrome_cmd, repeat_url, args.timeout, repeat_run_id, base_glb_sha, warmup, frames)
            _ensure_swiftshader_renderer(out.renderer, out.run_id)
            repeat_runs.append(out.median_ms)
            repeat_run_results.append(
                {
                    "run_id": out.run_id,
                    "glb_sha256": out.glb_sha256,
                    "median_ms": out.median_ms,
                    "renderer": out.renderer,
                }
            )
            renderer = out.renderer
        repeat_median = sorted(repeat_runs)[len(repeat_runs) // 2]
        repeat_spread_pct = 0.0 if repeat_median == 0 else (max(repeat_runs) - min(repeat_runs)) / repeat_median * 100.0
        return {
            "mode": "alternating",
            "base_runs_ms": base_runs,
            "head_runs_ms": head_runs,
            "base_run_results": base_run_results,
            "head_run_results": head_run_results,
            "base_median_ms": sorted(base_runs)[len(base_runs) // 2],
            "head_median_ms": sorted(head_runs)[len(head_runs) // 2],
            "repeat_target": args.repeat_target,
            "repeat_runs_ms": repeat_runs,
            "repeat_run_results": repeat_run_results,
            "repeat_spread_pct": repeat_spread_pct,
            "renderer": renderer,
            "execution_label": "swiftshader",
            "interpretation": "relative-only",
            "warmup_frames": warmup,
            "measured_frames": frames,
            "base_glb_sha256": base_glb_sha,
            "head_glb_sha256": head_glb_sha,
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
    ap.add_argument("--no-sandbox", action="store_true", help="launch Chrome with --no-sandbox (needed where its sandbox cannot access the executable)")
    ap.add_argument("--preset", required=True, help="preset name or preset json path")
    ap.add_argument("--camera", default=None, help="fixed camera name from preset (default first camera)")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--alternating-pairs", type=int, default=3)
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--repeat-target", choices=("base", "head"), default="head")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8781)
    ap.add_argument("--timeout", type=float, default=60.0)
    ap.add_argument("--warmup", type=int, default=60)
    ap.add_argument("--frames", type=int, default=300)
    args = ap.parse_args()
    args.chrome_cmd = [args.chrome, *(["--no-sandbox"] if args.no_sandbox else [])]

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
