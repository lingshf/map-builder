# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""Negative tests of tools/water_replay.py (S4-WATER-SURFACE, spec section 7): the replay must flag what it
should not label as an intended water change."""

from __future__ import annotations

import os
import sys
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

import water_replay as wr  # noqa: E402

WATER = "water:osm:way/1"
DECK = "bridge_way_7"


def head_pkg(report: dict | None = None, probes: list | None = None, raised: dict | None = None) -> SimpleNamespace:
    objects = [{"name": "terrain", "class": "terrain", "aabb": [-500, -500, 0, 500, 500, 9]},
               {"name": WATER, "class": "water", "aabb": [0, 0, 1, 100, 100, 1]},
               {"name": DECK, "class": "bridge", "aabb": [200, 0, 0, 260, 10, 9]}]
    return SimpleNamespace(col=SimpleNamespace(objects=objects), raised=raised if raised is not None else {DECK: 0.5},
                           names={o["name"] for o in objects} | {"osm:way/9", "bld"},
                           mbids={"osm:way/9"}, probes=probes or [], report=report or {})


def ctx() -> wr.Context:
    return wr.Context({"terrain", DECK}, head_pkg())


class RayLabelTest(unittest.TestCase):
    def test_water_over_old_bed_is_labelled(self) -> None:
        self.assertEqual(wr.ray_label((10.0, "terrain", "terrain"), (8.5, WATER, "water"), (50, 50), ctx()),
                         "new water hit")

    def test_bed_moved_needs_terrain_on_both_sides_near_water(self) -> None:
        c = ctx()
        self.assertEqual(wr.ray_label((10.0, "terrain", "terrain"), (11.0, "terrain", "terrain"), (120, 50), c),
                         "bed moved")
        self.assertEqual(wr.ray_label((10.0, "terrain", "terrain"), (11.0, "terrain", "terrain"), (400, 400), c),
                         "unlisted")

    def test_farther_building_replacing_terrain_is_not_a_bed_move(self) -> None:
        self.assertEqual(wr.ray_label((10.0, "terrain", "terrain"), (12.0, "bld", "building"), (50, 50), ctx()),
                         "unlisted")

    def test_deleted_dry_bridge_hit_is_not_a_deck_raise(self) -> None:
        c = ctx()
        self.assertEqual(wr.ray_label((5.0, "bridge_way_dry", "bridge"), (9.0, "terrain", "terrain"), (230, 5), c),
                         "unlisted")
        self.assertEqual(wr.ray_label((5.0, "bridge_way_dry", "bridge"), None, (230, 5), c), "unlisted")

    def test_deck_raise_must_be_reported_and_bounded(self) -> None:
        c = ctx()
        self.assertEqual(wr.ray_label((5.0, DECK, "bridge"), (4.6, DECK, "bridge"), (230, 5), c), "deck raised")
        self.assertEqual(wr.ray_label((5.0, DECK, "bridge"), (3.0, DECK, "bridge"), (230, 5), c), "unlisted")
        self.assertEqual(wr.ray_label((5.0, DECK, "bridge"), (5.4, DECK, "bridge"), (230, 5), c), "unlisted")

    def test_distance_change_under_1mm_is_equal_and_above_is_not(self) -> None:
        c = ctx()
        self.assertIsNone(wr.ray_label((5.0, DECK, "bridge"), (5.0005, DECK, "bridge"), (230, 5), c))
        self.assertEqual(wr.ray_label((5.0, "bld", "building"), (5.002, "bld", "building"), (230, 5), c), "unlisted")


class CapsuleLabelTest(unittest.TestCase):
    def test_only_new_water_may_enter_and_only_reported_things_leave(self) -> None:
        c = ctx()
        self.assertEqual(wr.capsule_labels([], [(WATER, "water")], (10, 10), c), ["new water hit"])
        self.assertEqual(wr.capsule_labels([], [("bld", "building")], (10, 10), c), ["unlisted"])
        self.assertEqual(wr.capsule_labels([("bridge_way_dry", "bridge")], [], (10, 10), c), ["unlisted"])
        self.assertEqual(wr.capsule_labels([(DECK, "bridge")], [], (10, 10), c), ["deck raised"])
        self.assertEqual(wr.capsule_labels([("terrain", "terrain")], [], (400, 400), c), ["unlisted"])


class PassageReasonTest(unittest.TestCase):
    BASE = SimpleNamespace(probes=[{"id": "a:deck"}, {"id": "a:under"}], report={"passage_probes_blocked": []})

    def head(self, row: dict) -> SimpleNamespace:
        return head_pkg(report={"passage_probes_blocked": [row] if row is not None else []},
                        probes=[{"id": "a:deck"}])

    def check(self, row: dict | None, reason: str) -> list[str]:
        h = self.head(row)  # type: ignore[arg-type]
        return wr.passage_check(self.BASE, h, {"a:under": reason}, {}, {"a:under": reason})

    def test_backed_reason_passes(self) -> None:
        self.assertEqual(self.check({"id": "a:under", "blocker": "osm:way/9"}, "blocked-by-osm:way/9"), [])

    def test_id_only_report_row_is_rejected(self) -> None:
        self.assertTrue(any("no non-empty reason" in p for p in self.check({"id": "a:under"}, "anything")))
        self.assertTrue(any("no row" in p for p in self.check(None, "anything")))

    def test_invented_reason_is_rejected(self) -> None:
        out = self.check({"id": "a:under", "blocker": "osm:way/9"}, "made-up-cli-reason")
        self.assertTrue(any("does not quote" in p for p in out), out)

    def test_blocker_must_be_a_head_object(self) -> None:
        out = self.check({"id": "a:under", "blocker": "osm:way/404"}, "x-osm:way/404")
        self.assertTrue(any("not an object of HEAD" in p for p in out), out)

    def test_listed_extra_or_missing_ids_fail(self) -> None:
        h = self.head({"id": "a:under", "blocker": "osm:way/9"})
        out = wr.passage_check(self.BASE, h, {"a:under": "osm:way/9", "zz": "x"}, {"n": "x"}, {})
        self.assertEqual(len(out), 3, out)


if __name__ == "__main__":
    unittest.main()
