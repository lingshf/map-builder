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


WTRI = [(0.0, 0.0), (100.0, 0.0), (0.0, 100.0)]


def head_pkg(report: dict | None = None, probes: list | None = None, raised: dict | None = None) -> SimpleNamespace:
    objects = [{"name": "terrain", "class": "terrain", "aabb": [-500, -500, 0, 500, 500, 9]},
               {"name": WATER, "class": "water", "aabb": [0, 0, 1, 100, 100, 1]},
               {"name": DECK, "class": "bridge", "aabb": [200, 0, 0, 260, 10, 9]}]
    return SimpleNamespace(col=SimpleNamespace(objects=objects), raised=raised if raised is not None else {DECK: 0.5},
                           names={o["name"] for o in objects} | {"osm:way/9", "bld"},
                           mbids={"osm:way/9"}, probes=probes or [], report=report or {})


BOX = (200.0, 0.0, 260.0, 10.0)


def ctx(base_top: float = 9.0, head_top: float = 9.0, head_box: tuple = BOX, **kw) -> wr.Context:
    c = wr.Context({"terrain", DECK}, head_pkg(), [WTRI],
                   ({DECK: (BOX, base_top)}, {DECK: (head_box, head_top)}))
    for k, v in kw.items():
        setattr(c, k, v)
    return c


T0, T1 = (10.0, "terrain", "terrain"), (11.0, "terrain", "terrain")
W = (8.5, WATER, "water")


class RayLabelTest(unittest.TestCase):
    def test_water_over_old_bed_is_labelled_when_the_terrain_went_down(self) -> None:
        self.assertEqual(wr.ray_label([T0], [W, T1], (50, 50), ctx()), "new water hit")

    def test_farther_water_must_not_hide_lost_nearer_terrain(self) -> None:
        # the base terrain is gone on HEAD (no terrain hit below the water): not explained
        self.assertEqual(wr.ray_label([T0], [(12.0, WATER, "water")], (50, 50), ctx()), "unlisted")
        # a nearer base building lost under the water is not explained either
        self.assertEqual(wr.ray_label([(9.0, "bld", "building"), T0], [(9.5, WATER, "water"), T1], (50, 50), ctx()), "unlisted")
        # terrain far from any new water cannot have been carved
        self.assertEqual(wr.ray_label([T0], [(12.0, WATER, "water"), (13.0, "terrain", "terrain")], (400, 400), ctx()),
                         "unlisted")

    def test_bed_moved_needs_terrain_on_both_sides_near_water(self) -> None:
        c = ctx()
        self.assertEqual(wr.ray_label([T0], [T1], (120, 50), c), "bed moved")
        self.assertEqual(wr.ray_label([T0], [T1], (400, 400), c), "unlisted")
        self.assertEqual(wr.ray_label([T1], [T0], (120, 50), c), "unlisted")     # terrain rose

    def test_terrain_replaced_by_bridge_needs_the_terrain_to_go_down(self) -> None:
        c = ctx()
        deck = (12.0, DECK, "bridge")
        self.assertEqual(wr.ray_label([T0, deck], [deck, (14.0, "terrain", "terrain")], (120, 50), c), "bed moved")
        self.assertEqual(wr.ray_label([T0, deck], [deck], (120, 50), c), "unlisted")   # terrain vanished

    def test_farther_building_replacing_terrain_is_not_a_bed_move(self) -> None:
        self.assertEqual(wr.ray_label([T0], [(12.0, "bld", "building")], (50, 50), ctx()), "unlisted")

    def test_deleted_dry_bridge_hit_is_not_a_deck_raise(self) -> None:
        c = ctx()
        dry = (5.0, "bridge_way_dry", "bridge")
        self.assertEqual(wr.ray_label([dry], [(9.0, "terrain", "terrain")], (230, 5), c), "unlisted")
        self.assertEqual(wr.ray_label([dry], [], (230, 5), c), "unlisted")

    def test_deck_raise_must_be_reported_bounded_and_near_water(self) -> None:
        c = ctx()
        d = lambda t: (t, DECK, "bridge")  # noqa: E731
        self.assertEqual(wr.ray_label([d(5.0)], [d(4.6)], (50, 50), c), "deck raised")
        self.assertEqual(wr.ray_label([d(5.0)], [d(3.0)], (50, 50), c), "unlisted")
        self.assertEqual(wr.ray_label([d(5.0)], [d(5.4)], (50, 50), c), "unlisted")
        self.assertEqual(wr.ray_label([d(5.0)], [d(4.6)], (400, 400), c), "unlisted")   # dry

    def test_distance_change_under_1mm_is_equal_and_above_is_not(self) -> None:
        c = ctx()
        d = lambda t: (t, DECK, "bridge")  # noqa: E731
        self.assertIsNone(wr.ray_label([d(5.0)], [d(5.0005)], (230, 5), c))
        self.assertEqual(wr.ray_label([(5.0, "bld", "building")], [(5.002, "bld", "building")], (230, 5), c),
                         "unlisted")


