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

**Owner of every `core/package.py` edit in S3 (D65).** S3-TEX-UV-CORE and S3-TEX-BLENDER only
call the API added here; they do not edit `package.py`. Sequence: this task first, then UV-CORE
flips the constant.

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
* `core/package.py` (D65), in this order:
  1. **Schema-version writing:** the package writer takes `schema_version=` (default
     `PACKAGE_SCHEMA_VERSION`) and writes it into `manifest.schema_version`. The validator
     keeps today's rule: major 2 is accepted, any minor.
  2. **Asset notices:** a new optional top-level manifest field, `asset_notices`. It is an array
     of `{name, attribution, license{id,name,url,text}, sha256[]}`. `sources[]` is **not**
     changed and keeps `kind` ∈ {elevation, features}, because the v0.3.0 Python and C#
     readers reject any other kind. Both legacy readers ignore unknown top-level manifest
     fields (PACKAGE_FORMAT §versioning; neither enumerates manifest keys).
  3. `notices_text(sources, asset_notices=())` appends an "Assets" section with each entry's
     name, attribution and licence id, name, URL and text, verbatim. A legacy reader only
     checks that the `sources[]` notices are present, so the extra section is harmless.
  4. 2.1 validator rules:
     * every `asset_notices` entry's attribution and licence keys appear verbatim in
       `NOTICES.txt`;
     * if `visual/map.glb` has images, each image's SHA-256 is listed in some
       `asset_notices[].sha256`. Otherwise it is an error ("texture without provenance");
     * an `asset_notices` entry whose SHA-256 is not in the GLB gets a warning.
* C# `examples/csharp/MbmapReader`: the same `asset_notices` rules, plus: the same checks; accepts 2.0 and 2.1; rejects an unknown
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
4. **Frozen v0.3.0 readers on a full package.** A test helper, `tests/make_textured_fixture.py`,
   writes a **complete** textured 2.1.0 `.mbmap`. It uses the synthetic input, one 4×4 test
   texture with its `asset_notices` entry, and the normal package writer, so the manifest,
   `.mbcol`, heightfield, NOTICES and report are all real. The C# CI job then:
   * extracts the v0.3.0 Python package and the C# reader with `git archive v0.3.0 map_builder
     tools examples/csharp` (`actions/checkout` with `fetch-depth: 0`);
   * runs the **v0.3.0** `tools/mbmap_cli.py validate` and the **v0.3.0** C# reader on **that
     exact `.mbmap` file**;
   * runs both on `examples/synthetic_sample.mbmap`. This is the untextured 2.0.0 sample here;
     after UV-CORE it is the shipped textured 2.1.0 sample, and the step is unchanged.

   Expected: both accept with 0 errors and 0 warnings (C# treats warnings as errors), the
   collision verdicts are unchanged, and the textures are ignored. The step adds about +25 s.
   Evidence goes in the PR.
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

Hard: `core/glb.py`, `core/mesh.py`, `core/package.py` (schema-version writing, `asset_notices`,
notices; sole S3 owner, D65), `tests/make_textured_fixture.py` (new), `examples/csharp/MbmapReader/**`, `docs/PACKAGE_FORMAT.md`,
`tests/test_package.py`, `tests/test_csharp_parity.py` (new class), `.github/workflows/ci.yml`
(C# job only). Soft: `docs/UNITY_CORE_HANDOFF.md`. Not `core/__init__.py` and not the sample
(D64).
