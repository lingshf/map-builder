# S4-BLENDER-HYGIENE: bbox precision and the "MB Default" material name

Owner: dev · sprint S4 · lane B · D74, D88 · closes S3-F6, S3-F11

## Background

* S3-F6 (D74): an area bounding box derived from Blender float32 values loses precision far from the origin.
  The centre itself is already text (`blender/props.py:51`).
* S3-F11: with D88 material keys, the default material can be exported as "MB Default" plus a digest suffix
  instead of the plain name (`blender/bake.py:64`).

## Scope

1. Derive the bbox and outside-area tests from the double-precision centre and extent, not float32 object
   data. First write a test that fails on main (for example an area at 48 N with a 0.5 m edge feature).
2. Export the unmodified default material under its plain name; any parameter variant keeps the D88 digest.

## Acceptance criteria

1. **Pre-change measurement:** on f8bedf6, record in the PR the bbox error (metres, per edge) of the
   Blender-derived area against the double-precision area for the Munich and Pittsburgh centres and one area
   at 48 N far from the origin. The test threshold is set from that table (must: below the smallest feature the
   test uses). A headless Blender check reproduces the error on f8bedf6 and passes after the fix.
2. The exported GLB names the default material "MB Default" exactly when its parameters equal the default;
   material identity is still the D88 key (existing tests unchanged).
3. Munich and Pittsburgh headless-Blender builds VALID, with the same probe ids as the CLI.

## Performance considerations

None measurable. Report Blender whole Generate (D91).

## Expected tests

`tests/blender/checks_*.py` (one new check per item), plus a pure-Python unit test where the logic is in a
helper. Each ≤ 5 s.

## Conflict domain

Hard: `blender/export.py` (material naming), `blender/bake.py` (default material, bbox), the bbox code in
`blender/sources.py` or `blender/props.py` if it lives there, new Blender checks. Soft:
`tests/blender/run_integration.py` (one line). Serialised before S4-COL-DEGEN.
