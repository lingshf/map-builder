# S4-EXT-READY: Blender Extensions platform readiness (no submission)

Owner: dev · sprint S4 · any lane · D13, D100

## Background (measured on f8bedf6, Blender 4.2.23)

* `blender --command extension validate map_builder` passes. `release.yml` already runs it.
* Two `extension build` runs from the same tree give identical zips (892,653 B, SHA-256 `6AE6A63D…`). After the
  file mtimes are changed, the SHA-256 changes (`B9966F9D…`). A build from a fresh clone of the tag is
  therefore not reproducible.
* The manifest has no `website`, and `maintainer` is "map-builder contributors" with no contact. The tagline is
  58 characters, the licence is `SPDX:GPL-3.0-or-later`, and permissions `network` and `files` have reasons.
* The zip has 45 entries: `core/` 25, `blender/` 8, `assets/` 7, top-level 5.

## Scope

1. In `release.yml`, set every source file's mtime to the tag commit time before `extension build` (D100).
2. Add a cheap PR-CI unit test of the manifest against the platform rules this repo can check without Blender:
   * tagline ≤ 64 characters, with no trailing punctuation;
   * `id`, `version` and `schema_version` formats;
   * the licence is an SPDX list containing a GPL-compatible add-on licence;
   * each permission has a reason of 1 to 64 characters with no trailing period;
   * `blender_version_min` = 4.2.0;
   * `website` present once the user provides it, with a `TODO(user)` test skip until then;
   * the build excludes `__pycache__` and `*.pyc`;
   * no binaries in the zip.
3. Write `docs/PLATFORM_SUBMISSION.md`. It is a checklist of each platform requirement with its status
   (done, or user action) and the exact commands. The user-owned fields are the maintainer contact, the
   website, the screenshots and the submission itself.

## Acceptance criteria

1. Two clean builds from two fresh clones of the same commit, with mtimes normalised as in `release.yml`, are
   byte-identical. Recorded in the PR; the workflow step is shown in a dry run on a fork or a test tag.
2. The manifest test passes in PR CI; its duration is measured and quoted (expected ≤ 1 s), not asserted.
3. `extension validate` passes (recorded).
4. The checklist names every user action; no personal data is invented (D100).
5. `ExtensionZipTest` (texture set and licence texts in the zip) still passes on the built zip.

## Performance considerations

None on the product path. Release workflow time grows by under 5 s.

## Expected tests

`tests/test_manifest.py` (new, ≤ 1 s).

## Conflict domain

Hard: `.github/workflows/release.yml`, `tests/test_manifest.py` (new), `docs/PLATFORM_SUBMISSION.md` (new),
`map_builder/blender_manifest.toml` (non-version fields only). Serialised before REL-v0.5.0, which bumps the
version.
