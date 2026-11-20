# S3-PARITY: CLI vs Blender passage-probe parity (hygiene, time-boxed)

Owner: dev · sprint S3 · wave 2 · time box ½ day · D62, D64

## Background

At the v0.3.0 close, the CLI and headless Blender emitted different probe counts for the same
area:

| Area | CLI | Blender |
|---|---|---|
| Munich | 3 | 1 |
| Pittsburgh | 13 | 14 |

Both packages were VALID and every emitted probe passed, but the difference is unexplained.

## Scope

1. Build Munich and Pittsburgh from the **same acquisition file** with the CLI and with headless
   Blender. Record the acquisition SHA-256 in the PR. Diff the probe lists by `mb_id`/kind.
2. Explain each difference, for example Blender-side splitting, an evaluated-mesh difference,
   or a budget/ordering difference.
3. For each difference:
   * if it is a bug, fix it in this PR when the fix is ≤ ~50 lines in the probe/export path;
     otherwise file `S3-PARITY-FIX`;
   * if it is intended, document it.

## Acceptance criteria

1. `tests/blender/checks_parity.py` (new) is registered in `run_integration.py`. It compares
   the CLI and Blender probe sets on the synthetic fixture and asserts that they are equal, or
   match a documented allow-list with reasons.
2. The PR contains the Munich and Pittsburgh diff table and a classification of each
   difference.
3. Touches probes (D47): attach the Python and C# Pittsburgh runs.
4. If the time box expires, report the findings and stop; the coordinator decides.

**Optional (D64):**
* A `docs/VALIDATION.md` note, only if an intended difference needs documenting.
* No sample or fixture changes.

## Performance considerations

No product-path cost. The Blender check adds ≤ 5 s to the local harness and nothing to PR CI.

## Conflict domain

Hard: `tests/blender/checks_parity.py` (new). Soft: `tests/blender/run_integration.py` (one
appended line); optional `docs/VALIDATION.md` note. Only if fixing: `blender/bake.py` probe
export or `core/probes*`. A `bake.py` fix is serialised with S3-TEX-BLENDER.
