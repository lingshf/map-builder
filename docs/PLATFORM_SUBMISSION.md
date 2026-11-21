<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- Copyright 2026 lingshf -->
# Blender Extensions platform: submission checklist

Status of Map Builder against the [extensions.blender.org](https://extensions.blender.org) requirements
(S4-EXT-READY; decisions D13, D100). **Nothing has been submitted.** Items marked **user action** need data
or an account that only the maintainer can supply; do not fill them with placeholders.

Commands assume Blender 4.2 LTS (`blender` on `PATH`) and the repo root as the working directory.

## Requirements

| # | Requirement | Status | Check / command |
|---|-------------|--------|-----------------|
| 1 | Manifest validates | done | `blender --command extension validate map_builder` (also run by `release.yml`) |
| 2 | `schema_version`, `id`, `version`, `name`, `type = "add-on"` | done | `python -m unittest tests.test_manifest -v` |
| 3 | `blender_version_min = "4.2.0"` | done | `tests.test_manifest` |
| 4 | Tagline at most 64 characters, no trailing punctuation | done | `tests.test_manifest` |
| 5 | Licence is an SPDX list with a GPL-compatible entry (`SPDX:GPL-3.0-or-later`) | done | `tests.test_manifest`, `tests.test_licence` |
| 6 | Licence texts and NOTICE ship in the zip | done | `tests.test_textures.ExtensionZipTest` |
| 7 | Every permission (`network`, `files`) has a reason of 1 to 64 characters, no trailing period | done | `tests.test_manifest` |
| 8 | No `__pycache__` or `*.pyc` in the zip; no binaries | done | `tests.test_manifest`, run against the built zip with `MB_EXTENSION_ZIP` set |
| 9 | Reproducible zip: file mtimes normalised to the commit time | done | `bash tools/build_extension.sh . dist` (used by `release.yml`; a `workflow_dispatch` run builds twice from a fresh clone and compares SHA-256) |
| 10 | `maintainer` with a contact (name and email) | **user action** | Edit `maintainer` in `map_builder/blender_manifest.toml`, format `"Name <email>"`. Currently `"map-builder contributors"`, which has no contact. |
| 11 | `website` (project homepage or repository URL) | **user action** | Add `website = "https://..."` to the manifest, then remove the `@unittest.skip` (marked `TODO(user)`) from `test_website_present` in `tests/test_manifest.py`. |
| 12 | Screenshots / preview images for the listing | **user action** | Take them in Blender; upload them in the web form at submission time. |
| 13 | Platform account and the submission itself | **user action** | Sign in at extensions.blender.org, then upload the zip (see below). The release version is set by REL-v0.5.0, not here. |

## Build and verify the zip

```sh
bash tools/build_extension.sh . dist
blender --command extension validate map_builder
MB_EXTENSION_ZIP="$(ls dist/*.zip)" python3 -m unittest tests.test_textures.ExtensionZipTest tests.test_manifest -v
sha256sum dist/*.zip
```

Building the same commit twice from fresh clones gives the same SHA-256.

## Submission (user action)

1. Complete items 10 to 12 and commit the manifest change.
2. Build the zip from the release tag with the commands above.
3. Upload it at <https://extensions.blender.org/submit/> and attach the screenshots.
