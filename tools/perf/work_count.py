# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""Deterministic work-vector checker for S5-PERF-GATE (D153).

This checker has two responsibilities:
1) validate and compare deterministic work vectors under F1..F6;
2) prepare merge-base+counter-commit temporary worktrees used as the base revision.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Final, Iterable


COUNTERS: Final[tuple[str, ...]] = (
    "tri_emitted[building]",
    "tri_emitted[road]",
    "tri_emitted[terrain]",
    "tri_emitted[vegetation]",
    "tri_emitted[water]",
    "ring_edge_tests",
    "clip_steps",
    "overlap_pairs",
    "overlap_edge_tests",
    "candidate_pairs",
    "grid_cells",
    "deflate_in_bytes",
    "bytes_written[manifest.json]",
    "bytes_written[visual/map.glb]",
    "bytes_written[collision/map.mbcol]",
    "bytes_written[collision/terrain.mbhf]",
    "bytes_written[report.json]",
    "bytes_written[NOTICES.txt]",
    "validator_pairs",
    "bpy_mesh_vertices",
    "primitive_calls",
)

STAGES: Final[tuple[str, ...]] = (
    "acquire",
    "build_plan",
    "_water_stage",
    "shore_ramps",
    "build_terrain",
    "buildings_roofs",
    "roads",
    "bridges",
    "tunnels",
    "build_scene",
    "package_write",
    "validate_package",
    "other",
)

SERIES: Final[tuple[str, ...]] = ("cli_generate", "blender_generate", "blender_generate_export")
GATING_PRESETS: Final[tuple[str, ...]] = ("munich", "pittsburgh")

NOT_APPLICABLE: Final[dict[str, set[str]]] = {
    "cli_generate": {"bpy_mesh_vertices"},
    "blender_generate": {"bytes_written[manifest.json]", "bytes_written[visual/map.glb]",
                         "bytes_written[collision/map.mbcol]", "bytes_written[collision/terrain.mbhf]",
                         "bytes_written[report.json]", "bytes_written[NOTICES.txt]",
                         "deflate_in_bytes", "validator_pairs"},
    "blender_generate_export": set(),
}


class Rule(str, Enum):
    F1 = "F1"
    F2 = "F2"
    F3 = "F3"
    F4 = "F4"
    F5 = "F5"
    F6 = "F6"


@dataclass(frozen=True)
class RuleEvent:
    rule: Rule
    message: str


@dataclass(frozen=True)
class WorkValue:
    total: int
    stages: dict[str, int]


@dataclass(frozen=True)
class WorkVector:
    preset: str
    series: str
    values: dict[str, WorkValue]
    package_valid: bool = True
    run_error: str | None = None


@dataclass(frozen=True)
class CompareOptions:
    cpu_ratio: float | None = None
    uncounted_sites: tuple[str, ...] = ()
    noop_expected: bool = False


def _ratio(head: int, base: int) -> float:
    if base == 0:
        return 0.0 if head == 0 else float("inf")
    return (head - base) / base


def _ensure_vector_shape(v: WorkVector) -> list[RuleEvent]:
    errors: list[RuleEvent] = []
    if v.run_error:
        errors.append(RuleEvent(Rule.F1, f"run error: {v.run_error}"))
    if not v.package_valid:
        errors.append(RuleEvent(Rule.F1, "package is not VALID"))
    if v.series not in SERIES:
        errors.append(RuleEvent(Rule.F1, f"unknown series {v.series!r}"))
        return errors
    na = NOT_APPLICABLE[v.series]
    for name in COUNTERS:
        if name in na:
            continue
        if name not in v.values:
            errors.append(RuleEvent(Rule.F1, f"missing counter {name}"))
            continue
        w = v.values[name]
        stage_sum = sum(w.stages.get(s, 0) for s in STAGES)
        if stage_sum != w.total:
            errors.append(RuleEvent(Rule.F1, f"stage sum mismatch for {name}: {stage_sum} != {w.total}"))
        for stage in w.stages:
            if stage not in STAGES:
                errors.append(RuleEvent(Rule.F1, f"unknown stage {stage!r} for {name}"))
    return errors


def _f1_determinism(v1: WorkVector, v2: WorkVector) -> list[RuleEvent]:
    if (v1.preset, v1.series) != (v2.preset, v2.series):
        return [RuleEvent(Rule.F1, "determinism inputs mismatch in preset/series")]
    if set(v1.values) != set(v2.values):
        return [RuleEvent(Rule.F1, "determinism inputs mismatch in counter keys")]
    errors: list[RuleEvent] = []
    for name in sorted(v1.values):
        a = v1.values[name]
        b = v2.values[name]
        if a.total != b.total:
            errors.append(RuleEvent(Rule.F1, f"determinism mismatch for {name}: {a.total} != {b.total}"))
            continue
        if a.stages != b.stages:
            errors.append(RuleEvent(Rule.F1, f"determinism stage mismatch for {name}"))
    return errors


