# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""S5-F3 evidence (session files): rebuild a preset offline and record every shore strip the ramp builder left out,
with the reason (footprint, line mask, or wet overlap). Product code is only wrapped in-process, never edited.

  py -3.12 blocked_strips.py --root <tree> --cache <dir> --preset bellevue-factoria --out <pkg> --json <out.json>
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_factoria  # noqa: E402


def _mask_reasons(masks: Any, tri: list[tuple[float, float]]) -> list[dict[str, Any]]:
    """Every footprint and line of ``masks`` the plan triangle meets, as ``hit_triangle`` decides it."""
    from map_builder.core.overlap import triangle_touches
    xs, ys = [v[0] for v in tri], [v[1] for v in tri]
    box = (min(xs), min(ys), max(xs), max(ys))
    out = []
    for i in sorted(masks.foot_idx.in_box(box)):
        if triangle_touches(tri, masks.footprints[i].outer, 0.0, closed=True):
            out.append({"mask": "footprint", "index": i, "ring_head": [list(p) for p in masks.footprints[i].outer[:3]]})
    for i in sorted(masks.line_idx.in_box(box)):
        polyline, half_width = masks.lines[i]
        if triangle_touches(tri, polyline, half_width, closed=False):
            out.append({"mask": "line", "index": i, "half_width_m": round(half_width, 3),
                        "polyline": [[round(p[0], 2), round(p[1], 2)] for p in polyline]})
    return out


def install_recorder(records: list[dict[str, Any]]) -> None:
    from map_builder.core import shore
    original = shore._place_strip

    def recording_place_strip(out: Any, a: Any, b: Any, blocked_by: Any, wet_by: Any) -> None:
        before = out.blocked_m
        original(out, a, b, blocked_by, wet_by)
        if out.blocked_m == before:
            return
        cascade = a.cascade and b.cascade and a.receiver is not None and a.receiver == b.receiver
        receiver = a.receiver if cascade else None
        reasons = []
        for t in shore._ramp_tris(a, b):
            plan = [(v[0], v[1]) for v in t]
            if blocked_by(plan):
                reasons.extend(_mask_reasons(blocked_by.__self__, plan))
            if wet_by(plan, receiver, a.source_piece):
                reasons.append({"mask": "wet"})
        records.append({"a": [round(a.top[0], 3), round(a.top[1], 3), round(a.top[2], 3)],
                        "b": [round(b.top[0], 3), round(b.top[1], 3), round(b.top[2], 3)],
                        "cascade": bool(cascade), "reasons": _dedupe(reasons)})

    shore._place_strip = recording_place_strip


def _dedupe(reasons: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen, out = set(), []
    for r in reasons:
        key = json.dumps(r, sort_keys=True)
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--cache", type=Path, required=True)
    ap.add_argument("--preset", default="bellevue-factoria")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--json", type=Path, required=True)
    a = ap.parse_args(argv)
    sys.path.insert(0, str(a.root))
    records: list[dict[str, Any]] = []
    install_recorder(records)
    build_factoria.deny_network()
    with tempfile.TemporaryDirectory(prefix="mb-s5f3-") as scratch:
        cache_dir = str(build_factoria.fresh_cache_copy(a.cache, a.preset, Path(scratch)))
        ok = build_factoria.build_cli(a.preset, cache_dir, a.out)
    a.json.write_text(json.dumps(records, indent=1), encoding="utf-8")
    print(f"valid {ok}; {len(records)} blocked strips -> {a.json}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
