# Changelog

All notable user-visible changes are recorded here, following
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Extension versions use
[Semantic Versioning](https://semver.org/); package schema versions are independent.

## [Unreleased]

### Planned

- DSM terrain correction is awaiting merge of [#11](https://github.com/lingshf/map-builder/pull/11).
  It is **not included in this release candidate**. Move its verified changes into
  0.1.0 before approving the baseline release.

## [0.1.0] - 2026-11-19

Baseline **preview candidate**, not a published release. Final tagging requires
DSM correction (#11), release review and coordinator authorization.

### Added

- Blender 4.2 LTS extension with a Map Builder sidebar: choose an area, load
  Copernicus GLO-30 or a local DEM, and load Overpass or local OSM features (#1, #2, #5).
- Editable terrain, buildings with basic roof shapes and courtyards, draped roads,
  water and procedural vegetation; reports distinguish inferred and unsupported
  content (#3, #5).
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
  diagrams and an offline synthetic demo with reproducible renders (REL-v0.1.0).

### Fixed

- Reject oversized terrain/heightfield requests before network or file access (#6).
- Reject impossible calendar dates in `created_utc` in both reference readers (#8).
- Recognize split OSM part identities such as `osm:way/123#1` during validation (#9).

### Known limitations

- Bridges and tunnels are reported unsupported; elevated buildings are closed
  solids, not flyable passages. No interiors, streaming or LOD.
- Visuals are procedural, flat-shaded and untextured; no performance guarantee.
- Online acquisition is not exercised by CI or the offline release demo.
- Code licence is provisionally GPL-3.0-or-later; owner confirmation and a root
  licence file are still outstanding. Source-data licences apply separately.

[Unreleased]: https://github.com/lingshf/map-builder/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/lingshf/map-builder/releases/tag/v0.1.0