def compare(base: WorkVector, head: WorkVector, opts: CompareOptions | None = None) -> list[RuleEvent]:
    opts = opts or CompareOptions()
    events: list[RuleEvent] = []
    events.extend(_ensure_vector_shape(base))
    events.extend(_ensure_vector_shape(head))
    if base.series != head.series or base.preset != head.preset:
        events.append(RuleEvent(Rule.F1, "base/head vector identity mismatch"))
        return events
    if any(e.rule == Rule.F1 for e in events):
        return events

    na = NOT_APPLICABLE[base.series]
    for name in COUNTERS:
        if name in na:
            continue
        b = base.values[name]
        h = head.values[name]
        dr = _ratio(h.total, b.total)
        if dr > 0.05:
            events.append(RuleEvent(Rule.F2, f"{name} total ratio {dr:.3%} exceeds +5%"))
        for stage in STAGES:
            bs = b.stages.get(stage, 0)
            hs = h.stages.get(stage, 0)
            sr = _ratio(hs, bs)
            if sr > 0.10 and (hs - bs) > b.total * 0.01:
                events.append(RuleEvent(Rule.F3, f"{name} stage {stage} ratio {sr:.3%} exceeds F3"))
            if sr > 0.05:
                events.append(RuleEvent(Rule.F4, f"{name} stage {stage} grew {sr:.3%}"))

    if opts.cpu_ratio is not None and opts.cpu_ratio > 0.05:
        events.append(RuleEvent(Rule.F5, f"cpu ratio {opts.cpu_ratio:.3%} exceeds +5%"))
    if opts.uncounted_sites:
        events.append(RuleEvent(Rule.F6, "uncounted work declared: " + ", ".join(opts.uncounted_sites)))

    if opts.noop_expected:
        for e in events:
            if e.rule in (Rule.F1, Rule.F2, Rule.F3, Rule.F4, Rule.F5, Rule.F6):
                return [RuleEvent(Rule.F1, f"no-op expected, but got {e.rule.value}: {e.message}")]
    return events


def _parse_vector(path: str) -> WorkVector:
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    values: dict[str, WorkValue] = {}
    for name, item in raw["values"].items():
        values[name] = WorkValue(total=int(item["total"]),
                                 stages={str(k): int(v) for k, v in item["stages"].items()})
    return WorkVector(
        preset=str(raw["preset"]),
        series=str(raw["series"]),
        values=values,
        package_valid=bool(raw.get("package_valid", True)),
        run_error=raw.get("run_error"),
    )


def _emit(events: list[RuleEvent]) -> int:
    out = [{"rule": e.rule.value, "message": e.message} for e in events]
    print(json.dumps({"events": out}, indent=2, sort_keys=True))
    return 1 if any(e.rule in (Rule.F1, Rule.F2, Rule.F3) for e in events) else 0


def _run_git(cwd: Path, args: Iterable[str]) -> str:
    cp = subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True)
    return cp.stdout.strip()


def prepare_merge_base_worktree(repo: Path, *, head_ref: str, base_ref: str, counter_commit: str,
                                keep: bool = False) -> dict[str, str]:
    merge_base = _run_git(repo, ["merge-base", head_ref, base_ref]).strip()
    tmp_root = Path(tempfile.mkdtemp(prefix="mb-perf-base-"))
    wt = tmp_root / "worktree"
    try:
        _run_git(repo, ["worktree", "add", "--detach", str(wt), merge_base])
        try:
            _run_git(wt, ["cherry-pick", "--no-commit", counter_commit])
        except subprocess.CalledProcessError as exc:
            # explicit F1 failure signal for the checker caller
            _run_git(wt, ["cherry-pick", "--abort"])
            raise RuntimeError("F1: counter commit does not apply cleanly to merge-base") from exc
        _run_git(wt, ["reset"])  # keep the applied index/worktree only
        out = {
            "merge_base": merge_base,
            "worktree_path": str(wt),
            "counter_commit": counter_commit,
        }
        if not keep:
            out["cleanup_hint"] = "run `git worktree remove <path> --force` when done"
        return out
    except Exception:
        if not keep:
            shutil.rmtree(tmp_root, ignore_errors=True)
        raise


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    cmp_ap = sub.add_parser("compare", help="compare base/head work vectors under F1..F6")
    cmp_ap.add_argument("--base", required=True, help="base vector json")
    cmp_ap.add_argument("--head", required=True, help="head vector json")
    cmp_ap.add_argument("--cpu-ratio", type=float, default=None, help="optional cpu delta as ratio (0.06 = +6%%)")
    cmp_ap.add_argument("--uncounted-site", action="append", default=None, help="declare uncounted work site(s)")
    cmp_ap.add_argument("--noop", action="store_true", help="assert no-op case")
    cmp_ap.add_argument("--determinism-peer", default=None, help="second run vector of same revision for F1")

    prep_ap = sub.add_parser("prepare-base", help="create merge-base+C temporary worktree")
    prep_ap.add_argument("--repo", default=".", help="repository root")
    prep_ap.add_argument("--head-ref", default="HEAD", help="head ref")
    prep_ap.add_argument("--base-ref", default="origin/main", help="base ref")
    prep_ap.add_argument("--counter-commit", required=True, help="isolated counter commit C")
    prep_ap.add_argument("--keep", action="store_true", help="keep the temporary root folder")

    a = ap.parse_args(argv)
    if a.cmd == "prepare-base":
        out = prepare_merge_base_worktree(
            Path(a.repo).resolve(),
            head_ref=str(a.head_ref),
            base_ref=str(a.base_ref),
            counter_commit=str(a.counter_commit),
            keep=bool(a.keep),
        )
        print(json.dumps(out, indent=2, sort_keys=True))
        return 0

    base = _parse_vector(a.base)
    head = _parse_vector(a.head)
    events: list[RuleEvent] = []
    if a.determinism_peer:
        events.extend(_f1_determinism(head, _parse_vector(a.determinism_peer)))
    events.extend(compare(base, head, CompareOptions(
        cpu_ratio=a.cpu_ratio,
        uncounted_sites=tuple(a.uncounted_site or ()),
        noop_expected=a.noop,
    )))
    return _emit(events)


if __name__ == "__main__":
    raise SystemExit(main())
