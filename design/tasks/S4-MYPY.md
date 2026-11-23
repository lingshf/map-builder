# S4-MYPY: mypy-clean main with a CI step

Owner: dev · sprint S4 · **v0.5.0 blocker** (D128) · after S4-COL-FLOAT-2 (#77)

## Problem

`pyproject.toml` `[tool.mypy]` checks `map_builder` and `tools` with `disallow_untyped_defs` and
`disallow_incomplete_defs`, but no CI job runs it (D79 kept S3-TYPING local). Main has drifted: the REL-v0.5.0 RC
(#75) counted **19 errors in 6 files** on main, none touched by the RC. #77 adds `core/shore.py` and
`core/overlap.py` and edits `core/water.py`, `core/generate.py` and `core/package.py`, so the error set is final
only once #77 has merged.

## Sequence (D128, D133)

1. **While #77 is open: read-only triage.** Run `python -m mypy` on main and on the #77 head; post the error list
   (file:line, code, one-line cause, planned fix) to the coordinator. No branch, no edits.
2. **After #77 merges:** branch from main and fix.

## Change

* Fix every mypy error in the configured scope with annotations, narrowing (`assert x is not None`, `isinstance`)
  or small type-only refactors. **No behaviour change.**
* `# type: ignore[<code>]` only with the exact code and a one-line reason, only where a fix would change behaviour
  or the error comes from a third-party stub; each is listed in the PR.
* The mypy configuration is not weakened: no new global `ignore_errors`, no removed flags, no newly excluded
  modules. A new per-module override needs a reason in the PR, like the existing `map_builder.blender.props` one.
* Add a CI step `python -m mypy` (configuration from `pyproject.toml`, pinned mypy version) that fails on any error.

## Acceptance criteria

1. `python -m mypy` reports `Success: no issues found` on the PR head, locally and in CI, with the pinned version.
2. **Byte identity (D97):** the committed sample and the frozen Munich and Pittsburgh CLI builds are byte-identical
   before and after, as whole archives; validator verdicts and messages unchanged. Both sides are built fresh with
   the same pinned inputs and settings as S4-WATER-BANK: frozen caches, seed 1, DSM on, offline,
   `created_utc = "2026-11-20T00:00:00Z"`, same export options. Blender: the sample through headless Blender is
   byte-identical under the same pins (the presets too if `map_builder/blender/` changed).
3. Unit suite: same test count and result as the base (nothing added, removed or skipped to make mypy pass).
4. **CI budget:** the new step adds ≤ 60 s to the slowest job; PR CI stays ≤ 10 min. mypy runs once, in one job
   (the Python 3.12 leg or a separate light job), not in every matrix leg.
5. The PR lists touched files with error counts before → after, and every `type: ignore` with its reason.
6. **Performance:** none expected; AC2 proves identical output, so one sanity CLI Pittsburgh pair is enough. D106
   alternating rounds only if non-annotation code changed.

## Tests

None new: mypy in CI is the test. No tests that only restate types.

## Conflict domain

Hard: `pyproject.toml` (`[tool.mypy]`), `.github/workflows/ci.yml` (the new step only), and the files with mypy
errors on main after #77 (listed by the triage; expected to overlap the `core/` modules #77 touches, hence the
serial order). Not the sample. REL-v0.5.0 waits for this task, then updates the VALIDATION row to mypy-clean with
CI enforcement.
