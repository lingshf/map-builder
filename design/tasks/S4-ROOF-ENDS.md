# S4-ROOF-ENDS: chamfered and angled gable ends, mixed ends, concave pyramidal

Owner: dev · sprint S4 · lane A · after S4-ROOF-SPIKE and S4-ROOF-NAMED · D82, D95 · closes S3-F10

## Background

30 Munich gabled roofs fall back to hipped because a gable end is not representable: 21 because the ridge
meets the gable edge outside it, 9 because the gable end is a sliver. One pyramidal roof is flat because its
footprint is concave. S4-ROOF-SPIKE measures how many of them the construction below turns into counted roofs.
After the final-checker replay, the coordinator records the stretch as a D-number (D95). This task does not
start before that number exists.

## Scope

1. **Vertical cut** across a chamfered or angled end: the gable wall is a vertical plane through the
   representable part of the end edge, and the remainder is hipped.
2. **Mixed ends:** a gable on each representable end and a hip on the others. The roof counts as gabled when
   the checker's gabled signature holds (≥ 2 gable ends, D82).
3. **Concave pyramidal** via the skeleton (one apex face per edge), or a named fallback.
4. Every roof that still falls back carries a named reason (keeps S4-ROOF-NAMED AC1).

## Acceptance criteria

1. **Must:** Munich counted ≥ **29** under the final checker, and every roof that is still uncounted is named.
   **Aim:** ≥ the recorded stretch (D95); if missed, the PR explains the gap per roof (way id, reason).
2. The checker is unchanged. Every new construction passes overlap, gap, slope-count, ridge and vertical-end
   checks on the emitted triangles (D64, D71, D80).
3. Synthetic cases written first (DoD 10): a chamfered L, a trapezoid end, a mixed end, a sliver end, a
   concave pyramid, plus counterexamples that must fall back with a named reason.
4. `roof:direction` handling follows D84.
5. Real data: Munich and Pittsburgh CLI and headless-Blender builds VALID; the per-shape table is in the PR.

## Performance considerations

Each construction is bounded by the skeleton event cap (`MAX_SKELETON_EVENTS`) and raises `LimitError`,
never a timeout. Roof stage on Munich ≤ +20 % against S4-ROOF-NAMED (information); whole Generate is the gate
(D91).

## Expected tests

`tests/test_roofs.py`, `tests/test_skeleton.py` (if the skeleton grows a helper),
`tests/test_roofs_munich.py`, `tests/blender/checks_roofs.py`. Each ≤ 5 s.

## Conflict domain

Hard: `core/roofs.py`, `core/skeleton.py`, `core/generate.py` (building roof section only),
`tests/test_roofs*.py`, `tests/test_skeleton.py`, `tests/blender/checks_roofs.py`. Soft: sample (D103),
VALIDATION row. Serialised after S4-ROOF-NAMED.
