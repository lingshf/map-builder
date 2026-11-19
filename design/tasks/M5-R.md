# M5-R: end-of-v2 review

Owner: Design · depends on M5-DEMO merged

## Checklist

1. **Goal met?** On the demo package, a drone-sized capsule (r = 1 m) can pass under at least
   one real bridge, through the real tunnel and beneath an elevated part/passage, shown by
   validator + C# probe results and the renders.
2. **Design conformance across v2:** decisions D17–D25 honoured or explicitly superseded in the
   decision record; follow-ups from M3-R and M4-R closed or consciously deferred.
3. **SOLID without over-engineering:** size and responsibility of `generate.py`, `osm.py` and the
   new modules; dead code and leftover stubs removed.
4. **Performance:** real-data build ≤ 120 s, CI ≤ 10 min, probe budget headroom on the demo;
   regressions vs v1 explained.
5. **Test audit (whole suite):** coverage of every v2 acceptance criterion; flaky or slow tests;
   Blender headless coverage of bridges/tunnels/passages; consumer-facing checks (C# reader,
   probes) in CI.
6. **Handoff:** UNITY_CORE_HANDOFF.md checklist for the simulator (under-bridge/tunnel flight now
   in scope for the consumer); PROJECT_BRIEF.md PR history and open items; README Limits.
7. **Open items for v3:** list (e.g. railway structures if D24 stays, LOD, textures, licence D13).

## Output

`design/reviews/M5-R.md`; problems become `design/tasks/M5-Fn.md` rows; final report to the
coordinator with a go/no-go for closing v2.

## Conflict domain

`design/` only.
