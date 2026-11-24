# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""Optional operation counters for deterministic perf gating (D153).

Counted sites guard every increment with ``if perf_counters.ENABLED:`` so a disabled registry costs one flag
check. Each count is charged to the innermost active ``stage``; counts outside every stage go to ``OTHER_STAGE``.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TypedDict

OTHER_STAGE = "other"
ENABLED: bool = os.environ.get("MAP_BUILDER_PERF_COUNTERS", "").strip().lower() in ("1", "true", "yes", "on")


class CounterSnapshot(TypedDict):
    total: int
    stages: dict[str, int]


_totals: dict[str, int] = {}
_by_stage: dict[str, dict[str, int]] = {}
_stage_stack: list[str] = []


def set_enabled(enabled: bool) -> None:
    global ENABLED
    ENABLED = enabled


def reset() -> None:
    _totals.clear()
    _by_stage.clear()
    _stage_stack.clear()


def current_stage() -> str:
    return _stage_stack[-1] if _stage_stack else OTHER_STAGE


@contextmanager
def stage(name: str) -> Iterator[None]:
    _stage_stack.append(name)
    try:
        yield
    finally:
        _stage_stack.pop()


def inc(name: str, amount: int = 1) -> None:
    _totals[name] = _totals.get(name, 0) + amount
    per_stage = _by_stage.setdefault(name, {})
    owner = current_stage()
    per_stage[owner] = per_stage.get(owner, 0) + amount


def inc_keyed(name: str, key: str, amount: int = 1) -> None:
    inc(f"{name}[{key}]", amount)


def snapshot() -> dict[str, CounterSnapshot]:
    return {name: {"total": total, "stages": dict(_by_stage[name])} for name, total in _totals.items()}
