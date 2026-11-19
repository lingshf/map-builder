# S1-RELEASE-WF: release workflow

Sprint S1 (first task) · no dependencies · decision D17 (two sprints, releases only at sprint end)

## Goal

Pushing a `v*` tag produces a GitHub **pre-release** with the installable Blender extension zip
attached, so every sprint can be tried by installing from disk. PR CI is unchanged.

## Scope

* `.github/workflows/release.yml`, triggers: `push: tags: ['v*']` and `workflow_dispatch`
  (dry run: builds and uploads the zip as a workflow artifact, creates no release).
* Steps: checkout → download Blender 4.2 LTS for Linux x64 from `download.blender.org`
  (pinned version and SHA-256, cached with `actions/cache`) → `blender --command extension
  validate --source-dir map_builder` → `blender --command extension build --source-dir
  map_builder --output-dir dist` → check the manifest `version` equals the tag without `v`
  (fail otherwise) → `gh release create <tag> --prerelease --notes-file
  docs/releases/<tag>.md` (fallback: generated notes) or `gh release upload --clobber` if the
  release exists → attach `dist/*.zip`.
* `permissions: contents: write` only in this workflow; `ci.yml` untouched.
* `docs/releases/README.md`: the release procedure (bump version → write
  `docs/releases/vX.Y.Z.md` → merge → tag → workflow → sprint-review task attaches the sample
  package, GLB, screenshots and viewer zip with `gh release upload`).

## Acceptance criteria

1. `workflow_dispatch` dry run on the branch produces `map_builder-0.1.0.zip` (name as Blender
   builds it) as an artifact; installing it in Blender 4.2.23 with *Install from Disk* shows the
   Map Builder panel (recorded once, manually).
2. A tag whose version differs from `blender_manifest.toml` fails before creating a release.
3. Re-running on an existing tag replaces the zip asset instead of failing.
4. PR CI (`ci.yml`) unchanged; its run time unchanged.
5. No secrets beyond the default `GITHUB_TOKEN`.
6. ~~v0.1.0 baseline~~ superseded by D29: the first release is the full task
   [REL-v0.1.0](REL-v0.1.0.md) owned by the release manager.
7. AC1's panel check is a headless panel-registration assert (D27); the visual screenshot comes
   from S1-DEMOKIT `--panel`.

## Performance considerations

Release job ≤ 5 min (Blender download ≈ 300 MB, cached after the first run). It runs only on
tags and manual dispatch, so it adds nothing to PR CI.

## Expected tests

The dry run itself (link the run in the PR); no unit tests.

## Conflict domain

Hard: `.github/workflows/release.yml` (new), `docs/releases/` (new). Parallel with everything.
