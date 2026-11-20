# Changelog

All notable user-visible changes are recorded here, following
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Extension versions use
[Semantic Versioning](https://semver.org/); package schema versions are independent.

## [Unreleased]

## [0.2.0] - 2026-11-20

"Fly under bridges and through tunnels." **Release candidate**, not a published
release: tagging requires release review and coordinator authorization.
Package schema stays **2.0.0**.

### Added

- Highway bridges (`highway=*` + `bridge=*`) are generated as editable deck
  solids (class `bridge`) whose height follows OSM `layer` (5 m clearance per
  layer, ramps of 8 % or less). They carry `deck` and, where clearance is at
  least 4 m, `under` passage probes (#21).
- Bridge piers where a deck stands more than 6 m above the ground, kept off
  roads beneath, and 1 m parapets on wide enough decks (#26).
- Road tunnels (`highway=*` + `tunnel=*`) as flyable tubes with an arched
  roof, an exact terrain cut that does not leak, portal headwalls (class
  `structure`), matching heightfield NaN cells and a `bore` passage probe (#22).
- Elevated building parts get an `under` probe. `tunnel=building_passage` /
  `covered=yes` highways split their building into lower parts and an upper
  part with a flyable `passage` probe (#24).
- The generator re-checks every probe against the finished scene. Blocked
  probes are not exported; they are listed in `report.json`
  `passage_probes_blocked` with the blocking `mb_id` (#21, #22, #24).
- Pittsburgh demo preset with fixed cameras; fast tests without wall-clock
  gates (#23).
- User guide [bridges, tunnels and passages](docs/user/structures.md),
  [fly-through check flow](docs/flows/flythrough.md), and a
  [Pittsburgh v0.2.0 demo](docs/demo/v0.2.0/README.md) that compares
  before/after renders from the unchanged v0.1.0 cameras (REL-v0.2.0).

### Changed

- The C# reference reader now counts probe query work the same way as the
  Python validator, so it checks all 13 Pittsburgh probes within its budget.
  Both validators accept tunnel headwall ids (`osm:way/N:headwall0`,
  `osm:way/N:headwall1`) without a warning (#27, D46).

### Not included

- PERF-PROBE-INDEX (#25) was closed without merging. Probe checking performance
  is unchanged.
- Railway bridges/tunnels (including funiculars), culverts, `man_made=bridge`
  outlines and `man_made=tunnel` remain unsupported and reported (D25).

## [0.1.0] - 2026-11-19

Baseline **preview candidate**, not a published release. Final tagging requires
release review and coordinator authorization.

### Added

- Blender 4.2 LTS extension with a Map Builder sidebar: choose an area, load
  Copernicus GLO-30 or a local DEM, and load Overpass or local OSM features (#1, #2, #5).
- Editable terrain, buildings with basic roof shapes and courtyards, draped roads,
  water and procedural vegetation; reports distinguish inferred and unsupported
  content (#3, #5).
- Additional OSM roofs: half-hipped, gambrel, mansard, round and saltbox on
  rectangular footprints; dome and onion on convex footprints.
  `roof:orientation` and `roof:direction` are honored, with reported
  inferred/fallback provenance for unsupported or ill-fitting shapes (#18).
- Export final evaluated Blender meshes, including modifiers, transforms, mirrors,
  duplicates and user geometry, into GLB visuals and authoritative collision in an
  atomic `.mbmap` package. Include optional terrain heightfield, georeference,
  hashes, attribution and orientation probes (#4, #5).
- Headless CLI build/validate, a synthetic sample and a C# reference reader for
  consumer integration. Simulator loading and flight collision remain
  **consumer-side preview work**, not a delivered simulator feature (#4, #7).
- Package schema **2.0.0**, collision header v2, bridge/tunnel/structure classes and
  passage-probe validation. These are format capabilities, not generated flyable
  bridges or tunnels; schema 1.x packages must be regenerated (#10).
- Tag-triggered extension packaging and GitHub pre-release publication. Manual
  workflow runs build an artifact only (#13).
- Reusable demo kit with Cycles CPU renders, a bundled three.js viewer, probe
  results and real Blender-sidebar capture using a separate Mesa runtime (#14).
- End-user installation, generation, export and simulator-handoff guides, UI flow
  diagrams, synthetic editing demo and real Pittsburgh DSM Off/On comparison
  with reproducible renders and reusable cameras (REL-v0.1.0).

### Changed

- Copernicus maps now enable inferred DSM terrain correction by default: lower
  ground under OSM-mapped buildings, trees, forests and bridge decks toward
  surrounding ground, never raise it. Buildings and vegetation are placed on
  the corrected terrain, reducing rooftop/canopy-height "plinths" (#11).
- Blender's **DSM correction** control offers Auto / On / Off; CLI flags are
  `--dsm-correction` / `--no-dsm-correction`. Auto leaves local elevation files
  unchanged. Online Overpass acquisition with correction enabled adds a
  mask-only request, increasing cold-cache generation time (#11).
- Generation reports record whether correction ran, lowered sample counts,
  lowering amounts and skip reasons. Applied processing is attributed in
  package NOTICES; source hashes and package schema 2.0.0 stay unchanged (#11).
- If mask acquisition fails, correction budgets are exceeded, fewer than 5% of
  samples remain unmasked, or the fill does not converge, generation warns and
  uses the original surface model. Required source-data failures still stop
  generation; no flat or fabricated terrain is substituted (#11).
- The committed synthetic sample's way/1043 now has a dome rather than a flat
  fallback; its identity changed and collision count increased to 4987
  triangles (#18).
- Internal structure routing and stage hooks prepare later feature work without
  changing generated output or reports. **Bridges and tunnels remain unsupported
  and omitted**; this is not a new flyable-structure feature (#19).

### Fixed

- Reject oversized terrain/heightfield requests before network or file access (#6).
- Reject impossible calendar dates in `created_utc` in both reference readers (#8).
- Recognize split OSM part identities such as `osm:way/123#1` during validation (#9).
- Real-terrain road exports no longer fail upward-normal validation because of
  slivers below float32 storage resolution. Only unrepresentable, failing faces
  are omitted and reported as `slivers_dropped` provenance; wider folded faces
  still reject the road. Pittsburgh drops one 0.000012 m-wide face per DSM
  mode; validator rules and the synthetic sample are unchanged (#20).

### Known limitations

- Bridges and tunnels are reported unsupported; elevated buildings are closed
  solids, not flyable passages. No interiors, streaming or LOD.
- Visuals are procedural, flat-shaded and untextured; no performance guarantee.
- Online acquisition is not exercised by CI. The Pittsburgh demo uses a recorded
  online acquisition; provider availability and live-data changes still apply.
- DSM correction is an approximation, not a bare-earth DTM: hidden relief is
  smoothed, edge-touching fills level off, and unmapped buildings/trees are not
  corrected.
- Code licence is provisionally GPL-3.0-or-later; owner confirmation and a root
  licence file are still outstanding. Source-data licences apply separately.

[Unreleased]: https://github.com/lingshf/map-builder/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/lingshf/map-builder/releases/tag/v0.2.0
[0.1.0]: https://github.com/lingshf/map-builder/releases/tag/v0.1.0
