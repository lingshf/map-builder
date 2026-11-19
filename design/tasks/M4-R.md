# M4-R: milestone review (M4)

Owner: Design · depends on M4-ELEV, M4-ROOF merged

## Checklist

1. **Design conformance:** roofs live in `core/roofs.py` behind one entry point; the refactor
   commit was output-neutral; passages reuse the elevated-volume path (D23) instead of a second
   building builder; ids follow the `#k` rule.
2. **SOLID without over-engineering:** `build_building` is shorter, not more branched; no
   per-shape class hierarchy unless it removed duplication.
3. **Performance:** dome/onion triangle caps, passage polygon-difference cost, fixture build and
   CI time against the targets.
4. **Test audit:** each acceptance criterion of M4-ELEV and M4-ROOF maps to a test; elevated and
   passage probes PASS in Python and C#; Blender checks recorded.
5. **Docs:** provenance rules, unsupported list, VALIDATION matrix rows.

## Output

`design/reviews/M4-R.md`; problems become `design/tasks/M4-Fn.md` rows. Report to the
coordinator.

## Conflict domain

`design/` only.
