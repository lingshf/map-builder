# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf

from __future__ import annotations

import dataclasses
import unittest

from map_builder.core import perf_counters
from tools.perf.stages import StageCallProfiler
from tools.perf.work_count import CompareOptions, compare, cpu_ratio_from_rounds
from tools.perf.work_vector import (
    OTHER_STAGE,
    Rule,
    VectorFormatError,
    WorkValue,
    WorkVector,
    applicable_counters,
    applicable_stages,
    check_determinism,
    check_vector,
    parse_vector,
)

BASE_TOTAL = 1000
STAGE = "build_terrain"


def make_vector(series: str = "cli_generate", total: int = BASE_TOTAL, **overrides: object) -> WorkVector:
    """A complete vector: every applicable counter has ``total`` charged to ``other``, zero elsewhere."""
    stages = {name: 0 for name in applicable_stages(series)}
    stages[OTHER_STAGE] = total
    values = {name: WorkValue(total, dict(stages)) for name in applicable_counters(series)}
    return dataclasses.replace(WorkVector("munich", series, values, package_valid=True, run_error=None), **overrides)


def with_counter(vector: WorkVector, name: str, total: int, stage_counts: dict[str, int]) -> WorkVector:
    stages = {**vector.values[name].stages, **stage_counts}
    return dataclasses.replace(vector, values={**vector.values, name: WorkValue(total, stages)})


def grown(counter: str, growth: int, stage: str = STAGE) -> WorkVector:
    """The base vector with ``growth`` extra units of ``counter`` charged to ``stage``."""
    base = make_vector()
    stages = base.values[counter].stages
    return with_counter(base, counter, BASE_TOTAL + growth, {stage: stages[stage] + growth})


def rules(events: list) -> set[Rule]:
    return {event.rule for event in events}


class NestedAttributionTest(unittest.TestCase):
    def tearDown(self) -> None:
        perf_counters.set_enabled(False)

    def test_counters_charge_the_innermost_stage_and_the_rest_to_other(self) -> None:
        perf_counters.set_enabled(True)
        perf_counters.reset()
        perf_counters.inc("clip_steps")
        with perf_counters.stage("outer"):
            perf_counters.inc("clip_steps", 2)
            with perf_counters.stage("inner"):
                perf_counters.inc("clip_steps", 4)
            perf_counters.inc("clip_steps", 8)
        entry = perf_counters.snapshot()["clip_steps"]
        self.assertEqual(entry["total"], 15)
        self.assertEqual(entry["stages"], {OTHER_STAGE: 1, "outer": 10, "inner": 4})

    def test_primitive_calls_are_charged_to_the_innermost_stage(self) -> None:
        def leaf() -> None:
            pass

        def callers(count: int) -> None:
            for _ in range(count):
                leaf()

        profiler = StageCallProfiler()
        profiler.start()
        with profiler.stage("outer"):
            callers(3)
            with profiler.stage("inner"):
                callers(100)
        calls = profiler.primitive_calls()
        profiler.stop()
        self.assertGreaterEqual(calls["inner"], 100)
        self.assertLess(calls["outer"], 100)
        self.assertGreaterEqual(calls["outer"], 3)
        self.assertIn(OTHER_STAGE, calls)


class ParseVectorTest(unittest.TestCase):
    def document(self) -> dict:
        return {"preset": "munich", "series": "cli_generate", "package_valid": True, "run_error": None,
                "values": {"clip_steps": {"total": 3, "stages": {"other": 3}}}}

    def test_a_well_formed_document_parses(self) -> None:
        vector = parse_vector(self.document())
        self.assertEqual(vector.values["clip_steps"], WorkValue(3, {"other": 3}))

    def test_malformed_documents_are_rejected_without_coercion(self) -> None:
        def broken(edit) -> dict:
            doc = self.document()
            edit(doc)
            return doc

        cases = {
            "float count": broken(lambda d: d["values"]["clip_steps"].update(total=3.0)),
            "bool count": broken(lambda d: d["values"]["clip_steps"].update(total=True)),
            "negative stage": broken(lambda d: d["values"]["clip_steps"]["stages"].update(other=-1)),
            "string count": broken(lambda d: d["values"]["clip_steps"].update(total="3")),
            "missing package_valid": broken(lambda d: d.pop("package_valid")),
            "non-bool package_valid": broken(lambda d: d.update(package_valid=1)),
            "missing run_error": broken(lambda d: d.pop("run_error")),
            "missing stages": broken(lambda d: d["values"]["clip_steps"].pop("stages")),
            "not an object": [],
        }
        for name, document in cases.items():
            with self.subTest(name), self.assertRaises(VectorFormatError):
                parse_vector(document)


