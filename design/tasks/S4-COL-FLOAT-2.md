# S4-COL-FLOAT-2: close the water-sheet/bank gaps with terrain shore ramps

Owner: dev · sprint S4 · **v0.5.0 blocker** (D126, D129) · after S4-COL-FLOAT (#76) · PR #77

This spec was written after the PR opened (D133). It records the criteria that the three review rounds on #77
converged on, so the coordinator's D89 ruling (D135) and the final check measure against a fixed list instead of
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
    different levels, falling from the higher sheet onto the lower (receiving) one.
* Bank ramps are `bank:<osm-id>` terrain objects (visual and collision, class `terrain`); cascades belong to the
  higher body's `water:<osm-id>` object. `core/package.py` `_MB_ID` accepts `bank:` (D125).
* A vertical skirt is not allowed: terrain, road and water are +Z-only open surfaces and the validator rejects
  down-facing triangles. A confined carve is not allowed: it breaks the −1.5 m bed (D113–D118).
* Every strip is typed per transition (bank or cascade); a strip whose two ends differ is split and each part is
  judged on its own type (#77 R1, under the D127 readability rule). A strip that fails a mask is skipped whole and its length added to
  `info["shore_ramp_blocked_m"]`.

## Acceptance criteria

Inputs and settings as S4-WATER-BANK (sample fixture; frozen caches for Munich and Pittsburgh; seed 1, DSM on,
offline; `created_utc = "2026-11-20T00:00:00Z"`). Base = main at the PR's merge-base (53c54d3 or later).

1. **Gap closed.** `tools/floating_audit.py` (threshold 0.2 m) on sample, Munich and Pittsburgh, CLI and headless
   Blender: **0** `water_above_bank` and **0** `water_buried` regions. The remaining `water_shore_step` (info
   only, the designed slope across the 1 m audit ring) is listed with its count and maximum, which is ≤ 1.5 m.
2. **No ramp over protected geometry (R1.1).** Every **emitted** ramp and cascade triangle is tested over its whole
   area against building footprints, road ribbons and bridge abutments, not at its vertices or along a centre
   line. A strip with any triangle that meets a mask is skipped and counted in `shore_ramp_blocked_m`. This mask
   may stay conservative: boundary contact may block a strip, and this spec adds no rule that it must pass.
3. **No ramp over water except its own landing (R2.1, R3.1, R3.2).** A bank triangle has zero positive-area overlap
   with any body piece (outer minus holes). The wet test (`overlap.triangle_overlaps_region`) uses the emitted
   triangle **unshrunk**. It separates boundary-only contact (allowed, for example an edge on the triangle's own
   sheet outline) from positive-area overlap (blocked). If an area tolerance is kept, it is a named constant in m²,
   stated in the PR and pinned by one test on each side of it. A cascade runs from a higher body down to a
   **lower** receiving body (see Design). It may overlap only that receiving body; every other body is checked
   like a bank.
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
7. **Performance (D91, D106, D147) on the exact merge head.** One rule: **5 alternating offline base/head rounds**
   per preset, judged on the median of **CPU time** (`time.process_time`); elapsed wall time is posted for the record.
   Three series, each judged separately:
   * CLI whole Generate (`design/bench/cli_time.py`, acquisition through package write and strict validation);
   * Blender **Generate**, measured inside Blender (`design/bench/bl_time.py`);
   * Blender **Generate+Export**, measured inside Blender (`design/bench/bl_time.py`).

   * **Per-PR gate:** each series is within **+5 % CPU** of the base. A head that changes shared generator geometry
     needs fresh numbers on every series, because numbers from an earlier head do not carry over (R3.4). Stages
     may move inside the +5 % (D109). An exception is recorded as a coordinator decision, never left out silently.
   * **Release floor (not a per-PR gate):** the Sprint 4 v0.4.0 floors are checked once, at the release candidate
     (REL-v0.5.0, #75). They use matched CPU time on the same host against a v0.4.0 (18f0822) CPU baseline (D147).
     #77 deferred its floor check to #75.
8. **Docs.** `docs/PACKAGE_FORMAT.md` and `docs/UNITY_CORE_HANDOFF.md` describe `bank:<id>` objects and ramps;
   the `.mbcol` and `.mbhf` formats are unchanged (D101, D110).
9. **Merge gate (D133, D135).** The D89 ruling limits rounds and scope only. The final head still needs an approval
   on that exact head, green CI, mergeability with current main and the coordinator's authorization. #77 merged
   under the one-off exception recorded in D146.

## Tests (≤ 5 s each, no wall-clock asserts, no duplicates)

Small synthetic cases in `tests/test_shore_ramps.py`, each failing on the code before its fix: footprint wholly
inside a strip (AC2); mixed bank/cascade strip (D127); wet patch inside a strip; the R3.1 sliver, a 0.001 m²
(1,000 mm²) wet overlap at a triangle edge (triangle (0,0),(12,0),(12,2) against wet x = 5..7, y = −1..0.0005),
versus pure boundary contact; a third body crossed by a cascade (all AC3). `tests/test_water_replay.py`:
the four AC5 rejections, including a sloped-edge case. `tests/test_floating_audit.py`: the off-terrain shore cell
rule. Do not repeat a case already covered by `tests/test_water.py`. The real-data runs (AC1, AC5, AC7) are PR
evidence and are not persisted as tests.

## Conflict domain

Hard: `core/shore.py`, `core/overlap.py` (both new), `core/water.py`, `core/generate.py` (water stage and the
terrain/ramp objects), `core/package.py` (`_MB_ID`), `tools/floating_audit.py`, `tools/water_replay.py`,
`tests/test_shore_ramps.py`, `tests/test_floating_audit.py`, `tests/test_water_replay.py`,
`docs/PACKAGE_FORMAT.md`, `docs/UNITY_CORE_HANDOFF.md`. Soft: sample slot (D103), VALIDATION row. S4-MYPY and
REL-v0.5.0 wait for this task (D128, D133).
