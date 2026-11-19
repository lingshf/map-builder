# S1-REVIEW: sprint 1 milestone review + test audit

Owner: Design · after REL-v0.2.0's RC PR merges, before the retro and tag ·
[SPRINT_CLOSE.md](SPRINT_CLOSE.md) step 3

## Checklist

1. **Design conformance:** SEAMS, BRIDGE, PIERS, TUNNEL follow their task docs and D18–D25
   (hooks only in `generate.py`; shared sweep and probe helper used by bridges and tunnels;
   blocked probes reported, not emitted; terrain cut + leak test). Deviations with file:line.
2. **SOLID without over-engineering:** one responsibility per module, no duplicated geometry,
   no speculative registries or class hierarchies; `run_integration.py` split kept small.
3. **Performance:** fixture build, unit-suite and PR CI time vs the roadmap targets; Pittsburgh
   build time from the RC.
4. **Test audit:** every acceptance criterion maps to a test or a recorded run; probes PASS in
   Python and C#; headless Blender checks recorded; no wall-clock gates in the PR suite; no new
   test > 5 s; no tests that only restate constants.
5. **Docs/demo:** PACKAGE_FORMAT, README Limits, UNITY_CORE_HANDOFF, VALIDATION, `docs/user`
   consistent with code; RC demo shows what the notes claim.

## Output

`design/reviews/S1-REVIEW.md`; each problem becomes `design/tasks/S1-Fn.md` and a table row,
marked *blocker* (fixed before the tag) or scheduled in S2. Report to the coordinator.

## Conflict domain

`design/` only.
