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
    median_render_ms: float
    passes: int
    renderer: str

    def record(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "glb_sha256": self.glb_sha256,
            "median_ms": self.median_ms,
            "median_render_ms": self.median_render_ms,
            "passes": self.passes,
            "renderer": self.renderer,
        }


AA_TOLERANCE = 0.03       # C1: head == base, so the ratio must stay within this of 1
C2_MIN_RATIO = 1.10       # C2: a known +100 % render-work increase must read at least this high
D139_MAX_RATIO = 1.10     # D139: the allowed render-time growth of head over merge-base


def render_ratio(base_runs: list[float], head_runs: list[float]) -> float:
    """median(head median_render_ms) / median(base median_render_ms) over the alternating pairs."""
    return _median(head_runs) / _median(base_runs)


def control_verdict(ratio: float, head_passes: int, same_package: bool) -> dict[str, object]:
    """Which rule the ratio answers, and whether it passes: C1 (same package, one pass), C2 (same package, more
    passes), or D139 (different packages, one pass)."""
    if same_package:
        rule, passed = ("C1", abs(ratio - 1.0) <= AA_TOLERANCE) if head_passes == 1 else ("C2", ratio >= C2_MIN_RATIO)
    else:
        if head_passes != 1:
            raise SystemExit("--head-passes above 1 is only valid with the same package on both sides")
        rule, passed = "D139", ratio <= D139_MAX_RATIO
    return {"rule": rule, "ratio": ratio, "passed": passed}


