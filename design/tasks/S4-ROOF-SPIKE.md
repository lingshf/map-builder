# S4-ROOF-SPIKE: measure the S4 roof construction before setting the target

Owner: dev · sprint S4 · lane A, first · time box ½ day · D90, D95

## Background

Of the 67 tagged non-flat Munich roofs, 29 are built as tagged under the frozen checker
(`tests.test_roofs_munich`). The 38 uncounted roofs are:

| Count | Outcome | Reason |
|---|---|---|
| 21 | gabled → hipped | ridge meets the gable edge outside it |
| 9 | gabled → hipped | sliver gable end (`GABLE_MIN_HEIGHT_RATIO`) |
| 4 | gabled, analytic | none; they fail the checker's `planar` test (S3-F1) |
| 1 + 1 + 1 + 1 | flat | courtyard; quadruple_saltbox; roof height 0; concave pyramidal |

The sprint-3 target of 40 was set without a measurement (D90 retro). This spike measures the input to the
stretch. No stretch number exists until it does (D95).

## Scope

A throw-away prototype, on a branch that is **not merged**, of:

1. vertical cuts across chamfered or angled gable ends;
2. mixed gable + hip ends (a gable where it is representable, a hip elsewhere);
3. pyramidal roofs on concave footprints through the skeleton;
4. the reference-plane warp fix for the 4 analytic gables (S3-F7).

Run it on the frozen Munich snapshot with the **unchanged** checker (`tests/roof_checks.py`).

## Acceptance criteria

1. A PR comment, or a draft PR that is closed, reports for each of the 4 items: the roofs it would turn into
   counted roofs (OSM way ids), the roofs it would not, and why.
2. It reports the measured total counted under the unchanged checker, for example "29 → N", with the scratch
   branch SHA and the snapshot SHA-256 so it can be replayed. It also gives an effort estimate for S4-ROOF-ENDS
   (lines touched, risk).
3. **Final-checker replay (D95).** If S4-ROOF-NAMED merges a checker change (reference plane only), the spike
   branch is rebased onto that main and both numbers are replayed under the final checker: the floor baseline
   (main, no S4 construction) and the spike count. Only the replayed pair is reported to the coordinator, who
   records the stretch as a D-number before S4-ROOF-ENDS starts. If the checker did not change, the original
   pair stands; say so explicitly.
4. It reports any checker change that would be *needed*. Such a change is a finding for the coordinator,
   never part of the measurement.
5. When the time box expires, report what was measured and stop.

## Performance considerations

None on the product path. Note the roof-stage time of the prototype on Munich for information.

## Expected tests

None merged.

## Conflict domain

None merged (scratch branch). Reads `core/roofs.py`, `core/skeleton.py`, `tests/roof_checks.py`.
