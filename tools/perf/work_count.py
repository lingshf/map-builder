# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""Work-count gate of S5-PERF-GATE (D153): compare two work vectors under F1..F6.

  collect.py                     captures a revision's work vector (see tools/perf/collect.py)
  work_count.py compare          F1 completeness, F2 series total, F3 stage; F4/F5/F6 are listed for review
  work_count.py prepare-base     builds the merge-base + counter-commit worktree used as the base revision

F1-F3 fail the revision (exit 1). F4, F5 and F6 are review gates: they are printed, and the reviewer accepts or
rejects each listed item explicitly. See docs/dev/tools.md for the workflow.
"""

from __future__ import annotations

import argparse
import json
import shutil
import statistics
import subprocess
import tempfile
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Final

from tools.perf.work_vector import (
    Rule, RuleEvent, WorkValue, WorkVector, applicable_counters, applicable_stages, check_determinism,
    check_vector, parse_vector)

SERIES_LIMIT: Final = Fraction(5, 100)        # F2: a counter's series total may grow by at most +5.0 %
STAGE_LIMIT: Final = Fraction(10, 100)        # F3: a stage's value may grow by at most +10.0 % ...
STAGE_SHARE_LIMIT: Final = Fraction(1, 100)   # ... unless the increase is <= 1 % of the counter's base total
REDISTRIBUTION_LIMIT: Final = Fraction(5, 100)  # F4: growth above +5 % is listed for review
CPU_LIMIT: Final = 0.05                       # F5: CPU median growth above +5 % needs an account
CPU_ROUNDS: Final = 5                         # D147: alternating rounds per revision
FAILING_RULES: Final = (Rule.F1, Rule.F2, Rule.F3)


@dataclass(frozen=True)
class CompareOptions:
    cpu_ratio: float | None = None
    uncounted_sites: tuple[str, ...] = ()
    noop_expected: bool = False


def _exceeds(head: int, base: int, limit: Fraction) -> bool:
    """Whether ``head`` is more than ``limit`` above ``base``; growth from zero always exceeds."""
    return head - base > limit * base


def _growth_text(head: int, base: int) -> str:
    return f"{base} -> {head}" + (f" ({(head - base) / base:+.1%})" if base else "")


def _stage_events(name: str, base: WorkValue, head: WorkValue, stage: str) -> list[RuleEvent]:
    base_stage, head_stage = base.stages[stage], head.stages[stage]
    text = f"{name} in {stage}: {_growth_text(head_stage, base_stage)}"
    events: list[RuleEvent] = []
    if _exceeds(head_stage, base_stage, STAGE_LIMIT) and head_stage - base_stage > STAGE_SHARE_LIMIT * base.total:
        events.append(RuleEvent(Rule.F3, f"{text} exceeds +10% and 1% of the series total"))
    if _exceeds(head_stage, base_stage, REDISTRIBUTION_LIMIT):
        events.append(RuleEvent(Rule.F4, f"{text} grew more than 5%"))
    return events


def _counter_events(name: str, base: WorkValue, head: WorkValue, stages: Iterable[str]) -> list[RuleEvent]:
    events: list[RuleEvent] = []
    text = f"{name} total: {_growth_text(head.total, base.total)}"
    if _exceeds(head.total, base.total, SERIES_LIMIT):
        events.append(RuleEvent(Rule.F2, f"{text} exceeds +5%"))
    if _exceeds(head.total, base.total, REDISTRIBUTION_LIMIT):
        events.append(RuleEvent(Rule.F4, f"{text} grew more than 5%"))
    for stage in stages:
        events.extend(_stage_events(name, base, head, stage))
    return events


def _review_events(gate_events: Sequence[RuleEvent], opts: CompareOptions) -> list[RuleEvent]:
    events: list[RuleEvent] = []
    gate_passes = not any(e.rule in (Rule.F2, Rule.F3) for e in gate_events)
    if gate_passes and opts.cpu_ratio is not None and opts.cpu_ratio > CPU_LIMIT:
        events.append(RuleEvent(Rule.F5, f"CPU median {opts.cpu_ratio:+.1%} exceeds +5% while F2 and F3 pass: "
                                         "name the uncounted work or show a same-code control pair"))
    if opts.uncounted_sites:
        events.append(RuleEvent(Rule.F6, "uncounted work declared: " + ", ".join(opts.uncounted_sites)))
    return events


def compare(base: WorkVector, head: WorkVector, opts: CompareOptions | None = None) -> list[RuleEvent]:
    opts = opts or CompareOptions()
    events = [*check_vector(base, "base"), *check_vector(head, "head")]
    if (base.preset, base.series) != (head.preset, head.series):
        events.append(RuleEvent(Rule.F1, "base and head are different preset/series"))
    if events:
        return events
    stages = applicable_stages(base.series)
    for name in applicable_counters(base.series):
        events.extend(_counter_events(name, base.values[name], head.values[name], stages))
    events.extend(_review_events(events, opts))
    if opts.noop_expected and events:
        return [RuleEvent(Rule.F1, f"no-op expected, but got {events[0].rule.value}: {events[0].message}")]
    return events


def cpu_ratio_from_rounds(raw: object) -> float:
    """Median CPU growth from ``{"base": [...], "head": [...]}`` with exactly ``CPU_ROUNDS`` rounds each."""
    if not isinstance(raw, dict):
        raise ValueError("CPU evidence must be an object with 'base' and 'head' round lists")
    medians = []
    for side in ("base", "head"):
        rounds = raw.get(side)
        if (not isinstance(rounds, list) or len(rounds) != CPU_ROUNDS
                or not all(isinstance(r, (int, float)) and not isinstance(r, bool) and r > 0 for r in rounds)):
            raise ValueError(f"CPU evidence {side!r} must be {CPU_ROUNDS} positive CPU-second values")
        medians.append(statistics.median(rounds))
    return medians[1] / medians[0] - 1


def _load_vector(path: str, label: str) -> WorkVector:
    try:
        return parse_vector(json.loads(Path(path).read_text(encoding="utf-8")))
    except (OSError, ValueError) as exc:
        raise ValueError(f"{label} vector {path}: {exc}") from exc


def _run_git(cwd: Path, args: Iterable[str]) -> str:
    cp = subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True)
    return cp.stdout.strip()


def prepare_merge_base_worktree(repo: Path, *, head_ref: str, base_ref: str, counter_commit: str) -> dict[str, str]:
    """Create a detached worktree at the merge-base with the counter commit applied. It is never pushed."""
    merge_base = _run_git(repo, ["merge-base", head_ref, base_ref])
    root = Path(tempfile.mkdtemp(prefix="mb-perf-base-"))
    worktree = root / "worktree"
    try:
        _run_git(repo, ["worktree", "add", "--detach", str(worktree), merge_base])
        try:
            _run_git(worktree, ["cherry-pick", "--no-commit", counter_commit])
        except subprocess.CalledProcessError as exc:
            raise RuntimeError("F1: counter commit does not apply cleanly to the merge-base") from exc
        _run_git(worktree, ["reset"])
    except BaseException:
        subprocess.run(["git", "worktree", "remove", "--force", str(worktree)], cwd=str(repo), check=False)
        shutil.rmtree(root, ignore_errors=True)
        raise
    return {"merge_base": merge_base, "worktree_path": str(worktree), "counter_commit": counter_commit,
            "cleanup": f"git worktree remove --force {worktree}"}


def _emit(events: Sequence[RuleEvent]) -> int:
    print(json.dumps({"events": [{"rule": e.rule.value, "message": e.message} for e in events]},
                     indent=2, sort_keys=True))
    return 1 if any(e.rule in FAILING_RULES for e in events) else 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    cmp_ap = sub.add_parser("compare", help="compare base/head work vectors under F1..F6")
    cmp_ap.add_argument("--base", required=True, help="base vector json")
    cmp_ap.add_argument("--head", required=True, help="head vector json")
    cmp_ap.add_argument("--base-peer", help="second run of the base revision (F1 determinism)")
    cmp_ap.add_argument("--head-peer", help="second run of the head revision (F1 determinism)")
    cmp_ap.add_argument("--cpu-rounds", help=f"json {{'base': [..], 'head': [..]}}, {CPU_ROUNDS} CPU-second rounds each")
    cmp_ap.add_argument("--uncounted-site", action="append", default=[], help="declare an uncounted work site (F6)")
    cmp_ap.add_argument("--noop", action="store_true", help="assert that nothing at all is reported")
    prep_ap = sub.add_parser("prepare-base", help="create the merge-base + counter-commit worktree")
    prep_ap.add_argument("--repo", default=".", help="repository root")
    prep_ap.add_argument("--head-ref", default="HEAD")
    prep_ap.add_argument("--base-ref", default="origin/main")
    prep_ap.add_argument("--counter-commit", required=True, help="the isolated counter commit C")
    return parser


def _run_compare(args: argparse.Namespace) -> int:
    base, head = _load_vector(args.base, "base"), _load_vector(args.head, "head")
    events: list[RuleEvent] = []
    for label, vector, peer in (("base", base, args.base_peer), ("head", head, args.head_peer)):
        if peer:
            events.extend(check_determinism(vector, _load_vector(peer, f"{label} peer"), label))
    cpu_ratio = None
    if args.cpu_rounds:
        cpu_ratio = cpu_ratio_from_rounds(json.loads(Path(args.cpu_rounds).read_text(encoding="utf-8")))
    events.extend(compare(base, head, CompareOptions(cpu_ratio, tuple(args.uncounted_site), args.noop)))
    return _emit(events)


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.cmd == "prepare-base":
        print(json.dumps(prepare_merge_base_worktree(
            Path(args.repo).resolve(), head_ref=args.head_ref, base_ref=args.base_ref,
            counter_commit=args.counter_commit), indent=2, sort_keys=True))
        return 0
    try:
        return _run_compare(args)
    except (OSError, ValueError) as exc:
        return _emit([RuleEvent(Rule.F1, str(exc))])


if __name__ == "__main__":
    raise SystemExit(main())
