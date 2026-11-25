# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""Capture the work vector of one revision (D153): counters and primitive calls per stage, from a frozen cache.

Run once per revision and per backend, with the hash seed fixed, offline:

  PYTHONHASHSEED=0 python -m tools.perf.collect cli --root <tree> --cache <frozen caches> --preset munich \\
      --out-dir <dir>
  PYTHONHASHSEED=0 blender --background --python tools/perf/collect.py -- blender --root <tree> \\
      --cache <frozen caches> --preset munich --out-dir <dir>

``--root`` is the product tree measured (head, or the merge-base + counter-commit worktree); the cache directory
holds ``cache-munich`` and ``cache-pittsburgh``, which are copied afresh for every run. The CLI backend writes
``<preset>.cli_generate.json``; the Blender backend writes ``<preset>.blender_generate.json`` (generate) and
``<preset>.blender_generate_export.json`` (generate then export, cumulative).
"""

from __future__ import annotations

import argparse
import json
import shutil
import socket
import sys
import tempfile
from collections.abc import Sequence
from contextlib import ExitStack
from pathlib import Path
from typing import Any, Final

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.perf.stages import BLENDER_TARGETS, CORE_TARGETS, StageCallProfiler, StageTarget, instrumented  # noqa: E402
from tools.perf.work_vector import (  # noqa: E402
    COUNTERS, GATING_PRESETS, PRIMITIVE_CALLS, applicable_counters, applicable_stages)

SEED: Final = 1
TERRAIN_SPACING_M: Final = 10.0
HEIGHTFIELD_SPACING_M: Final = 2.0
CREATED_UTC: Final = "2026-11-20T00:00:00Z"
# preset -> (centre latitude, centre longitude, width m, height m, package name)
PRESET_AREAS: Final = {
    "munich": (48.1395, 11.5764, 400.0, 400.0, "munich_altstadt"),
    "pittsburgh": (40.437, -80.016, 1200.0, 1000.0, "pittsburgh"),
}


class NetworkAccessError(OSError):
    """A measured run tried to reach the network: a frozen-cache miss."""


def deny_network() -> None:
    def refuse(*_args: Any, **_kwargs: Any) -> Any:
        raise NetworkAccessError("work-count runs are offline: network access denied")
    socket.getaddrinfo = refuse  # type: ignore[assignment]
    socket.create_connection = refuse  # type: ignore[assignment]
    socket.socket.connect = refuse  # type: ignore[method-assign,assignment]


def require_fixed_hash_seed(backend: str) -> None:
    # Blender's embedded interpreter ignores PYTHONHASHSEED; its runs rely on the determinism peer instead.
    if backend == "cli" and sys.flags.hash_randomization:
        raise SystemExit("set PYTHONHASHSEED=0: set iteration order changes the work counts otherwise")


def point_at_tree(root: Path) -> None:
    sys.path.insert(0, str(root))


def fresh_cache_copy(caches: Path, preset: str, scratch: Path) -> Path:
    target = scratch / f"cache-{preset}"
    shutil.copytree(caches / f"cache-{preset}", target)
    return target


class Capture:
    """One instrumented run: counters on, stage wrappers installed, a profile per stage."""

    def __init__(self, targets: Sequence[StageTarget]) -> None:
        from map_builder.core import perf_counters
        self._counters = perf_counters
        self._targets = targets
        self._profiler = StageCallProfiler()
        self._restore = ExitStack()

    def __enter__(self) -> Capture:
        self._counters.reset()
        self._counters.set_enabled(True)
        self._restore.enter_context(instrumented(self._targets, self._profiler, self._counters.stage))
        self._profiler.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self._profiler.stop()
        self._restore.close()
        self._counters.set_enabled(False)

    def vector(self, preset: str, series: str, *, package_valid: bool, run_error: str | None) -> dict[str, Any]:
        """The work vector so far: every applicable counter and stage listed, zeros included."""
        return build_vector(preset, series, self._counters.snapshot(), self._profiler.primitive_calls(),
                            package_valid=package_valid, run_error=run_error)


def build_vector(preset: str, series: str, counters: dict[str, Any], calls_by_stage: dict[str, int], *,
                 package_valid: bool, run_error: str | None) -> dict[str, Any]:
    unknown = sorted(set(counters) - set(COUNTERS))
    if unknown:
        raise SystemExit(f"counters not in the pinned list (adding one is a gated change): {unknown}")
    stages = applicable_stages(series)
    stray = sorted(set(calls_by_stage) - set(stages))
    if stray:
        raise SystemExit(f"primitive calls attributed to stages not applicable to {series}: {stray}")
    values = {name: _stage_row(counters.get(name, {"total": 0, "stages": {}})["stages"], stages)
              for name in applicable_counters(series) if name != PRIMITIVE_CALLS}
    values[PRIMITIVE_CALLS] = _stage_row(calls_by_stage, stages)
    return {"preset": preset, "series": series, "package_valid": package_valid, "run_error": run_error,
            "values": values}


def _stage_row(by_stage: dict[str, int], stages: Sequence[str]) -> dict[str, Any]:
    stray = sorted(set(by_stage) - set(stages))
    if stray:
        raise SystemExit(f"counts charged to stages not applicable to this series: {stray}")
    row = {stage: by_stage.get(stage, 0) for stage in stages}
    return {"total": sum(row.values()), "stages": row}


def write_vector(out_dir: Path, vector: dict[str, Any]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{vector['preset']}.{vector['series']}.json"
    path.write_text(json.dumps(vector, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def collect_cli(root: Path, caches: Path, preset: str, out_dir: Path) -> Path:
    point_at_tree(root)
    from map_builder.core.generate import PlanOptions
    from map_builder.core.geodesy import Area
    from map_builder.core.pipeline import Settings, generate_plan, plan_to_package

    lat, lon, width, height, package_name = PRESET_AREAS[preset]
    with tempfile.TemporaryDirectory(prefix="mb-perf-") as scratch_name:
        scratch = Path(scratch_name)
        settings = Settings(cache_dir=str(fresh_cache_copy(caches, preset, scratch)),
                            terrain_spacing=TERRAIN_SPACING_M, dsm_correction=True,
                            heightfield_spacing=HEIGHTFIELD_SPACING_M, plan_options=PlanOptions(seed=SEED))
        with Capture(CORE_TARGETS) as capture:
            plan, sources = generate_plan(Area(lat, lon, width, height), settings)
            _, result = plan_to_package(plan, str(scratch / "out.mbmap"), package_name, sources, textures=True,
                                        heightfield_spacing=HEIGHTFIELD_SPACING_M, created_utc=CREATED_UTC)
            vector = capture.vector(preset, "cli_generate", package_valid=result.ok, run_error=None)
    return write_vector(out_dir, vector)


def collect_blender(root: Path, caches: Path, preset: str, out_dir: Path) -> list[Path]:
    point_at_tree(root)
    import bpy
    import map_builder

    lat, lon, width, height, package_name = PRESET_AREAS[preset]
    map_builder.register()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    with tempfile.TemporaryDirectory(prefix="mb-perf-") as scratch_name:
        scratch = Path(scratch_name)
        settings = bpy.context.scene.map_builder
        settings.area_mode, settings.centre_lat, settings.centre_lon = "CENTER", repr(lat), repr(lon)
        settings.width, settings.height = width, height
        settings.elevation_source, settings.osm_source = "copernicus", "overpass"
        settings.cache_dir = str(fresh_cache_copy(caches, preset, scratch))
        settings.terrain_spacing, settings.heightfield_spacing = TERRAIN_SPACING_M, HEIGHTFIELD_SPACING_M
        settings.dsm_correction, settings.seed, settings.textures = "ON", SEED, True
        settings.package_name, settings.export_path = package_name, str(scratch / "out.mbmap")
        with Capture(CORE_TARGETS + BLENDER_TARGETS) as capture:
            generated = bpy.ops.map_builder.generate()
            generate_vector = capture.vector(preset, "blender_generate", package_valid=True,
                                             run_error=None if "FINISHED" in generated else f"generate: {generated}")
            exported = bpy.ops.map_builder.export()
            export_vector = capture.vector(preset, "blender_generate_export", package_valid="FINISHED" in exported,
                                           run_error=None if "FINISHED" in exported else f"export: {exported}")
    return [write_vector(out_dir, generate_vector), write_vector(out_dir, export_vector)]


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("backend", choices=("cli", "blender"))
    parser.add_argument("--root", type=Path, required=True, help="product tree to measure")
    parser.add_argument("--cache", type=Path, required=True, help="directory holding cache-<preset> copies")
    parser.add_argument("--preset", choices=GATING_PRESETS, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str]) -> int:
    args = parse_args(argv)
    require_fixed_hash_seed(args.backend)
    deny_network()
    collect = collect_cli if args.backend == "cli" else collect_blender
    written = collect(args.root.resolve(), args.cache.resolve(), args.preset, args.out_dir.resolve())
    print(json.dumps([str(p) for p in ([written] if isinstance(written, Path) else written)]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]))
