# REL-v0.1.0: first full release (everything on main)

Owner: release manager · depends on #11 merged, S1-RELEASE-WF (#13, done) · decision D29
(supersedes the "tag + zip only" baseline of D17) · follows [SPRINT_CLOSE.md](SPRINT_CLOSE.md)

## Scope

A full first release of what main already does: v1 (terrain + OSM → editable scene, GLB +
`.mbmap` export, validator), package format 2.0 (#10), DSM terrain correction (#11) and the
release workflow (#13). Version stays `0.1.0`.

* RC PR with `CHANGELOG.md` (initial entry), `docs/user/` (install, generate, export,
  validate, DSM option, limits), `docs/flows/`, `docs/releases/v0.1.0.md`.
* Demo `docs/demo/v0.1.0/`: if S1-DEMOKIT is merged, run it on the `synthetic` preset and the
  D26 Pittsburgh preset (records the "before" images for v0.2.0: bridges/tunnel omitted and
  listed as unsupported); otherwise use the existing `examples/` sample with a small set of
  manually rendered images and note that later releases use the demo kit.
* Examples: (1) synthetic sample from the committed fixtures, (2) a real-data area, (3) DSM
  correction on/off on the same area.

## Acceptance criteria

The common release criteria in SPRINT_CLOSE.md; the Pittsburgh `cameras` used are stored with
the preset so v0.2.0 reuses them.

## Performance considerations

No code change; demo rendering within the common budget.

## Conflict domain

Hard: `CHANGELOG.md`, `docs/user/`, `docs/flows/`, `docs/demo/v0.1.0/`,
`docs/releases/v0.1.0.md`. Soft: README. Runs alone (no product code merges between RC and tag).
