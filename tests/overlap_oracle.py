# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""Test-only baseline oracle: ``triangle_touches`` as it was before the indexed masks (S5-PERF-WATER), a plain
scan of every path edge. It shares no code with ``PathMask``, so an indexing regression cannot hide in both."""

from __future__ import annotations

from collections.abc import Sequence

from map_builder.core.osm import point_in_ring
from map_builder.core.overlap import Pt, _edge_in_box, _edges, _in_box, _padded_box, _segment_distance


def brute_force_touches(tri: Sequence[Pt], path: Sequence[Pt], margin: float, closed: bool) -> bool:
    box = _padded_box(tri, margin)
    if any(point_in_ring(x, y, tri) for x, y in path if _in_box(x, y, box)):
        return True
    if closed and any(point_in_ring(x, y, path) for x, y in tri):
        return True
    return any(_segment_distance(a, b, c, d) <= margin
               for a, b in _edges(path, closed) if _edge_in_box(a, b, box) for c, d in _edges(tri, True))