class RoadLoweredTest(unittest.TestCase):
    NEAR_WATER = (50, 50)
    FAR_FROM_WATER = (400, 400)

    def test_the_same_road_hit_farther_down_is_lowered(self) -> None:
        base, head = [(1.0, "road_a", "road")], [(9.0, "road_a", "road")]
        self.assertEqual(wr.ray_label(base, head, self.NEAR_WATER, ctx()), "road lowered")
        self.assertEqual(wr.ray_label(base, head, self.FAR_FROM_WATER, ctx()), "unlisted")

    def test_an_unrelated_deeper_road_replacing_the_base_road_is_not_lowered(self) -> None:
        base, head = [(1.0, "road_a", "road")], [(9.0, "road_b", "road")]
        self.assertEqual(wr.ray_label(base, head, self.NEAR_WATER, ctx()), "unlisted")

    def test_another_road_winning_is_not_lowered_even_if_the_base_road_is_still_hit_farther_down(self) -> None:
        base = [(1.0, "road_a", "road")]
        for winner_t in (0.5, 9.0):
            head = [(winner_t, "road_b", "road"), (9.5, "road_a", "road")]
            self.assertEqual(wr.ray_label(base, head, self.NEAR_WATER, ctx()), "unlisted", winner_t)

    def test_a_road_that_was_on_the_base_ray_and_moved_down_may_take_over_as_winner(self) -> None:
        base = [(1.0, "road_a", "road"), (1.3, "road_b", "road")]
        head = [(1.6, "road_b", "road")]
        self.assertEqual(wr.ray_label(base, head, self.NEAR_WATER, ctx()), "road lowered")

    def test_the_same_road_hit_higher_is_not_lowered(self) -> None:
        self.assertEqual(wr.ray_label([(1.0, "road_a", "road")], [(0.5, "road_a", "road")], self.NEAR_WATER, ctx()),
                         "unlisted")


class SharedEdgeRoadsStub:
    """Collision stub: ribbon A is a triangle whose edge x=0, y in [0, 1] is shared with ribbon B."""

    def __init__(self, drop_a: float, drop_b: float, gap: float = 0.0, swap_sides: bool = False) -> None:
        self.objects = [{"name": "road_a"}, {"name": "road_b"}]
        far_a, far_b = (1.0, -1.0) if swap_sides else (-1.0, 1.0)
        self.tris = {"road_a": [((far_a, 0.0, 5.0 - drop_a), (0.0, 0.0, 5.0 - drop_a), (0.0, 1.0, 5.0 - drop_a))],
                     "road_b": [((gap, 0.0, 5.0 - drop_b), (far_b, 0.0, 5.0 - drop_b), (gap, 1.0, 5.0 - drop_b))]}

    def object_triangles(self, entry: dict) -> list:
        return self.tris[entry["name"]]


