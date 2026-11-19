# Project brief: map-builder

## Purpose
Generate an editable, georeferenced map of about 1 × 1 km from real terrain and OpenStreetMap,
let a human edit it in Blender, and export a validated, engine-neutral `.mbmap` package: GLB
visuals plus authoritative platform-neutral collision.

## Users
* Map authors using Blender 4.2 LTS+.
* Game/simulator developers consuming `.mbmap`. The first consumer is
  lingshf/drone-flight-simulator: Unity 6 LTS + URP for presentation, and a netstandard2.1
  Core (250 Hz) as the physics authority.

## Stack
* Python 3.11+, stdlib only, in the core and CLI.
* A Blender 4.2 LTS extension (`map_builder/blender_manifest.toml`).
* GitHub Actions CI.
* A C# reference reader (net8.0 project with netstandard2.1-compatible code).

## Architecture
* `map_builder/core/` (pure Python, no bpy):
  * `geodesy`: map frame and axes;
  * `http` and `cache`: bounded downloads, URL redaction, a public-only cache;
  * `dem` and `tiff`: Copernicus GLO-30 and local GeoTIFF/ASCII;
  * `osm`: Overpass or `.osm`, plus classification;
  * `generate` and `triangulate`: the scene plan;
  * `glb`: GLB write/read;
  * `collision`: `.mbcol`/`.mbhf`;
  * `package`: manifest, atomic write, validator, probes;
  * `pipeline`: glue.
* `map_builder/blender/`:
  * `props` and `ui`: the panel, in View3D › Sidebar › Map Builder;
  * `operators`: Generate, Export, Validate;
  * `sources`: credential policy and settings;
  * `scene_build`: plan to Blender objects;
  * `bake` and `export`: evaluated meshes to the package.
* `tools/mbmap_cli.py`: a headless build and validate.
* `docs/`:
  * `PACKAGE_FORMAT.md`: the contract;
  * `VALIDATION.md`: coverage and gaps;
  * `UNITY_CORE_HANDOFF.md`: the consumer guide.
* `examples/`:
  * the synthetic sample `.mbmap`;
  * `csharp/MbmapReader`.

## Commands
```powershell
py -3.12 -W error::ResourceWarning -m unittest discover -s tests -t .
py -3.12 tools\mbmap_cli.py validate examples\synthetic_sample.mbmap
blender --command extension build --source-dir map_builder --output-dir dist
& $blender --background --factory-startup --python tests\blender\run_integration.py -- "$env:TEMP\mb_it"
dotnet run -c Release --project examples\csharp\MbmapReader -- examples\synthetic_sample.mbmap
```
The sample regeneration command is in `examples/README.md`.

## Key decisions
* **An independent Blender add-on**, not part of the simulator. Its output is a neutral package.
* **Collision is authoritative and platform-neutral** (`.mbcol` triangles plus an optional
  `.mbhf`). It is bound one-to-one by name to the GLB nodes. Visuals are presentation only, and
  visual LOD must not change collision.
* **The GLB is baked from the evaluated triangles by core `write_glb`**, not by Blender's glTF
  exporter, so the visuals and collision are exactly the same triangles. The trade-off is flat
  shading with no UVs or textures in v1.
* **v1 buildings are closed, outward-facing, positive-volume shell sets** with no cavities.
  Under-bridge, tunnel and elevated flying are unsupported, and are reported in `report.json`.
* **Package format 2.0.0** adds the `bridge`/`tunnel`/`structure` classes with per-kind
  winding rules (solid, surface, inward tube), two-sided triangles for queries, `.mbcol` v2 and
  validator-checked `passage_probes`. 1.x packages are rejected. Generators do not emit the new
  classes yet.
* **Credential policy:**
  * there is no free-text endpoint;
  * a private Overpass URL comes only from `MAP_BUILDER_OVERPASS_URL` at Generate time;
  * URLs are reduced to their origin;
  * text fields are scrubbed;
  * the validator enforces the policy on every JSON surface.
* **No silent flat-ground substitution.** An elevation failure stops Generate.
* **DSM terrain correction** (`Settings.dsm_correction`; default auto = on for Copernicus, off
  for local files) lowers DEM points under OSM buildings (+15 m), trees (6 m), forest/wood and
  bridge ways (width/2 + 15 m) by a harmonic (Laplace) fill solved by multigrid (reproduces
  planes, bounded by the surrounding ground, linear work), `min(original, filled)`; it is
  skipped below 5 % unmasked points. It is a derived step: raw elevation provenance and hashes are
  unchanged; the outcome is in `report.json` `terrain_correction`, the terrain `surface` is
  `inferred:`, and the elevation source gets a `processing` note. Approximation, not a DTM.
* **Identity:** `package_id = sha256(raw manifest bytes)`, valid only after the files[] hashes
  are verified. Replays bind to it.
* **Licensing:**
  * OSM ODbL attribution (Produced Work; game code need not be open source);
  * Copernicus attribution;
  * no Google content;
  * the add-on is GPL-3.0-or-later, **assumed and pending owner confirmation** (there is no
    LICENSE file).

## Workflow
* One feature branch and one PR per change.
* CI must pass: Python 3.11 and 3.12 unit tests, plus a CLI build and validate.
* Code review by a different model family (gpt-6.2-sol), with a summary comment on the PR.
* Squash merge, then delete the branch.
* Headless Blender runs are manual and recorded in VALIDATION.md.

## PR history
1. #1: package contract, geodesy, CI
2. #2: terrain and OSM ingestion
3. #3: scene generation
4. #4: GLB export, package and collision
5. #5: Blender edit support
6. #6: validation
7. #7: consumer handoff docs, the C# reference reader, a reproducible synthetic sample and
   `--created-utc` (this branch: `feature/handoff-docs`)

## Open items
* Consumer work in Unity and Core: a triangle collider or BVH in Core, the loader,
  probe-checked glTF import, and replay binding. See the checklist in UNITY_CORE_HANDOFF.md.
* Confirm the add-on licence and add a LICENSE file.
* A live check of Copernicus and Overpass, including the online Blender path. Neither runs in CI.
* Optional: a texture/UV visual path.
