# CLI and demo presets

The CLI needs Python 3.11 or newer and local OSM XML and elevation files; it
does not acquire online data or export Blender edits. Use the panel for online
sources and edited scenes. Run from the repository root in PowerShell.

## Offline build

This command was verified on Python 3.12 using the committed synthetic fixtures.
They are invented data, not OpenStreetMap or a real place. The command overwrites
the named output if it already exists.

```powershell
$out = Join-Path $env:TEMP 'map-builder-doc-audit.mbmap'
py -3.12 tools\mbmap_cli.py build --osm tests\fixtures\synthetic_area.osm --dem tests\fixtures\synthetic_dem.asc --datum SYNTHETIC --dem-license 'SYNTHETIC test data (no licence required)' --osm-license 'SYNTHETIC test fixture (hand-written OSM-format XML, not OpenStreetMap data; no licence required)' --lat 47.0 --lon 8.0 --width 400 --height 300 --created-utc 2026-01-01T00:00:00Z --name synthetic_sample --out $out
py -3.12 tools\mbmap_cli.py validate $out
```

The build and validation print `VALID`; the sample has a warning about two
degenerate collision triangles. For real inputs, declare the actual elevation
datum and licence; omit `--osm-license` for OpenStreetMap data. ASCII grids
default to EPSG:4326; set `--dem-crs` for WGS84 UTM grids. GeoTIFFs carry
their own CRS. `--spacing` controls terrain spacing; `--heightfield 0`
omits the optional heightfield. `--seed` controls procedural scatter.
`--dsm-correction` forces correction for a local DSM; `--no-dsm-correction`
disables it. Auto is off for local elevation.

`--style stylized` (the default since v0.6.0) writes the low-poly stylized
look: a flat-shaded palette with no embedded textures, a smaller GLB and no
CC0 texture notices. `--style classic` gives the v0.5.0 look, where the
texture options below apply. `--textures` is ignored for `stylized`. Geometry,
collision (`.mbcol`), heightfield and passage probes are the same in both
styles; `report.json` records the style in `options.style`.

With `--style classic`, `--textures` (the default) embeds the CC0 facade, roof, road and terrain
textures with world-scaled UVs; `--no-textures` writes a plain-colour GLB of
the same geometry as the textured build (not the v0.3.0 roofs). The collision (`.mbcol`) and
heightfield are byte-identical either way, so a simulator sees the same
physics; the GLB, `manifest.json` (`asset_notices`), `NOTICES.txt` and
therefore the `package_id` differ. Both write package schema
2.1.0, which v0.3.0 readers still accept.

`--created-utc` fixes the manifest timestamp for reproducible builds with the
same inputs on the same platform. Without it, the current time is used. Build
and validate return 0 for valid packages, 1 for invalid validation, and 2 for
caught input or operational errors. Inspect warnings even when validation
returns 0. See [generation and DSM limits](generate.md).

## Demo presets

Presets are for the demo kit's area and camera configuration, not a CLI
`build` option. Bundling the existing sample without rendering was verified:

```powershell
py -3.12 tools\demo\run_demo.py --preset synthetic --after examples\synthetic_sample.mbmap --out "$env:TEMP\map-builder-doc-demo" --bundle-only
```

Available names are `synthetic`, `pittsburgh`, `sf-fidi`, and
`munich-altstadt`; a preset JSON path is also accepted. Bundle-only writes a
viewer and summary; it does not fetch or build a map. For render and
before/after options see the [demo kit](../../tools/demo/README.md).

## Troubleshooting

- **Missing coverage, NoData, invalid CRS or licence:** supply a covering
  elevation grid with a supported CRS and a declared datum and licence. The
  pipeline does not substitute flat terrain.
- **Network disabled or provider failure:** enable Blender online access or
  switch to local files. The CLI itself uses local files only. A failed
  optional DSM mask query instead skips correction with a warning.
- **Invalid export or old output:** read the operator error and system console;
  failed export leaves the previous package in place. The Blender report text
  remains the last successful report after a failure.
- **VALID with warnings:** inspect the warnings and `report.json`. Blocked or
  unchecked passage probes are warnings, not proof a flight path is safe.
- **Missing sidebar:** enable the installed extension and use a 3D Viewport.
  See [installation](install.md) and [export](export.md).