def _median(values: list[float]) -> float:
    return sorted(values)[len(values) // 2]


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


def _wait_result(url: str, timeout_s: float, run_id: str, glb_sha256: str, warmup: int, frames: int, passes: int) -> dict[str, object]:
    end = time.time() + timeout_s
    while time.time() < end:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status == 200:
                    data = cast("dict[str, object]", json.loads(r.read().decode("utf-8")))
                    if not _matches_expected_result(data, run_id, glb_sha256, warmup, frames, passes):
                        time.sleep(0.2)
                        continue
                    return data
        except OSError:
            pass
        time.sleep(0.2)
    raise TimeoutError("frame-time proxy did not publish results before timeout")


def _matches_expected_result(data: dict[str, object], run_id: str, glb_sha256: str, warmup: int, frames: int, passes: int) -> bool:
    if str(data.get("run_id", "")) != run_id:
        return False
    if str(data.get("glb_sha256", "")) != glb_sha256:
        return False
    for key, expected in (("warmup_frames", warmup), ("measured_frames", frames), ("passes", passes)):
        raw = data.get(key, -1)
        if not isinstance(raw, (int, float)) or int(raw) != expected:
            return False
    return all(isinstance(data.get(key), (int, float)) for key in ("median_ms", "median_render_ms"))


def _run_once(chrome_cmd: list[str], url: str, timeout_s: float, run_id: str, glb_sha256: str, warmup: int, frames: int,
              passes: int) -> RunResult:
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
        out = _wait_result(result_url, timeout_s, run_id, glb_sha256, warmup, frames, passes)
        return RunResult(run_id=run_id, glb_sha256=glb_sha256, median_ms=float(cast("float", out["median_ms"])),
                         median_render_ms=float(cast("float", out["median_render_ms"])), passes=passes,
                         renderer=str(out.get("renderer", "unknown")))
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


def _make_url(host: str, port: int, camera: PresetCamera, run_id: str, warmup: int, frames: int, passes: int = 1) -> str:
    eye = camera["eye"]
    target = camera["target"]
    eye_gltf = _enu_to_gltf(eye)
    target_gltf = _enu_to_gltf(target)
    qs = urllib.parse.urlencode(
        {
            "run_id": run_id,
            "warmup": warmup,
            "frames": frames,
            "passes": passes,
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


def _timed_run(args: argparse.Namespace, camera: PresetCamera, port: int, glb_sha256: str, passes: int,
               result_file: str) -> RunResult:
    run_id = str(uuid.uuid4())
    url = _make_url(args.host, port, camera, run_id, int(args.warmup), int(args.frames), passes)
    if os.path.exists(result_file):
        os.remove(result_file)
    out = _run_once(args.chrome_cmd, url, args.timeout, run_id, glb_sha256, int(args.warmup), int(args.frames), passes)
    _ensure_swiftshader_renderer(out.renderer, out.run_id)
    return out


def _single_mode(args: argparse.Namespace, camera: PresetCamera) -> dict[str, object]:
    viewer = os.path.abspath(args.viewer_dir)
    if not os.path.isfile(os.path.join(viewer, "map.glb")):
        raise SystemExit("viewer-dir must contain map.glb")
    if not os.path.isfile(os.path.join(viewer, "frame_time_proxy.html")):
        raise SystemExit("viewer-dir must contain frame_time_proxy.html")
    httpd = _http_serve(viewer, args.host, args.port)
    try:
        result_file = os.path.join(viewer, "frame_time_proxy_result.json")
        glb_sha256 = _sha256_file(os.path.join(viewer, "map.glb"))
        runs = [_timed_run(args, camera, args.port, glb_sha256, 1, result_file) for _ in range(args.runs)]
        vals = [r.median_ms for r in runs]
        median = _median(vals)
        spread_pct = 0.0 if median == 0 else (max(vals) - min(vals)) / median * 100.0
        return {
            "mode": "single",
            "runs_ms": vals,
            "run_results": [r.record() for r in runs],
            "median_ms": median,
            "median_render_ms": _median([r.median_render_ms for r in runs]),
            "spread_pct": spread_pct,
            "renderer": runs[-1].renderer if runs else "unknown",
            "execution_label": "swiftshader",
            "interpretation": "relative-only",
            "warmup_frames": int(args.warmup),
            "measured_frames": int(args.frames),
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
        base_glb_sha = _sha256_file(os.path.join(base, "map.glb"))
        head_glb_sha = _sha256_file(os.path.join(head, "map.glb"))
        base_result_file = os.path.join(base, "frame_time_proxy_result.json")
        head_result_file = os.path.join(head, "frame_time_proxy_result.json")
        base_results: list[RunResult] = []
        head_results: list[RunResult] = []
        for _ in range(args.alternating_pairs):
            base_results.append(_timed_run(args, camera, base_port, base_glb_sha, 1, base_result_file))
            head_results.append(_timed_run(args, camera, head_port, head_glb_sha, args.head_passes, head_result_file))
        repeat_results = [
            _timed_run(args, camera, head_port, head_glb_sha, args.head_passes, head_result_file)
            if args.repeat_target == "head"
            else _timed_run(args, camera, base_port, base_glb_sha, 1, base_result_file)
            for _ in range(args.repeats)
        ]
        repeat_runs = [r.median_ms for r in repeat_results]
        repeat_median = _median(repeat_runs) if repeat_runs else 0.0
        repeat_spread_pct = 0.0 if repeat_median == 0 else (max(repeat_runs) - min(repeat_runs)) / repeat_median * 100.0
        base_render = [r.median_render_ms for r in base_results]
        head_render = [r.median_render_ms for r in head_results]
        ratio = render_ratio(base_render, head_render)
        return {
            "mode": "alternating",
            "base_runs_ms": [r.median_ms for r in base_results],
            "head_runs_ms": [r.median_ms for r in head_results],
            "base_render_runs_ms": base_render,
            "head_render_runs_ms": head_render,
            "base_run_results": [r.record() for r in base_results],
            "head_run_results": [r.record() for r in head_results],
            "base_median_ms": _median([r.median_ms for r in base_results]),
            "head_median_ms": _median([r.median_ms for r in head_results]),
            "base_median_render_ms": _median(base_render),
            "head_median_render_ms": _median(head_render),
            "head_passes": args.head_passes,
            "ratio": ratio,
            "verdict": control_verdict(ratio, args.head_passes, base_glb_sha == head_glb_sha),
            "repeat_target": args.repeat_target,
            "repeat_runs_ms": repeat_runs,
            "repeat_run_results": [r.record() for r in repeat_results],
            "repeat_spread_pct": repeat_spread_pct,
            "renderer": head_results[-1].renderer if head_results else "unknown",
            "execution_label": "swiftshader",
            "interpretation": "relative-only",
            "warmup_frames": int(args.warmup),
            "measured_frames": int(args.frames),
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
    ap.add_argument("--head-passes", type=int, default=1, help="render passes per frame on the head side only (known-slowdown control)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8781)
    ap.add_argument("--timeout", type=float, default=60.0)
    ap.add_argument("--warmup", type=int, default=60)
    ap.add_argument("--frames", type=int, default=300)
    args = ap.parse_args()
    args.chrome_cmd = [args.chrome, *(["--no-sandbox"] if args.no_sandbox else [])]
    if args.head_passes < 1:
        raise SystemExit("--head-passes must be at least 1")

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