class CheckVectorTest(unittest.TestCase):
    def test_a_complete_vector_has_no_events(self) -> None:
        for series in ("cli_generate", "blender_generate", "blender_generate_export"):
            with self.subTest(series):
                self.assertEqual(check_vector(make_vector(series), "v"), [])

    def test_missing_counter_stage_or_bad_sum_is_f1(self) -> None:
        vector = make_vector()
        no_counter = dataclasses.replace(
            vector, values={k: v for k, v in vector.values.items() if k != "clip_steps"})
        no_stage = with_counter(vector, "clip_steps", BASE_TOTAL, {})
        del no_stage.values["clip_steps"].stages[STAGE]
        bad_sum = with_counter(vector, "clip_steps", BASE_TOTAL + 1, {})
        for name, broken in {"counter": no_counter, "stage": no_stage, "sum": bad_sum}.items():
            with self.subTest(name):
                self.assertEqual(rules(check_vector(broken, "v")), {Rule.F1})

    def test_run_errors_and_invalid_packages_are_f1(self) -> None:
        self.assertEqual(rules(check_vector(make_vector(run_error="boom"), "v")), {Rule.F1})
        self.assertEqual(rules(check_vector(make_vector(package_valid=False), "v")), {Rule.F1})

    def test_only_inapplicable_counters_and_stages_may_be_absent(self) -> None:
        self.assertNotIn("bpy_mesh_vertices", applicable_counters("cli_generate"))
        self.assertNotIn("package_write", applicable_stages("blender_generate"))
        self.assertIn("bpy_mesh_vertices", applicable_counters("blender_generate"))
        extra = with_counter(make_vector(), "clip_steps", BASE_TOTAL, {})
        extra.values["bpy_mesh_vertices"] = extra.values["clip_steps"]
        self.assertEqual(rules(check_vector(extra, "v")), {Rule.F1})


class DeterminismTest(unittest.TestCase):
    def test_identical_runs_pass(self) -> None:
        self.assertEqual(check_determinism(make_vector(), make_vector(), "base"), [])

    def test_a_differing_counter_is_f1(self) -> None:
        events = check_determinism(make_vector(), grown("clip_steps", 1), "base")
        self.assertEqual(rules(events), {Rule.F1})

    def test_the_peer_is_validated_too(self) -> None:
        events = check_determinism(make_vector(), make_vector(package_valid=False), "head")
        self.assertTrue(any("run 2" in event.message for event in events))


class CompareTest(unittest.TestCase):
    def test_identical_vectors_report_nothing(self) -> None:
        self.assertEqual(compare(make_vector(), make_vector(), CompareOptions(noop_expected=True)), [])

    def test_series_growth_over_five_percent_is_f2_and_still_disclosed_as_f4(self) -> None:
        events = compare(make_vector(), grown("clip_steps", 60, stage=OTHER_STAGE))
        self.assertIn(Rule.F2, rules(events))
        self.assertIn(Rule.F4, rules(events))

    def test_five_percent_growth_is_not_f2(self) -> None:
        self.assertNotIn(Rule.F2, rules(compare(make_vector(), grown("clip_steps", 50, stage=OTHER_STAGE))))

    def test_stage_growth_is_f3_only_above_ten_percent_and_one_percent_of_the_total(self) -> None:
        base = with_counter(make_vector(), "clip_steps", BASE_TOTAL, {STAGE: 100, OTHER_STAGE: BASE_TOTAL - 100})
        for growth, expect_f3 in ((20, True), (11, True), (10, False)):
            head = with_counter(base, "clip_steps", BASE_TOTAL + growth,
                                {STAGE: 100 + growth})
            with self.subTest(growth):
                self.assertEqual(Rule.F3 in rules(compare(base, head)), expect_f3)

    def test_growth_from_zero_is_judged_against_the_share_of_the_total(self) -> None:
        self.assertIn(Rule.F3, rules(compare(make_vector(), grown("clip_steps", 11))))
        self.assertNotIn(Rule.F3, rules(compare(make_vector(), grown("clip_steps", 10))))

    def test_cpu_growth_is_f5_only_when_f2_and_f3_pass(self) -> None:
        options = CompareOptions(cpu_ratio=0.2)
        self.assertEqual(rules(compare(make_vector(), make_vector(), options)), {Rule.F5})
        failing = compare(make_vector(), grown("clip_steps", 100), options)
        self.assertNotIn(Rule.F5, rules(failing))

    def test_cpu_growth_within_five_percent_is_silent(self) -> None:
        self.assertEqual(compare(make_vector(), make_vector(), CompareOptions(cpu_ratio=0.05)), [])

    def test_declared_uncounted_sites_are_f6(self) -> None:
        events = compare(make_vector(), make_vector(), CompareOptions(uncounted_sites=("generate.py:inline loop",)))
        self.assertEqual(rules(events), {Rule.F6})

    def test_noop_turns_any_event_into_f1(self) -> None:
        events = compare(make_vector(), grown("clip_steps", 1), CompareOptions(noop_expected=True))
        self.assertEqual(rules(events), {Rule.F1})

    def test_an_invalid_side_is_f1_and_nothing_else(self) -> None:
        events = compare(make_vector(), make_vector(package_valid=False))
        self.assertEqual(rules(events), {Rule.F1})

    def test_different_series_cannot_be_compared(self) -> None:
        events = compare(make_vector("cli_generate"), make_vector("blender_generate"))
        self.assertEqual(rules(events), {Rule.F1})


class CpuRoundsTest(unittest.TestCase):
    def test_median_ratio_of_five_rounds(self) -> None:
        evidence = {"base": [1.0, 1.0, 1.0, 9.0, 9.0], "head": [1.1, 1.1, 1.1, 1.1, 20.0]}
        self.assertAlmostEqual(cpu_ratio_from_rounds(evidence), 0.1)

    def test_wrong_round_count_or_bad_values_are_rejected(self) -> None:
        good = [1.0] * 5
        bad_inputs = [{"base": good[:4], "head": good}, {"base": good, "head": good + [1.0]},
                      {"base": good, "head": [1.0, 1.0, 1.0, 1.0, 0.0]}, {"base": good, "head": [True] * 5},
                      {"base": good}, []]
        for evidence in bad_inputs:
            with self.subTest(evidence), self.assertRaises(ValueError):
                cpu_ratio_from_rounds(evidence)


if __name__ == "__main__":
    unittest.main()
