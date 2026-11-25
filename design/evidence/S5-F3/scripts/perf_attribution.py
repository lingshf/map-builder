# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""Per-strip attribution of the D153 shore-ramp work (D179 waiver evidence).

``record`` runs the CLI plan of a preset on one tree under the gate's own ``Capture`` and writes, for every
strip ``_place_strip`` sees, the ``clip_steps`` and ``overlap_edge_tests`` charged to each of its tests
(``blocked_by``, ``wet_by``, ``trim``) and the strip's outcome, plus the ``_water_stage`` primitive calls per
function. ``compare`` joins a base and a head record by strip and splits the growth by cause.

    PYTHONHASHSEED=0 py -3.12 perf_attribution.py record --root TREE --cache CACHES --preset pittsburgh --out F
    py -3.12 perf_attribution.py compare BASE.json HEAD.json --out SPLIT.json
"""

from __future__ import annotations

import argparse
import json
import os
import pstats
import sys
import tempfile
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[4]
WORK_COUNTERS = ("clip_steps", "overlap_edge_tests")
STRIP_TESTS = ("blocked_by", "wet_by", "trim")
KEY_DECIMALS = 3
TOP_FUNCTIONS = 15
BUILTIN_PATH = "~"


def _work(counters: Any) -> dict[str, int]:
    snapshot = counters.snapshot()
    return {name: snapshot.get(name, {"total": 0})["total"] for name in WORK_COUNTERS}


def _minus(after: dict[str, int], before: dict[str, int]) -> dict[str, int]:
    return {name: after[name] - before[name] for name in WORK_COUNTERS}


def _strip_key(a: Any, b: Any) -> str:
    return " ".join(f"{v:.{KEY_DECIMALS}f}" for v in (a.top[0], a.top[1], b.top[0], b.top[1]))


class StripRecorder:
    """Wraps ``shore._place_strip`` and charges each strip's counter deltas to the test that spent them."""

    def __init__(self, shore: Any, counters: Any) -> None:
        self._shore = shore
        self._counters = counters
        self._original = shore._place_strip
        self.strips: list[dict[str, Any]] = []
        self._seen: Counter[str] = Counter()

    def __enter__(self) -> StripRecorder:
        self._shore._place_strip = self._place
        return self

    def __exit__(self, *_exc: object) -> None:
        self._shore._place_strip = self._original

    def _metered(self, spent: dict[str, int], test: Callable[..., Any], seen: StripEvents) -> Callable[..., Any]:
        def run(*args: Any) -> Any:
            before = _work(self._counters)
            result = test(*args)
            for name, amount in _minus(_work(self._counters), before).items():
                spent[name] += amount
            seen.tested = True
            return result
        return run

    def _metered_trim(self, spent: dict[str, int], trim: Callable[..., Any], seen: StripEvents) -> Callable[..., Any]:
        metered = self._metered(spent, trim, seen)

        def run(tri: Any) -> Any:
            parts = metered(tri)
            seen.cut |= parts != [tri]
            return parts
        return run

    def _place(self, out: Any, a: Any, b: Any, blocked_by: Callable[..., Any], wet_by: Callable[..., Any],
               *trim: Callable[..., Any]) -> None:
        spent = {test: dict.fromkeys(WORK_COUNTERS, 0) for test in STRIP_TESTS}
        seen = StripEvents()
        metered = [self._metered(spent["blocked_by"], blocked_by, seen), self._metered(spent["wet_by"], wet_by, seen)]
        metered += [self._metered_trim(spent["trim"], test, seen) for test in trim]
        placed_before = len(out.bank) + len(out.cascade)
        self._original(out, a, b, *metered)
        key = _strip_key(a, b)
        self._seen[key] += 1
        self.strips.append({"key": f"{key} #{self._seen[key]}", "work": spent,
                            "outcome": seen.outcome(len(out.bank) + len(out.cascade) > placed_before)})


class StripEvents:
    """What happened to one strip: whether any test ran and whether the trim cut part of it."""

    def __init__(self) -> None:
        self.tested = False
        self.cut = False

    def outcome(self, placed: bool) -> str:
        """``empty`` (no triangles, so no test ran), ``kept`` whole, ``trimmed`` (the trim cut part),
        ``trimmed_away`` (the trim cut all of it) or ``dropped`` by a mask or the wet test."""
        if not self.tested:
            return "empty"
        if placed:
            return "trimmed" if self.cut else "kept"
        return "trimmed_away" if self.cut else "dropped"


def _calls_by_function(profile: Any) -> dict[str, int]:
    """Primitive calls per Python function; a builtin's calls are charged to the functions that made them."""
    calls: Counter[str] = Counter()
    stats = pstats.Stats(profile).stats  # type: ignore[attr-defined]  # public at runtime, missing from typeshed
    for (path, _line, name), (primitive, _total, _own, _cumulative, callers) in stats.items():
        if path != BUILTIN_PATH:
            calls[f"{Path(path).name}:{name}"] += primitive
            continue
        for (caller_path, _caller_line, caller_name), (caller_calls, *_rest) in callers.items():
            calls[f"{Path(caller_path).name}:{caller_name}"] += caller_calls
    return dict(calls)


