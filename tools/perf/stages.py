# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""Stage attribution for the work vector (D153).

Wraps the pinned stage functions of a product tree so that, while one runs, its operation counters
(``perf_counters.stage``) and its Python primitive calls (a ``cProfile`` profile per stage) are charged to the
innermost active stage only. Work outside every stage is charged to ``other``.
"""

from __future__ import annotations

import cProfile
import functools
import importlib
import sys
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from typing import Any, NamedTuple

from tools.perf.work_vector import OTHER_STAGE


class StageTarget(NamedTuple):
    stage: str
    module: str
    function: str


CORE_TARGETS: tuple[StageTarget, ...] = (
    StageTarget("acquire", "map_builder.core.pipeline", "acquire"),
    StageTarget("build_plan", "map_builder.core.generate", "build_plan"),
    StageTarget("_water_stage", "map_builder.core.generate", "_water_stage"),
    StageTarget("shore_ramps", "map_builder.core.shore", "shore_ramps"),
    StageTarget("build_terrain", "map_builder.core.generate", "build_terrain"),
    StageTarget("buildings_roofs", "map_builder.core.generate", "build_building"),
    StageTarget("roads", "map_builder.core.generate", "build_road"),
    StageTarget("bridges", "map_builder.core.bridges", "build"),
    StageTarget("tunnels", "map_builder.core.tunnels", "build"),
    StageTarget("package_write", "map_builder.core.package", "write_package"),
    StageTarget("validate_package", "map_builder.core.package", "validate_package"),
)
BLENDER_TARGETS: tuple[StageTarget, ...] = (
    StageTarget("build_scene", "map_builder.blender.scene_build", "build_scene"),
)


class StageCallProfiler:
    """Counts primitive calls per stage: only the innermost active stage's profile is ever enabled."""

    def __init__(self) -> None:
        self._profiles: dict[str, cProfile.Profile] = {}
        self._stack: list[str] = []

    def _profile(self, stage: str) -> cProfile.Profile:
        return self._profiles.setdefault(stage, cProfile.Profile())

    def start(self) -> None:
        self._stack.append(OTHER_STAGE)
        self._profile(OTHER_STAGE).enable()

    def stop(self) -> None:
        self._profile(self._stack.pop()).disable()

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        self._profile(self._stack[-1]).disable()
        self._stack.append(name)
        self._profile(name).enable()
        try:
            yield
        finally:
            self._profile(self._stack.pop()).disable()
            self._profile(self._stack[-1]).enable()

    def primitive_calls(self) -> dict[str, int]:
        """Primitive calls per stage so far; the running stage's profile is paused while it is read."""
        running = self._profile(self._stack[-1])
        running.disable()
        counts = {name: _primitive_call_count(profile) for name, profile in self._profiles.items()}
        running.enable()
        return counts


def _primitive_call_count(profile: cProfile.Profile) -> int:
    return sum(entry.callcount - entry.reccallcount for entry in profile.getstats())


def _wrap(function: Callable[..., Any], stage: str, enter_stage: Callable[[str], Any]) -> Callable[..., Any]:
    @functools.wraps(function)
    def staged(*args: Any, **kwargs: Any) -> Any:
        with enter_stage(stage):
            return function(*args, **kwargs)
    return staged


def _rebind_everywhere(original: Callable[..., Any], replacement: Callable[..., Any]) -> None:
    """Replace every ``map_builder`` module attribute bound to ``original`` (``from x import f`` copies)."""
    for name, module in list(sys.modules.items()):
        if not name.startswith("map_builder") or module is None:
            continue
        for attribute, value in list(vars(module).items()):
            if value is original:
                setattr(module, attribute, replacement)


@contextmanager
def instrumented(targets: Sequence[StageTarget], profiler: StageCallProfiler,
                 counter_stage: Callable[[str], Any]) -> Iterator[None]:
    """Instrument ``targets`` for the duration of the block, then restore the original functions."""
    @contextmanager
    def enter_stage(name: str) -> Iterator[None]:
        with counter_stage(name), profiler.stage(name):
            yield

    patched: list[tuple[Callable[..., Any], Callable[..., Any]]] = []
    try:
        for target in targets:
            original = getattr(importlib.import_module(target.module), target.function)
            replacement = _wrap(original, target.stage, enter_stage)
            _rebind_everywhere(original, replacement)
            patched.append((original, replacement))
        yield
    finally:
        for original, replacement in reversed(patched):
            _rebind_everywhere(replacement, original)
