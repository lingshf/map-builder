# S4-COL-FLOAT-2: close the water-sheet/bank gaps with terrain shore ramps

Owner: dev · sprint S4 · **v0.5.0 blocker** (D126, D129) · after S4-COL-FLOAT (#76) · PR #77

This spec is written after the PR opened (D130). It records the criteria that the three review rounds on #77
converged on, so the coordinator's D89 ruling and any final check measure against a fixed list instead of
discovering new ones. It adds no criterion that R1–R3 did not already raise.

## Problem

`_carve_body` carves every cell under a body to (lowest shore level − 1.5 m). The bank blend only lowers terrain,
so the flat water sheet's edge can hang above the terrain outside it. The simulator takes the highest
terrain/road/water triangle as the ground (`GroundBelow`), so a descending drone stops on the sheet edge, and the
GLB shows a floating "mat". `tools/floating_audit.py` (#76) reports these as `water_above_bank`: Pittsburgh
10 regions, 380 m², max 6.28 m on main 53c54d3 (relation/1080 banks below the shore level, plus a 6.28 m level step
to the abutting relation/7937544). Sample and Munich: 0.

## Design (as built in #77)

* New `core/shore.py` builds sloped **terrain ramps**. A bank ramp starts 0.02 m under the sheet edge and falls at
  slope 0.5 to the ground, at most 12 m wide, and stops at water. A **cascade** joins two abutting bodies at
  different levels.
* Bank ramps are `bank:<osm-id>` terrain objects (visual and collision, class `terrain`); cascades belong to the
  higher body's `water:<osm-id>` object. `core/package.py` `_MB_ID` accepts `bank:` (D125).
* A vertical skirt is not allowed: terrain, road and water are +Z-only open surfaces and the validator rejects
  down-facing triangles. A confined carve is not allowed: it breaks the −1.5 m bed (D113–D118).
* Every strip is typed per transition (bank or cascade); a strip whose two ends differ is split and each part is
  judged on its own type (D127). A strip that fails a mask is skipped whole and its length added to
  `info["shore_ramp_blocked_m"]`.

## Acceptance criteria

Inputs and settings as S4-WATER-BANK (sample fixture; frozen caches for Munich and Pittsburgh; seed 1, DSM on,
offline; `created_utc = "2026-11-20T00:00:00Z"`). Base = main at the PR's merge-base (53c54d3 or later).

1. **Gap closed.** `tools/floating_audit.py` (threshold 0.2 m) on sample, Munich and Pittsburgh, CLI and headless
   Blender: **0** `water_above_bank` and **0** `water_buried` regions. The remaining `water_shore_step` (info
   only, the designed slope across the 1 m audit ring) is listed with its count and maximum, which is ≤ 1.5 m.
2. **No ramp over protected geometry (exact, positive area).** Each **emitted** ramp and cascade triangle has zero
   positive-area overlap with building footprints, road ribbons and bridge abutments. The predicate tests the
   emitted triangle itself (no shrink, no vertex or centre-line sampling). Shared boundary contact is not
   overlap. If a tolerance is kept, it is a named constant in m², stated in the PR and pinned by a test on each
   side of it (R3.1).
3. **No ramp over water except its own landing.** A bank triangle has zero positive-area overlap with any body
   piece (outer minus holes). A cascade triangle may overlap only the **receiving** body it lands on; any other
   body is checked like a bank (R3.2).
4. **Bed and decks unchanged.** −1.5 m bed, wet clearance (D116) and decks-never-lowered hold on every body; the
   `tools/water_check.py` invariants pass unchanged.
5. **Replay (§7 of `tools/water_replay.py`), Python and C#.** Every base → head query difference is listed. The
   new `bank ramp` label is accepted only when **all** of these hold, each with a rejecting test (R1.2, R2.2,
   R3.3):
   * the hit object is `bank:<id>` of a body built in the head package;
   * the ray's XY lies within the ramp reach (12 m) of that body's actual collision outline (not its bbox);
   * the hit is at or below the sheet elevation **interpolated** at the closest outline point;
   * the same base terrain object is still hit at or below the base surface.
   0 `unlisted` on all six package/path runs; Python and C# agree on every query.
6. **Munich and packages without water** are byte-identical on both paths. The sample is regenerated only under the
   D103 slot and the PR lists the member changes.
7. **Performance (D91, D106) on the exact merge head.** Three alternating offline base/head rounds per preset,
   whole path: CLI (`design/bench/cli_time.py`, acquire through strict validation) **and** Blender Generate+Export
   (`design/bench/bl_time.py`). Each median of per-round medians stays within **+5 %** of the base. A head that
   changes shared generator geometry needs fresh numbers on both paths; numbers from an earlier head do not carry
   over (R3.4). Stages may move inside the +5 % (D109).
8. **Docs.** `docs/PACKAGE_FORMAT.md` and `docs/UNITY_CORE_HANDOFF.md` describe `bank:<id>` objects and ramps;
   the `.mbcol` and `.mbhf` formats are unchanged (D101, D110).

## Tests (≤ 5 s each, no wall-clock asserts, no duplicates)

Small synthetic cases in `tests/test_shore_ramps.py`, each failing on the code before its fix: footprint wholly
inside a strip; mixed bank/cascade strip; wet patch inside a strip; sub-1 mm² positive-area overlap at a triangle
edge versus pure boundary contact (AC2); third body crossed by a cascade (AC3). `tests/test_water_replay.py`:
the four AC5 rejections, including a sloped-edge case. `tests/test_floating_audit.py`: the off-terrain shore cell
rule. Do not repeat a case already covered by `tests/test_water.py`. The real-data runs (AC1, AC5, AC7) are PR
evidence and are not persisted as tests.

## Conflict domain

Hard: `core/shore.py`, `core/overlap.py` (both new), `core/water.py`, `core/generate.py` (water stage and the
terrain/ramp objects), `core/package.py` (`_MB_ID`), `tools/floating_audit.py`, `tools/water_replay.py`,
`tests/test_shore_ramps.py`, `tests/test_floating_audit.py`, `tests/test_water_replay.py`,
`docs/PACKAGE_FORMAT.md`, `docs/UNITY_CORE_HANDOFF.md`. Soft: sample slot (D103), VALIDATION row. S4-MYPY and
REL-v0.5.0 wait for this task (D128, D130).