class PinnedSharedEdgeTest(unittest.TestCase):
    ON_THE_SHARED_EDGE = (0.0, 0.5)
    PIN = wr.SharedEdgeSwap("area", 7, ON_THE_SHARED_EDGE, frozenset({"road_a", "road_b"}), "test")

    def setUp(self) -> None:
        self._pins = wr.PINNED_SHARED_EDGE_SWAPS
        wr.PINNED_SHARED_EDGE_SWAPS = (self.PIN,)

    def tearDown(self) -> None:
        wr.PINNED_SHARED_EDGE_SWAPS = self._pins

    def swap(self, head_stub: SharedEdgeRoadsStub, index: int = 7, name: str = "area") -> bool:
        base = SimpleNamespace(col=SharedEdgeRoadsStub(0.0, 0.0), manifest={"name": name})
        head = SimpleNamespace(col=head_stub, manifest={"name": name})
        return wr.pinned_shared_edge_swap(base, head, index, self.ON_THE_SHARED_EDGE,
                                          (1.0, "road_a", "road"), (1.1, "road_b", "road"))

    def test_the_pinned_ray_on_a_shared_edge_lowered_together_is_accepted(self) -> None:
        self.assertTrue(self.swap(SharedEdgeRoadsStub(0.1, 0.1)))

    def test_the_same_shared_edge_on_an_unpinned_ray_or_package_is_rejected(self) -> None:
        self.assertFalse(self.swap(SharedEdgeRoadsStub(0.1, 0.1), index=8))
        self.assertFalse(self.swap(SharedEdgeRoadsStub(0.1, 0.1), name="other"))

    def test_ribbons_lowered_by_different_amounts_are_rejected(self) -> None:
        self.assertFalse(self.swap(SharedEdgeRoadsStub(0.1, 0.2)))

    def test_ribbons_swapping_sides_of_the_shared_edge_are_rejected(self) -> None:
        self.assertFalse(self.swap(SharedEdgeRoadsStub(0.1, 0.1, swap_sides=True)))

    def test_a_lateral_move_leaving_a_1_5_mm_gap_is_rejected(self) -> None:
        self.assertFalse(self.swap(SharedEdgeRoadsStub(0.1, 0.1, gap=0.0015)))


class CapsuleLabelTest(unittest.TestCase):
    WET = [[10, 10, 5], [30, 10, 5]]
    DRY = [[300, 300, 5], [320, 300, 5]]

    def test_only_new_water_may_enter_and_only_reported_things_leave(self) -> None:
        c = ctx()
        self.assertEqual(wr.capsule_labels([], [(WATER, "water")], self.WET, 1.0, c), ["new water hit"])
        self.assertEqual(wr.capsule_labels([], [("bld", "building")], self.WET, 1.0, c), ["unlisted"])
        self.assertEqual(wr.capsule_labels([("bridge_way_dry", "bridge")], [], self.WET, 1.0, c), ["unlisted"])
        self.assertEqual(wr.capsule_labels([("terrain", "terrain")], [], self.DRY, 1.0, c), ["unlisted"])

    def test_deck_raise_needs_overlap_with_water_a_reported_raise_and_a_present_bridge(self) -> None:
        c = ctx()
        self.assertEqual(wr.capsule_labels([(DECK, "bridge")], [], self.WET, 1.0, c), ["deck raised"])
        self.assertEqual(wr.capsule_labels([(DECK, "bridge")], [], self.DRY, 1.0, c), ["unlisted"])     # dry
        c.present = c.present - {DECK}
        self.assertEqual(wr.capsule_labels([(DECK, "bridge")], [], self.WET, 1.0, c), ["unlisted"])     # gone
        c = ctx(raised={})
        self.assertEqual(wr.capsule_labels([(DECK, "bridge")], [], self.WET, 1.0, c), ["unlisted"])     # unreported

class BridgeGeometryTest(unittest.TestCase):
    """A bridge name match is not evidence; its collision geometry must have changed only as reported."""

    def test_bridge_revealed_but_risen_more_than_reported(self) -> None:
        base = [(1.0, "terrain", "terrain"), (9.0, DECK, "bridge")]
        head = [(2.0, DECK, "bridge"), (10.0, "terrain", "terrain")]
        self.assertEqual(wr.ray_label(base, head, (120, 50), ctx(head_top=16.0)), "unlisted")
        self.assertNotEqual(wr.ray_label(base, head, (120, 50), ctx()), "unlisted")

    def test_sideways_moved_bridge_is_not_a_deck_raise(self) -> None:
        wet = [[10, 10, 5], [30, 10, 5]]
        moved = ctx(head_box=(300.0, 0.0, 360.0, 10.0))
        self.assertEqual(wr.capsule_labels([(DECK, "bridge")], [], wet, 1.0, moved), ["unlisted"])
        self.assertEqual(wr.capsule_labels([(DECK, "bridge")], [], wet, 1.0, ctx(head_top=9.4)), ["deck raised"])
        self.assertEqual(wr.capsule_labels([(DECK, "bridge")], [], wet, 1.0, ctx(head_top=9.6)), ["unlisted"])


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
