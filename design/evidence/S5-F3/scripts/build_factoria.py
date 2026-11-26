# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 lingshf
"""S5-F3 evidence harness (not product code): acquire, freeze and build the real-data presets.

  py -3.12 build_factoria.py acquire --root <tree> --cache <dir>/cache-bellevue-factoria
  py -3.12 build_factoria.py manifest --cache <dir>/cache-bellevue-factoria
  py -3.12 build_factoria.py cli --root <tree> --cache <dir> --preset <p> --out <pkg>
  blender -b --factory-startup --python build_factoria.py -- blender --root <tree> --cache <dir> --preset <p> --out <pkg>

Settings as every preset (S5-STYLE, D157): seed 1, DSM on, terrain 10 m, heightfield 2 m, textured, created_utc
pinned on both paths. ``--preset sample`` builds the headless run's synthetic fixtures through Blender. ``cli`` and
``blender`` copy the frozen cache afresh and deny the network, so a cache miss fails.
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import socket
import sys
import tempfile
from pathlib import Path
from typing import Any

SEED = 1
TERRAIN_SPACING_M = 10.0
HEIGHTFIELD_SPACING_M = 2.0
CREATED_UTC = "2026-11-20T00:00:00Z"
MANIFEST_NAME = "MANIFEST-sha256.txt"
# preset -> (centre latitude, centre longitude, width m, height m, package name)
PRESET_AREAS = {
    "bellevue-factoria": (47.5790, -122.1790, 1600.0, 1400.0, "bellevue_factoria"),
    "munich": (48.1395, 11.5764, 400.0, 400.0, "munich_altstadt"),
    "pittsburgh": (40.437, -80.016, 1200.0, 1000.0, "pittsburgh"),
}
SAMPLE = "sample"   # the headless run's synthetic fixtures; Blender only (the CLI sample is examples/)


def deny_network() -> None:
    def refuse(*_args: Any, **_kwargs: Any) -> Any:
        raise OSError("offline build: network access denied (frozen-cache miss)")
    socket.getaddrinfo = refuse  # type: ignore[assignment]
    socket.create_connection = refuse  # type: ignore[assignment]
    socket.socket.connect = refuse  # type: ignore[method-assign,assignment]


def fresh_cache_copy(caches: Path, preset: str, scratch: Path) -> Path:
    target = scratch / f"cache-{preset}"
    shutil.copytree(caches / f"cache-{preset}", target, ignore=shutil.ignore_patterns(MANIFEST_NAME))
    return target


def cli_settings(cache_dir: str) -> Any:
    from map_builder.core.generate import PlanOptions
    from map_builder.core.pipeline import Settings
    return Settings(cache_dir=cache_dir, terrain_spacing=TERRAIN_SPACING_M, dsm_correction=True,
                    heightfield_spacing=HEIGHTFIELD_SPACING_M, plan_options=PlanOptions(seed=SEED))


def build_cli(preset: str, cache_dir: str, out: Path) -> bool:
    from map_builder.core.geodesy import Area
    from map_builder.core.pipeline import generate_plan, plan_to_package
    lat, lon, width, height, name = PRESET_AREAS[preset]
    plan, sources = generate_plan(Area(lat, lon, width, height), cli_settings(cache_dir))
    _, result = plan_to_package(plan, str(out), name, sources, textures=True,
                                heightfield_spacing=HEIGHTFIELD_SPACING_M, created_utc=CREATED_UTC)
    return bool(result.ok)


def pin_created_utc() -> None:
    """Pin the manifest timestamp of the Blender export, whose operator takes no ``created_utc``: a harness-only stub
    of ``map_builder.core.package.time``, as for #74. Production timestamps are untouched."""
    import time
    from types import SimpleNamespace
    from map_builder.core import package
    fixed = time.strptime(CREATED_UTC, "%Y-%m-%dT%H:%M:%SZ")
    package.time = SimpleNamespace(gmtime=lambda *_: fixed, strftime=time.strftime)  # type: ignore[assignment]


