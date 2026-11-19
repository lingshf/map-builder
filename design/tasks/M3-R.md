# M3-R: milestone review (M2 + M3)

Owner: Design · depends on M3-BRIDGE, M3-TUNNEL, M3-PIERS merged

## Checklist

1. **Design conformance:** do `core/bridges.py`, `core/tunnels.py` and `core/structures.py`
   follow M2-SEAMS / M3-* (stage hooks only in `generate.py`, shared sweep and probe helper
   used, D20–D22 honoured)? List deviations with file:line.
2. **SOLID without over-engineering:** one responsibility per module; no duplicated profile or
   sweep code between bridges and tunnels; no speculative abstractions (registries, base
   classes) added.
3. **Performance:** fixture build time, unit-test time and CI time against the roadmap targets
   (numbers from the PRs and one re-run on main).
4. **Test audit:** every acceptance criterion of M2-SEAMS, M3-BRIDGE, M3-TUNNEL, M3-PIERS maps to
   a test or a recorded manual run; probes PASS in Python and the C# reader; the tunnel leak
   test exists; headless Blender result recorded in VALIDATION.md; no tests that only restate
   constants.
5. **Docs:** PACKAGE_FORMAT, README Limits, UNITY_CORE_HANDOFF, VALIDATION consistent with the
   code (no "not generated yet" left for bridges/tunnels).

## Output

`design/reviews/M3-R.md` with findings; each problem becomes a task doc
`design/tasks/M3-Fn.md` and a row in the task table. Report to the coordinator.

## Conflict domain

`design/` only.
