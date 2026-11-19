# Releases

Releases are cut at sprint end (decision D17) as GitHub **pre-releases** carrying the installable
Blender extension zip.

## Procedure

1. Bump `version` in `map_builder/blender_manifest.toml` (e.g. `0.1.0`).
2. Write `docs/releases/vX.Y.Z.md` (what is new, known limits, "How to try it").
3. Merge to `main`.
4. Tag that commit and push: `git tag vX.Y.Z && git push origin vX.Y.Z`.
5. The `Release` workflow (`.github/workflows/release.yml`) validates and builds the extension,
   fails if the manifest version differs from the tag, then creates the pre-release (notes from
   `docs/releases/vX.Y.Z.md`, or generated notes if missing). Re-running on an existing tag
   replaces the zip asset.
6. The sprint-review task attaches the sample package, GLB, screenshots and viewer zip with
   `gh release upload vX.Y.Z <files> --clobber`.

## Dry run

Run the workflow manually (**Actions › Release › Run workflow**) on any branch: it builds the
zip and uploads it as the `map_builder-extension` workflow artifact without creating a release.

## Trying a release

Download `map_builder-X.Y.Z.zip`, then in Blender 4.2 LTS: **Edit › Preferences › Get Extensions ›
⌄ › Install from Disk…**. The panel is in **3D Viewport › Sidebar (N) › Map Builder**.
