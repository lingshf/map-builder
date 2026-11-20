# S3-PARITY: CLI vs Blender passage-probe parity (hygiene, time-boxed)

Owner: dev · sprint S3 · wave 2 · time box ½ day · D62

## Background

At the v0.3.0 close, the CLI and headless Blender emitted different probe counts for the same
area:

| Area | CLI probes | Blender probes |
|---|---|---|
| Munich | 3 | 1 |
| Pittsburgh | 13 | 14 |

Both packages were VALID and every emitted probe passed, so this is not a correctness failure.
It is still an unexplained divergence.

## Scope

1. Build Munich and Pittsburgh from the **same cached acquisition** with the CLI and with
   headless Blender. Diff the probe lists by `mb_id`/kind.
2. Explain each difference, for example: Blender-side splitting, an evaluated-mesh difference,
   or a budget/ordering difference.
3. Choose one of:
   * if a difference is a bug, fix it in this PR when it is ≤ ~50 lines in the probe/export
     path, otherwise file `S3-PARITY-FIX`;
   * if a difference is intended, document it in `docs/VALIDATION.md`.

## Acceptance criteria

1. `tests/blender/checks_parity.py` compares the CLI and Blender probe sets on the synthetic
   fixture and asserts equality, or a documented allow-list with reasons.
2. The PR contains the Munich and Pittsburgh diff table and a classification for each
   difference.
3. Because this touches probes (D47), Python and C# real-data runs on Pittsburgh are attached.
4. If the time box expires, report the findings so far and stop. The coordinator decides.

## Performance considerations

No product-path cost. The Blender check adds ≤ 5 s to the local harness, and none to PR CI.

## Conflict domain

Hard: `tests/blender/checks_parity.py` (new). Soft (only if fixing): `blender/bake.py` probe
export or `core/probes*`. If a fix touches `bake.py`, serialise it with S3-TEX-BLENDER.
