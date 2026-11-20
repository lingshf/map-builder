# S4-REVIEW: sprint 4 milestone review and test audit

Owner: design · sprint S4 · after all S4 dev tasks · D104

## Checks (on main, fresh worktree)

1. **Roofs:** Munich counted against the floor 29 and the recorded stretch (D95). Every uncounted roof is named
   (38/38 or the new total). The frozen v0.3.0 replay stays 1/67. Spot renders of one vertical-cut gable, one
   mixed end and one named fallback.
2. **Collision:** 0 degenerate triangles in the sample and both presets through both paths. Probe ids and
   results are equal in Python and C#.
3. **Water:** the river region colour rule holds on a re-render (S4-TEX-WATER AC1).
4. **Performance (D91):** whole Generate, Pittsburgh and Munich, CLI and headless Blender, median of 3, against
   v0.4.0 from frozen inputs. Byte identity of PERF-PKG and PERF-UV checked independently (D97).
5. **Tests:** full suite with a private user-level NuGet feed configured (0 errors); two parallel suites; the
   slowest tests; no wall-clock gates; no finalizer ResourceWarning; PR CI times.
6. **Publishing:** `extension validate`; two clean builds from fresh clones are byte-identical; the
   `PLATFORM_SUBMISSION.md` checklist is complete apart from the user actions.
7. **Format policy:** the PACKAGE_FORMAT section matches D101 and its tests run.
8. **Design conformance:** each task stayed in its conflict domain; SOLID without over-engineering; the
   review-round count per PR against D89.
9. **v1.0 readiness:** evaluate each draft exit criterion (D102) as met, not met or user action.

## Deliverable

`design/reviews/S4-REVIEW.md`: verdict GO or NO-GO, gaps as S4-Fn tagged as v0.5.0 blockers or later, notes for
REL-v0.5.0, and retro notes. Roadmap rows for any new decisions. One PR, merged only through the coordinator's
gate (D47).

## Conflict domain

`design/` only.
