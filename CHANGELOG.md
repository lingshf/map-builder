# Changelog

All notable user-visible changes are recorded here, following
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Extension versions use
[Semantic Versioning](https://semver.org/); package schema versions are independent.

## [Unreleased]

## [0.3.0] - 2026-11-20

"Passages, roofs and the real-data v2 demo" (end of v2). **Release
candidate**: tagging requires release review and coordinator authorization.
Package schema stays **2.0.0**.

### Added

- Munich Altstadt demo preset (48.1395 N, 11.5764 E, 400 x 400 m). It is the
  second real-data area: a real elevated building part, a real building
  passage, a road tunnel and tagged OSM roofs, with fixed cameras `overview`,
  `elevated-under`, `passage` and `roofs` (#36, D49 outcome A).
- Headless Blender roof checks (`tests/blender/checks_roofs.py`). They check
  ridge, rise and wall/roof attachment for the supported shapes (#34).
- [v0.3.0 demo](docs/demo/v0.3.0/README.md) and [docs/DEMO.md](docs/DEMO.md):
  reproduce steps, numbers and attribution for both real-data presets.
- The release attaches both real-data packages (`munich-altstadt-0.3.0.mbmap`,
  `pittsburgh-0.3.0.mbmap`, GLB inside, ODbL attribution in `NOTICES.txt`)
  next to the extension zip (S2-F4).

### Fixed

- Blender export no longer fails validation with "road object ... normal does
  not point up" on steep terrain (seen in Pittsburgh). Blender stores a road's
  vertices and location as separate float32 values, and that double rounding
  could turn a needle-thin road face over even though the single-rounding
  check judged it fine. Generation now drops such faces (narrower than a few
  float32 ulps) for both storage paths and records them in the road's
  `slivers_dropped` provenance. In the tested CLI builds (the Pittsburgh and
  Munich release packages, rebuilt from the same cached data) the output is
  byte-identical to before the fix (S2-F6, #37).

### Changed

- An unsplit bridge approach no longer raises a false clearance warning. On
  the ramp ends (where the straight deck line is still below clearance height
  over the terrain), a crossing is exempt only if the road surface lies within
  0.3 m of the nominal deck top, above or below (a two-sided surface gap); no
  shared OSM node is needed. Roads further above or below are still measured
  on the exported geometry and still warn (#32).
- Packages now report `generator.version` **0.3.0**, and a unit test keeps it
  equal to the add-on version (D50). v0.1.0 and v0.2.0 packages report
  `generator.version` 0.1.0, a known historical mislabel. Because the
  manifest changes, every `package_id` changes from v0.3.0 on, even where the
  geometry is byte-identical to v0.2.0 (verified for the Pittsburgh and Munich
  builds in the v0.3.0 evidence). The committed
  `examples/synthetic_sample.mbmap` was regenerated
  (`sha256:2b560d04…`).
- Tests no longer depend on wall-clock speed: the TLS deadline test is
  deterministic, and the terrain-source tests have no timing gates (#31, #35).

### Known limitations

- Of 67 tagged non-flat roofs in the Munich area, only 5 are built as tagged
  (4 gabled, 1 skillion). The other 62 fall back (53 flat, 9 pyramidal),
  mostly gabled or hipped roofs on non-rectangular footprints (S2-F5, later).
- `tests/test_csharp_parity.py` builds the C# reader with `dotnet build`. If
  two test suites run in parallel, the builds can race on the output files
  (`CS2012`); run the suites one at a time.
- Some local tests take several seconds (L5). This is measured only; there is no gate.
- Degenerate (zero-area) collision triangles are a validation warning: 76 in
  Pittsburgh and 59 in Munich (L1).

## [0.2.0] - 2026-11-20

"Fly under bridges and through tunnels." Published as a GitHub
**pre-release**. Package schema stays **2.0.0**.

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
  `passage_probes_blocked` with the blocking `mb_id` (#21, #22, #24). At
  export, edits are not re-probed: a probe that an edit blocks, or that is not
  checked within the query budget, is a validation **warning**, and the
  package is still `VALID` ([check a package](docs/user/structures.md#check-a-package)).
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

[Unreleased]: https://github.com/lingshf/map-builder/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/lingshf/map-builder/releases/tag/v0.3.0
[0.2.0]: https://github.com/lingshf/map-builder/releases/tag/v0.2.0
[0.1.0]: https://github.com/lingshf/map-builder/releases/tag/v0.1.0
