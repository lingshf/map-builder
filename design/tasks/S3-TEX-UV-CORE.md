# S3-TEX-UV-CORE: UV assignment and textured CLI export

Owner: dev · sprint S3 · wave 2 · depends on S3-TEX-FORMAT, S3-TEX-ASSETS · D59, D60

## Goal

CLI packages get world-scaled UVs and textured materials. UVs are assigned **after**
generation, in a new module `core/uv.py`, so `generate.py` and `roofs.py` (where the roof track
is active) are not edited.

## Scope

* `core/uv.py`: `assign_uvs(mesh, policy_by_material)` fills `face_uvs` using the tile size in
  metres from `core/textures.py`. The policies are:

  | Material | Projection |
  |---|---|
  | `MB Facade` | U = distance along the face's horizontal tangent, V = z − face base z (window rows line up) |
  | `MB Roof` | planar projection onto the face plane, U along the slope's horizontal edge (tiles follow the slope) |
  | `MB Terrain`, `MB Road` | world XY |
  | `MB Concrete`, `MB Tunnel` | box projection by dominant normal |
  | Other materials | no texture; UVs are omitted unless the mesh has a textured material |

  All UVs are finite, with offsets reduced modulo the tile size per face so that float32
  precision holds on 2 km maps.
* Pipeline: call `assign_uvs` in the export path before `write_glb`. Materials gain a
  `baseColorTexture` with the factor set to white × the existing tint (keep COLOR_0).
* CLI: `--textures/--no-textures`, default **on** (D60). Provenance/metadata records
  `textures: true|false` and the texture SHA-256 list.

## Acceptance criteria

1. Unit tests, one per policy, use a fixed quad and check the expected UVs:
   * the facade V of a 6 m wall spans 0–6 m in tile units;
   * the roof U runs along the eave;
   * road and terrain UVs = XY / tile size;
   * UVs at x = 2000 m stay within ±1 tile after reduction.
2. The synthetic sample is built with textures and is VALID with `--strict`. With
   `--no-textures` the GLB equals the pre-S3 output (S3-TEX-FORMAT AC3).
3. Real data: Pittsburgh built with textures is strictly VALID in Python, and the C# reader
   loads it. Record the GLB size before and after: target ≤ +35 % plus the fixed texture bytes
   (D60).
4. Any "MB Probe" geometry stays untextured.

## Performance considerations

UV assignment is O(face corners), measured as its own stage. Budget: ≤ +20 % of the fixture
build (D35), with the median of 3 runs reported. Textures add a fixed ≤ 2 MiB to each GLB.
New tests ≤ 5 s.

## Conflict domain

Hard: `core/uv.py` (new), `tests/test_uv.py` (new), `core/pipeline.py` (export call site),
`tools/mbmap_cli.py` and CLI argument parsing, `examples/synthetic_sample.mbmap`. Soft: `docs/VALIDATION.md`, README CLI
section.
