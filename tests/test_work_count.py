# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf

from __future__ import annotations

import unittest

from tools.perf.work_count import (
    COUNTERS,
    STAGES,
    CompareOptions,
    Rule,
    WorkValue,
    WorkVector,
    _f1_determinism,
    compare,
)


def _mk_vector(total: int = 100, *, preset: str = "munich", series: str = "cli_generate") -> WorkVector:
    values: dict[str, WorkValue] = {}
    for c in COUNTERS:
        if c == "bpy_mesh_vertices" and series == "cli_generate":
            continue
        stages = {s: 0 for s in STAGES}
        stages["other"] = total
        values[c] = WorkValue(total=total, stages=stages)
    return WorkVector(preset=preset, series=series, values=values)


class WorkCountRuleTests(unittest.TestCase):
    def test_noop_passes(self) -> None:
        base = _mk_vector()
        head = _mk_vector()
        events = compare(base, head, CompareOptions(noop_expected=True))
        self.assertEqual([], events)

    def test_f2_deflate_total_fail(self) -> None:
        base = _mk_vector()
        head = _mk_vector()
        head.values["deflate_in_bytes"] = WorkValue(total=106, stages={"other": 106})
        events = compare(base, head, CompareOptions())
        self.assertTrue(any(e.rule == Rule.F2 for e in events), events)

    def test_f2_deflate_retry_path_fail(self) -> None:
        base = _mk_vector()
        head = _mk_vector()
        base.values["deflate_in_bytes"] = WorkValue(
            total=1_000, stages={"package_write": 900, "validate_package": 100}
        )
        head.values["deflate_in_bytes"] = WorkValue(
            total=2_000, stages={"package_write": 1_800, "validate_package": 200}
        )
        events = compare(base, head, CompareOptions())
        self.assertTrue(any(e.rule == Rule.F2 for e in events), events)

    def test_f3_build_terrain_grid_cells_fail(self) -> None:
        base = _mk_vector(total=20_000)
        head = _mk_vector(total=20_000)
        base.values["grid_cells"] = WorkValue(
            total=10_000, stages={"build_terrain": 1_000, "other": 9_000}
        )
        head.values["grid_cells"] = WorkValue(
            total=11_000, stages={"build_terrain": 2_000, "other": 9_000}
        )
        events = compare(base, head, CompareOptions())
        self.assertTrue(any(e.rule == Rule.F3 for e in events), events)

    def test_f3_small_stage_fail(self) -> None:
        base = _mk_vector()
        head = _mk_vector()
        base.values["overlap_edge_tests"] = WorkValue(
            total=10_000, stages={"_water_stage": 100, "other": 9_900}
        )
        head.values["overlap_edge_tests"] = WorkValue(
            total=10_050, stages={"_water_stage": 220, "other": 9_830}
        )
        events = compare(base, head, CompareOptions())
        self.assertTrue(any(e.rule == Rule.F3 for e in events), events)

    def test_uncounted_case_triggers_f5_and_f6(self) -> None:
        base = _mk_vector()
        head = _mk_vector()
        events = compare(
            base,
            head,
            CompareOptions(cpu_ratio=0.09, uncounted_sites=("build_terrain inline loop",)),
        )
        self.assertFalse(any(e.rule in (Rule.F1, Rule.F2, Rule.F3, Rule.F4) for e in events), events)
        self.assertTrue(any(e.rule == Rule.F5 for e in events), events)
        self.assertTrue(any(e.rule == Rule.F6 for e in events), events)

    def test_missing_required_counter_fails_f1(self) -> None:
        base = _mk_vector()
        head = _mk_vector()
        del head.values["grid_cells"]
        events = compare(base, head, CompareOptions())
        self.assertTrue(any(e.rule == Rule.F1 for e in events), events)

    def test_determinism_f1_mismatch(self) -> None:
        r1 = _mk_vector()
        r2 = _mk_vector()
        r2.values["clip_steps"] = WorkValue(total=101, stages={"other": 101})
        events = _f1_determinism(r1, r2)
        self.assertTrue(any(e.rule == Rule.F1 for e in events), events)


if __name__ == "__main__":
    unittest.main()
