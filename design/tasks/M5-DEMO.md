# M5-DEMO: real-data re-demo with bridges and tunnels

Milestone M5 · depends on M3-R, M4-R and the user's choice of area (D25)

## Goal

Show v2 on real data: an area with bridges and a tunnel, built from live Copernicus GLO-30 and
Overpass, with renders and a three.js viewer, and record the results.

## Scope

* Area: D25 (proposed Pittsburgh, Fort Pitt Bridge + Tunnel, ≈ 40.437 N, 80.016 W,
  1200 × 1000 m; final choice by the user).
* Build with the CLI (online sources through the add-on or a downloaded `.osm` + DEM tile; the
  download is not part of the timing) and validate.
* Headless Blender: generate the same area, export, validate, render 4 views: overview,
  under a bridge, into a tunnel portal, through an elevated part/passage if present.
* three.js viewer: load `visual/map.glb`, draw `passage_probes` as capsules (green PASS /
  red blocked) and collision class colours. Served on a **new** port (not 8765, which is in
  use); artefacts outside the repo (session files). Only a short `docs/DEMO.md` (how to
  reproduce, numbers, attribution) is committed.
* Bump generator version to 0.2.0 (`map_builder/__init__.py`, `blender_manifest.toml`).

## Acceptance criteria

1. Package `VALID`; ≥ 1 bridge, ≥ 1 tunnel generated; every emitted probe PASSes in the
   validator and in the C# reader; `passage_probes_blocked` entries (if any) explained in DEMO.md.
2. Build time (excluding download) ≤ 120 s; triangle count, object count, probe-check visits
   and peak memory (if measurable) recorded in DEMO.md and VALIDATION.md.
3. Renders show the drone-eye views listed above; the viewer runs locally and is reported with
   its URL.
4. NOTICES/attribution for OSM and Copernicus shown in DEMO.md and the viewer.
5. Online paths exercised for real once; result recorded in VALIDATION.md "Not validated"
   (moved to validated for this run).

## Performance considerations

This is the end-to-end performance check for v2 (roadmap targets). If the 120 s target is
missed, record the profile (top functions) and open a follow-up task rather than optimising in
this task.

## Expected tests

No new unit tests; the validator, C# reader and headless Blender run on the demo package are
the evidence.

## Conflict domain

Hard: `docs/DEMO.md` (new), `map_builder/__init__.py`, `map_builder/blender_manifest.toml`.
Soft: `docs/VALIDATION.md`, `README.md`. Runs alone.
