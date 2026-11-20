# S3-TEX-FORMAT: package format 2.1.0 support, UVs and embedded textures in GLB

Owner: dev · sprint S3 · wave 1 · D57, D58, D64

## Goal

Let `visual/map.glb` carry glTF 2.0 core PBR textures while staying self-contained. The writer,
the validator and the C# reader learn schema **2.1.0** (minor, additive). `.mbcol` and the
heightfield are unchanged.

**Out of scope (D64):** this task does **not** change the default `PACKAGE_SCHEMA_VERSION` and
does not regenerate `examples/synthetic_sample.mbmap`. Its tests build 2.1.0 packages by passing
the version explicitly. S3-TEX-UV-CORE flips the default when packages first contain textures,
and it is the sole owner of the sample.

## Scope

* `core/mesh.py`: optional per-face-corner UVs, `MeshData.face_uvs` (`None` = no UVs).
* `core/glb.py` `write_glb`:
  * Emit `TEXCOORD_0` (float32 VEC2) for primitives whose material has a texture, and only for
    those.
  * Write `images` (bufferView + `image/png` in the single BIN buffer, each image once),
    `textures`, and one `sampler` (REPEAT/REPEAT, LINEAR_MIPMAP_LINEAR/LINEAR).
  * Write `baseColorTexture` with `texCoord: 0`, keeping `baseColorFactor` and COLOR_0.
  * Without textures the output is byte-identical to today.
* `core/glb.py` validator. Each of the following is an error:

  | Area | Error condition |
  |---|---|
  | Image source | any URI; not embedded in BIN |
  | Image format | MIME type other than `image/png`; PNG signature or IHDR mismatch |
  | Image size | a side that is not a power of two, or > 1024; total image bytes > `MAX_TEXTURE_BYTES` (4 MiB) |
  | Image bufferView | out of range, or pointing outside the BIN chunk |
  | Texture | `textures[i].source` out of range; `textures[i].sampler` out of range |
  | Material | `baseColorTexture.index` out of range; `texCoord` ≠ 0 |
  | UVs | a textured primitive **missing `TEXCOORD_0`**; `TEXCOORD_0` count ≠ POSITION count; non-finite UVs |
  | Extensions | anything in `extensionsRequired` |

  A schema-version check accepts 2.0.x and 2.1.x. The package `schema_version` parameter of
  the writer defaults to the existing constant.
* C# `examples/csharp/MbmapReader`: the same checks; accepts 2.0 and 2.1; rejects an unknown
  major. Add a `--validate-many <dir>` mode that validates every `.mbmap` in a directory and
  prints one verdict line per file, so the tests can batch.
* `docs/PACKAGE_FORMAT.md`: 2.1.0 changelog. Textures are optional, and readers that ignore
  them still render factor × vertex colour. Update the materials checklist in
  `docs/UNITY_CORE_HANDOFF.md`.

## Acceptance criteria

1. **Round trip.** A 2-triangle mesh with UVs and a 4×4 PNG round-trips. The validator accepts
   it. The parsed JSON has the expected image, texture, sampler, `TEXCOORD_0` and material
   binding: the primitive's material → texture → image, the bytes have the PNG's SHA-256, and
   the untextured primitive has no `TEXCOORD_0`.
2. **Negative tests.** Each row of the validator table has one negative fixture failing with a
   named error, in both Python and C#. The fixtures are shared bytes generated once per class.
3. **C# budget.** C# is built once per test class (`setUpClass`, as `test_csharp_parity`), and
   all negative fixtures are validated in **one** `--validate-many` call. The class's test
   methods are each ≤ 5 s. The one-off `dotnet build` is reported separately, as for the
   existing parity class.
4. **Frozen v0.3.0 reader.** The v0.3.0 C# reader (sources from `git archive v0.3.0
   examples/csharp`) loads a textured 2.1.0 package. Expected: accepted (minor version), with
   textures ignored and the collision verdicts unchanged. This runs in the C# CI job
   (`actions/checkout` with `fetch-depth: 0` so the tag resolves; +~20 s) and is reported in
   the PR.
5. **glTFast smoke import.** Import the textured package's GLB with **glTFast at the version
   pinned by the simulator** (record the version and its source in the PR). Show that it
   imports without errors and the texture is bound, in an Editor scratch project outside
   drone-flight-simulator, with a screenshot.
   * If no Unity Editor is available, report that. The coordinator then decides whether the
     pinned Khronos glTF-Validator plus the three.js viewer is accepted as a proxy. The
     release notes must disclose it.
6. The C# reader loads the Pittsburgh v0.3.0 package (2.0.0) unchanged (real data, D47-style).

## Performance considerations

The writer is O(images + UV floats). The validator checks PNG headers only, with no decode.
New Python tests ≤ 5 s; C# as in AC3. PR CI stays ≤ 10 min (expected ≈ +20 s for AC4).

## Conflict domain

Hard: `core/glb.py`, `core/mesh.py`, `examples/csharp/MbmapReader/**`, `docs/PACKAGE_FORMAT.md`,
`tests/test_package.py`, `tests/test_csharp_parity.py` (new class), `.github/workflows/ci.yml`
(C# job only). Soft: `docs/UNITY_CORE_HANDOFF.md`. Not `core/__init__.py` and not the sample
(D64).
