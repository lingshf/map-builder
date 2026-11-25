# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""The work vector of S5-PERF-GATE (D153): schema, strict parsing and F1 completeness checks."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Final

TRI_CLASSES: Final[tuple[str, ...]] = (
    "terrain", "building", "road", "vegetation", "water", "prop", "bridge", "tunnel", "structure",
)
PACKAGE_MEMBERS: Final[tuple[str, ...]] = (
    "manifest.json", "visual/map.glb", "collision/map.mbcol", "collision/terrain.mbhf", "report.json",
    "NOTICES.txt",
)
PRIMITIVE_CALLS: Final = "primitive_calls"

COUNTERS: Final[tuple[str, ...]] = (
    *(f"tri_emitted[{name}]" for name in TRI_CLASSES),
    "ring_edge_tests",
    "clip_steps",
    "overlap_pairs",
    "overlap_edge_tests",
    "candidate_pairs",
    "grid_cells",
    "deflate_in_bytes",
    *(f"bytes_written[{member}]" for member in PACKAGE_MEMBERS),
    "validator_pairs",
    "bpy_mesh_vertices",
    PRIMITIVE_CALLS,
)

OTHER_STAGE: Final = "other"
STAGES: Final[tuple[str, ...]] = (
    "acquire", "build_plan", "_water_stage", "shore_ramps", "build_terrain", "buildings_roofs", "roads",
    "bridges", "tunnels", "build_scene", "package_write", "validate_package", OTHER_STAGE,
)

SERIES: Final[tuple[str, ...]] = ("cli_generate", "blender_generate", "blender_generate_export")
GATING_PRESETS: Final[tuple[str, ...]] = ("munich", "pittsburgh")

_PACKAGE_COUNTERS: Final[frozenset[str]] = frozenset(
    {"deflate_in_bytes", "validator_pairs", *(f"bytes_written[{member}]" for member in PACKAGE_MEMBERS)})

# Structurally inapplicable counters and stages per series: the only ones that may be absent.
NOT_APPLICABLE_COUNTERS: Final[dict[str, frozenset[str]]] = {
    "cli_generate": frozenset({"bpy_mesh_vertices"}),
    "blender_generate": _PACKAGE_COUNTERS,
    "blender_generate_export": frozenset(),
}
NOT_APPLICABLE_STAGES: Final[dict[str, frozenset[str]]] = {
    "cli_generate": frozenset({"build_scene"}),
    "blender_generate": frozenset({"package_write", "validate_package"}),
    "blender_generate_export": frozenset(),
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
    package_valid: bool
    run_error: str | None


class VectorFormatError(ValueError):
    """The vector document is not shaped like a work vector."""


def applicable_counters(series: str) -> tuple[str, ...]:
    return tuple(name for name in COUNTERS if name not in NOT_APPLICABLE_COUNTERS[series])


def applicable_stages(series: str) -> tuple[str, ...]:
    return tuple(stage for stage in STAGES if stage not in NOT_APPLICABLE_STAGES[series])


def _mapping(raw: object, where: str) -> Mapping[str, object]:
    if not isinstance(raw, dict):
        raise VectorFormatError(f"{where} must be an object")
    return raw


def _field(doc: Mapping[str, object], key: str, where: str) -> object:
    if key not in doc:
        raise VectorFormatError(f"{where} is missing {key!r}")
    return doc[key]


def _text(raw: object, where: str) -> str:
    if not isinstance(raw, str):
        raise VectorFormatError(f"{where} must be a string")
    return raw


def _flag(raw: object, where: str) -> bool:
    if not isinstance(raw, bool):
        raise VectorFormatError(f"{where} must be a boolean")
    return raw


def _count(raw: object, where: str) -> int:
    if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
        raise VectorFormatError(f"{where} must be a non-negative integer, got {raw!r}")
    return raw


def _parse_value(raw: object, name: str) -> WorkValue:
    doc = _mapping(raw, f"counter {name!r}")
    stages = _mapping(_field(doc, "stages", f"counter {name!r}"), f"counter {name!r} stages")
    return WorkValue(
        total=_count(_field(doc, "total", f"counter {name!r}"), f"counter {name!r} total"),
        stages={stage: _count(n, f"counter {name!r} stage {stage!r}") for stage, n in stages.items()})


def parse_vector(raw: object) -> WorkVector:
    """Parse a vector document; raises ``VectorFormatError`` rather than coercing or defaulting any field."""
    doc = _mapping(raw, "vector")
    run_error = _field(doc, "run_error", "vector")
    values = _mapping(_field(doc, "values", "vector"), "vector values")
    return WorkVector(
        preset=_text(_field(doc, "preset", "vector"), "preset"),
        series=_text(_field(doc, "series", "vector"), "series"),
        values={name: _parse_value(item, name) for name, item in values.items()},
        package_valid=_flag(_field(doc, "package_valid", "vector"), "package_valid"),
        run_error=None if run_error is None else _text(run_error, "run_error"))


def check_vector(vector: WorkVector, label: str) -> list[RuleEvent]:
    """F1 completeness: the run succeeded, the package is VALID, and every applicable counter and stage is
    present exactly once with stage sums equal to the total."""
    events: list[RuleEvent] = []
    if vector.run_error is not None:
        events.append(RuleEvent(Rule.F1, f"{label}: run error: {vector.run_error}"))
    if not vector.package_valid:
        events.append(RuleEvent(Rule.F1, f"{label}: package is not VALID"))
    if vector.series not in SERIES:
        return [*events, RuleEvent(Rule.F1, f"{label}: unknown series {vector.series!r}")]
    expected = applicable_counters(vector.series)
    for name in expected:
        if name not in vector.values:
            events.append(RuleEvent(Rule.F1, f"{label}: missing counter {name}"))
    for name, value in vector.values.items():
        if name not in expected:
            events.append(RuleEvent(Rule.F1, f"{label}: counter {name} is not applicable to {vector.series}"))
        else:
            events.extend(_check_stages(vector.series, name, value, label))
    return events


def _check_stages(series: str, name: str, value: WorkValue, label: str) -> list[RuleEvent]:
    expected = set(applicable_stages(series))
    events = [RuleEvent(Rule.F1, f"{label}: {name} is missing stage {stage}")
              for stage in sorted(expected - set(value.stages))]
    events.extend(RuleEvent(Rule.F1, f"{label}: {name} has unexpected stage {stage!r}")
                  for stage in sorted(set(value.stages) - expected))
    stage_sum = sum(value.stages.values())
    if stage_sum != value.total:
        events.append(RuleEvent(Rule.F1, f"{label}: {name} stage sum {stage_sum} != total {value.total}"))
    return events


def check_determinism(first: WorkVector, second: WorkVector, label: str) -> list[RuleEvent]:
    """F1: two runs of one revision are each complete and identical in every counter and stage."""
    events = [*check_vector(first, f"{label} run 1"), *check_vector(second, f"{label} run 2")]
    if (first.preset, first.series) != (second.preset, second.series):
        return [*events, RuleEvent(Rule.F1, f"{label}: runs differ in preset or series")]
    for name in sorted(set(first.values) | set(second.values)):
        if first.values.get(name) != second.values.get(name):
            events.append(RuleEvent(Rule.F1, f"{label}: {name} differs between runs"))
    return events
