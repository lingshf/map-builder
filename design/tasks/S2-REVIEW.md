# S2-REVIEW: sprint 2 + end-of-v2 milestone review + test audit

Owner: Design · **D48: runs before REL-v0.3.0** on main after S1-F1/S1-F2; its findings define
the remaining v0.3.0 scope. A short close check on the RC replaces the post-RC review step of
[SPRINT_CLOSE.md](SPRINT_CLOSE.md) for v0.3.0. Report: [../reviews/S2-REVIEW.md](../reviews/S2-REVIEW.md)

## Checklist

1. **Goal met?** On the Pittsburgh package a drone capsule (r = 1 m) passes under a real bridge,
   through the real tunnel and beneath an elevated part/passage (validator + C# + renders).
2. **Design conformance:** ELEV reuses the elevated-volume path with `#k` ids (D24); roofs live
   in `core/roofs.py` behind one entry point; D17–D29 honoured or superseded in the record;
   S1 findings closed or consciously deferred.
3. **SOLID without over-engineering:** size and responsibilities of `generate.py`, `osm.py`
   and the new modules; dead code and leftover stubs removed.
4. **Performance:** real-data build ≤ 120 s, PR CI ≤ 10 min, probe-budget headroom.
5. **Test audit (whole suite):** coverage of every v2 acceptance criterion; slow/flaky tests;
   Blender headless coverage of bridges/tunnels/passages/roofs; C# reader and probes in CI.
6. **Release audit:** v0.1.0–v0.3.0 each have their assets and a working "How to try it".
7. **Handoff and v3:** UNITY_CORE_HANDOFF, PROJECT_BRIEF, README Limits; open items (railway
   structures per D25, LOD, textures, licence D13); go/no-go for closing v2.

## Output

`design/reviews/S2-REVIEW.md`; problems become `design/tasks/S2-Fn.md` rows; final report to
the coordinator.

## Conflict domain

`design/` only.