def configure_preset(s: Any, preset: str, cache_dir: str) -> str:
    lat, lon, width, height, name = PRESET_AREAS[preset]
    s.area_mode, s.centre_lat, s.centre_lon = "CENTER", repr(lat), repr(lon)
    s.width, s.height = width, height
    s.elevation_source, s.osm_source = "copernicus", "overpass"
    s.cache_dir = cache_dir
    s.terrain_spacing, s.heightfield_spacing = TERRAIN_SPACING_M, HEIGHTFIELD_SPACING_M
    s.dsm_correction, s.seed, s.textures = "ON", SEED, True
    return name


def configure_sample(s: Any) -> str:
    """The sample fixtures exactly as the headless run of the same tree builds them (``it.mbmap``)."""
    from tests.blender import checks_core as it
    s.area_mode, s.centre_lat, s.centre_lon = "CENTER", str(it.LAT), str(it.LON)
    s.width, s.height = it.WIDTH, it.HEIGHT
    s.elevation_source, s.elevation_file = "file", str(Path(it.FIXTURES) / "synthetic_dem.asc")
    s.elevation_crs, s.elevation_vertical_datum = "EPSG:4326", "SYNTHETIC"
    s.elevation_license = "SYNTHETIC test data (no licence required)"
    s.osm_source, s.osm_file = "file", str(Path(it.FIXTURES) / "synthetic_area.osm")
    s.terrain_spacing, s.heightfield_spacing = 10.0, 2.0
    return "it"


def build_blender(preset: str, cache_dir: str, out: Path) -> bool:
    import bpy
    import map_builder
    map_builder.register()
    pin_created_utc()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    s = bpy.context.scene.map_builder
    name = configure_sample(s) if preset == SAMPLE else configure_preset(s, preset, cache_dir)
    s.package_name, s.export_path = name, str(out)
    return all("FINISHED" in op() for op in (bpy.ops.map_builder.generate, bpy.ops.map_builder.export))


def write_manifest(cache: Path) -> str:
    """Per-file SHA-256 (sorted relative paths) and the combined SHA-256 over those lines."""
    lines = [f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(cache).as_posix()}"
             for p in sorted(cache.rglob("*")) if p.is_file() and p.name != MANIFEST_NAME]
    combined = hashlib.sha256("\n".join(lines).encode()).hexdigest()
    (cache / MANIFEST_NAME).write_text("\n".join(lines) + f"\ncombined  {combined}\n", encoding="utf-8")
    return combined


def parse_args(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("acquire", "manifest", "cli", "blender"))
    ap.add_argument("--root", type=Path)
    ap.add_argument("--cache", type=Path, required=True)
    ap.add_argument("--preset", default="bellevue-factoria", choices=sorted(PRESET_AREAS) + [SAMPLE])
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    if a.preset == SAMPLE and a.mode != "blender":
        ap.error("--preset sample builds through Blender only; the CLI sample is examples/synthetic_sample.mbmap")
    return a


def main(argv: list[str]) -> int:
    a = parse_args(argv)
    if a.root:
        sys.path.insert(0, str(a.root))
    if a.mode == "manifest":
        print("combined", write_manifest(a.cache))
        return 0
    if a.mode == "acquire":
        with tempfile.TemporaryDirectory(prefix="mb-s5f3-") as scratch:
            ok = build_cli("bellevue-factoria", str(a.cache), Path(scratch) / "acquire.mbmap")
        print("acquire build valid:", ok)
        return 0 if ok else 1
    deny_network()
    with tempfile.TemporaryDirectory(prefix="mb-s5f3-") as scratch:
        cache_dir = "" if a.preset == SAMPLE else str(fresh_cache_copy(a.cache, a.preset, Path(scratch)))
        ok = (build_cli if a.mode == "cli" else build_blender)(a.preset, cache_dir, a.out)
    print(f"{a.mode} {a.preset} valid: {ok} -> {a.out}")
    return 0 if ok else 1


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    sys.exit(main(args))