def record(root: Path, caches: Path, preset: str, out: Path) -> Path:
    sys.path[:0] = [str(root), str(REPO)]
    from tools.perf.collect import (CORE_TARGETS, HEIGHTFIELD_SPACING_M, PRESET_AREAS, SEED,
                                    TERRAIN_SPACING_M, Capture, fresh_cache_copy, require_fixed_hash_seed)
    from map_builder.core import perf_counters, shore
    from map_builder.core.generate import PlanOptions
    from map_builder.core.geodesy import Area
    from map_builder.core.pipeline import Settings, generate_plan

    require_fixed_hash_seed("cli")
    lat, lon, width, height, _name = PRESET_AREAS[preset]
    with tempfile.TemporaryDirectory(prefix="mb-attr-") as scratch:
        settings = Settings(cache_dir=str(fresh_cache_copy(caches, preset, Path(scratch))),
                            terrain_spacing=TERRAIN_SPACING_M, dsm_correction=True,
                            heightfield_spacing=HEIGHTFIELD_SPACING_M, plan_options=PlanOptions(seed=SEED))
        with Capture(CORE_TARGETS) as capture, StripRecorder(shore, perf_counters) as strips:
            generate_plan(Area(lat, lon, width, height), settings)
            totals = _work(perf_counters)
            water_profile = capture._profiler._profiles.get("_water_stage")
            water_calls = _calls_by_function(water_profile) if water_profile else {}
    path = out / f"attribution-{preset}-{root.name}.json"
    path.write_text(json.dumps({"root": str(root), "preset": preset, "totals": totals, "strips": strips.strips,
                                "water_stage_calls": water_calls}, indent=1), encoding="utf-8")
    return path


def _strip_total(strip: dict[str, Any], tests: tuple[str, ...] = STRIP_TESTS) -> dict[str, int]:
    return {name: sum(strip["work"][test][name] for test in tests) for name in WORK_COUNTERS}


def _change_class(before: dict[str, Any], after: dict[str, Any]) -> str:
    if before["outcome"] == after["outcome"] and _strip_total(before) == _strip_total(after):
        return "unchanged"
    return f"{before['outcome']}_to_{after['outcome']}"


def _add(into: dict[str, int], amounts: dict[str, int], sign: int = 1) -> None:
    for name in WORK_COUNTERS:
        into[name] = into.get(name, 0) + sign * amounts[name]


def compare(base_path: Path, head_path: Path, out: Path) -> dict[str, Any]:
    base, head = (json.loads(p.read_text(encoding="utf-8")) for p in (base_path, head_path))
    before = {strip["key"]: strip for strip in base["strips"]}
    after = {strip["key"]: strip for strip in head["strips"]}
    classes: dict[str, dict[str, Any]] = {}
    for key in sorted(before.keys() & after.keys()):
        row = classes.setdefault(_change_class(before[key], after[key]),
                                 {"strips": 0, "growth": {}, "growth_by_test": {t: {} for t in STRIP_TESTS}})
        row["strips"] += 1
        _add(row["growth"], _strip_total(after[key]))
        _add(row["growth"], _strip_total(before[key]), -1)
        for test in STRIP_TESTS:
            _add(row["growth_by_test"][test], after[key]["work"][test])
            _add(row["growth_by_test"][test], before[key]["work"][test], -1)
    calls = {name: head["water_stage_calls"].get(name, 0) - base["water_stage_calls"].get(name, 0)
             for name in base["water_stage_calls"].keys() | head["water_stage_calls"].keys()}
    split = {"base_totals": base["totals"], "head_totals": head["totals"],
             "strips_only_in_base": sorted(before.keys() - after.keys()),
             "strips_only_in_head": sorted(after.keys() - before.keys()), "classes": classes,
             "water_stage_calls_growth": sum(calls.values()),
             "water_stage_calls_top": dict(sorted(((n, d) for n, d in calls.items() if d),
                                                  key=lambda item: -abs(item[1]))[:TOP_FUNCTIONS])}
    out.write_text(json.dumps(split, indent=1), encoding="utf-8")
    return split


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    record_cmd = commands.add_parser("record")
    record_cmd.add_argument("--root", type=Path, required=True)
    record_cmd.add_argument("--cache", type=Path, required=True)
    record_cmd.add_argument("--preset", required=True)
    record_cmd.add_argument("--out", type=Path, required=True)
    compare_cmd = commands.add_parser("compare")
    compare_cmd.add_argument("base", type=Path)
    compare_cmd.add_argument("head", type=Path)
    compare_cmd.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "record":
        print(record(args.root.resolve(), args.cache, args.preset, args.out))
    else:
        print(json.dumps(compare(args.base, args.head, args.out), indent=1))


if __name__ == "__main__":
    os.environ.setdefault("MAP_BUILDER_PERF_COUNTERS", "1")
    main()
