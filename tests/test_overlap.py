# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""The indexed masks answer exactly as the unindexed reference tests, over a seeded synthetic corpus."""

import json
import random
import unittest
from pathlib import Path
from typing import Any

from map_builder.core.osm import point_in_ring
from map_builder.core.overlap import (
    EdgeIndex, PathMask, RegionMask, RingIndex, triangle_overlaps_region)
from tests.overlap_oracle import brute_force_touches

PAIRS_PER_KIND = 2500
SEED = 20261127
ARENA_M = 120.0
SPECIAL_MARGIN_M = 0.5

BIG_RING = [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)]
HOLE = [(40.0, 40.0), (40.0, 60.0), (60.0, 60.0), (60.0, 40.0)]
# a concave ring, so crossing parity and clipping both see re-entrant edges
CONCAVE = [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (60.0, 100.0), (60.0, 30.0), (40.0, 30.0), (40.0, 100.0),
           (0.0, 100.0)]


def _point(rng: random.Random, lo: float = -10.0, hi: float = ARENA_M) -> tuple[float, float]:
    return rng.uniform(lo, hi), rng.uniform(lo, hi)


def _random_triangle(rng: random.Random, size: float) -> list[tuple[float, float]]:
    cx, cy = _point(rng)
    return [(cx + rng.uniform(-size, size), cy + rng.uniform(-size, size)) for _ in range(3)]


def _random_ring(rng: random.Random) -> list[tuple[float, float]]:
    cx, cy = _point(rng, 10.0, 100.0)
    count = rng.randint(3, 12)
    return [(cx + rng.uniform(-25, 25), cy + rng.uniform(-25, 25)) for _ in range(count)]


def _triangles(rng: random.Random, ring: list[tuple[float, float]]) -> list[list[tuple[float, float]]]:
    """Triangles of every contact kind the masks have to get right."""
    out = [_random_triangle(rng, rng.choice((0.5, 3.0, 15.0, 80.0))) for _ in range(PAIRS_PER_KIND)]
    out += [[ring[0], ring[1], (ring[0][0] + 1e-7, ring[0][1] + 1e-7)] for _ in range(10)]          # sliver
    out += [[(-1000.0, -1000.0), (1000.0, -1000.0), (0.0, 1000.0)]]                                   # contains the mask
    out += [[(10.0, 10.0), (20.0, 10.0), (10.0, 20.0)], [(2.0, 0.0), (20.0, 0.0), (10.0, -9.0)]]      # inside; edge contact only
    return out


REAL_CASES = Path(__file__).parent / "fixtures" / "water_mask_cases.json"


def _as_points(points: list[list[float]]) -> list[tuple[float, float]]:
    return [(x, y) for x, y in points]


class SyntheticCorpusTest(unittest.TestCase):
    def test_path_mask_matches_brute_force(self) -> None:
        for ring in (BIG_RING, CONCAVE):
            for closed in (True, False):
                with self.subTest(concave=ring is CONCAVE, closed=closed):
                    mask = PathMask(ring, SPECIAL_MARGIN_M, closed)
                    for tri in _triangles(random.Random(SEED), ring):
                        expected = brute_force_touches(tri, ring, SPECIAL_MARGIN_M, closed)
                        self.assertEqual(mask.touches(tri), expected)
                        if not mask.may_touch(tri):
                            self.assertFalse(expected)

    def test_path_mask_matches_brute_force_on_random_rings(self) -> None:
        rng = random.Random(SEED + 1)
        for _ in range(100):
            ring = _random_ring(rng)
            mask = PathMask(ring, SPECIAL_MARGIN_M, True)
            for tri in [_random_triangle(rng, rng.choice((1.0, 10.0, 60.0))) for _ in range(20)]:
                self.assertEqual(mask.touches(tri), brute_force_touches(tri, ring, SPECIAL_MARGIN_M, True))

    def test_region_mask_matches_reference(self) -> None:
        for outer, holes in ((BIG_RING, [HOLE]), (BIG_RING, []), (CONCAVE, [])):
            mask = RegionMask(outer, holes)
            extra = [list(HOLE[:3]), [(45.0, 45.0), (55.0, 45.0), (50.0, 55.0)]]
            for tri in _triangles(random.Random(SEED + 2), outer) + extra:
                self.assertEqual(mask.overlaps(tri), triangle_overlaps_region(tri, outer, holes))

    def test_ring_index_contains_matches_point_in_ring(self) -> None:
        rng = random.Random(SEED + 3)
        for ring in (BIG_RING, CONCAVE, *(_random_ring(rng) for _ in range(50))):
            index = RingIndex(ring)
            for x, y in [_point(rng) for _ in range(100)] + list(ring):
                self.assertEqual(index.contains(x, y), point_in_ring(x, y, ring))

    def test_repeated_and_zero_length_edges_match_brute_force(self) -> None:
        ring = BIG_RING + BIG_RING[:2] + [BIG_RING[1]]
        mask = PathMask(ring, SPECIAL_MARGIN_M, True)
        for tri in _triangles(random.Random(SEED + 4), ring):
            self.assertEqual(mask.touches(tri), brute_force_touches(tri, ring, SPECIAL_MARGIN_M, True))
            self.assertEqual(RingIndex(ring).contains(*tri[0]), point_in_ring(*tri[0], ring))


class EdgeIndexTest(unittest.TestCase):
    def test_an_edge_spanning_many_strips_is_yielded_once(self) -> None:
        tall = ((0.0, 0.0), (1.0, 100.0))
        short = ((5.0, 10.0), (6.0, 11.0))
        index = EdgeIndex([tall, short])
        found = list(index.edges_in_box((-1.0, -50.0, 10.0, 150.0)))
        self.assertEqual(sorted(found), sorted([tall, short]))
        self.assertEqual(list(index.edges_in_box((-1.0, 40.0, 10.0, 60.0))), [tall])


class RealWaterCasesTest(unittest.TestCase):
    """Masks and triangles recorded from the Pittsburgh and Bellevue-Factoria water stage."""

    cases: list[dict[str, Any]]

    @classmethod
    def setUpClass(cls) -> None:
        cls.cases = json.loads(REAL_CASES.read_text())["cases"]

    def test_the_fixture_covers_every_mask_kind(self) -> None:
        self.assertEqual({c["kind"] for c in self.cases}, {"region", "closed", "open"})
        self.assertEqual({c["preset"] for c in self.cases}, {"pittsburgh", "bellevue-factoria"})

    def test_masks_match_the_unindexed_answers(self) -> None:
        for case in self.cases:
            tris = [_as_points(t) for t in case["tris"]]
            mask = case["mask"]
            with self.subTest(preset=case["preset"], kind=case["kind"]):
                if case["kind"] == "region":
                    outer, holes = _as_points(mask["outer"]), [_as_points(h) for h in mask["holes"]]
                    region = RegionMask(outer, holes)
                    answers = [(region.overlaps(t), triangle_overlaps_region(t, outer, holes)) for t in tris]
                else:
                    path = _as_points(mask["path"])
                    path_mask = PathMask(path, mask["margin"], mask["closed"])
                    answers = [(path_mask.touches(t), brute_force_touches(t, path, mask["margin"], mask["closed"]))
                               for t in tris]
                self.assertTrue(answers)
                self.assertTrue(all(got == want for got, want in answers))


if __name__ == "__main__":
    unittest.main()
