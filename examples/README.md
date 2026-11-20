# Examples

## `synthetic_sample.mbmap`

This is a **synthetic** package. It is built with the CLI from the hand-written fixtures in
[tests/fixtures](../tests/fixtures/README.md), and it is not a real place or real data. It has a
400 × 300 m area, 80 objects, 5237 collision triangles, a 2 m heightfield, 3 orientation
probes and 4 passage probes (one road tunnel bore, way/1072, one on the bridge deck, way/1069, and two beneath the
elevated building part and through the split building passage). It uses
package format 2.1.0 and is **textured** (world-scaled UVs, five CC0 textures embedded in the GLB; build with \--no-textures\ for the untextured GLB). Regenerate it from the repository root:

```powershell
py -3.12 tools\mbmap_cli.py build --osm tests\fixtures\synthetic_area.osm --dem tests\fixtures\synthetic_dem.asc `
    --datum SYNTHETIC --dem-license "SYNTHETIC test data (no licence required)" `
    --osm-license "SYNTHETIC test fixture (hand-written OSM-format XML, not OpenStreetMap data; no licence required)" --lat 47.0 --lon 8.0 `
    --width 400 --height 300 --heightfield 2 --created-utc 2026-01-01T00:00:00Z `
    --name synthetic_sample --out examples\synthetic_sample.mbmap
py -3.12 tools\mbmap_cli.py validate examples\synthetic_sample.mbmap
```

The build is deterministic. With the fixed `--created-utc`, Python 3.12 on Windows x64
(the platform the sample was generated on) reproduces it byte-identically and gives
`package_id = sha256:05d8ad89be7d0fed6882e704080167879a31e48e9649f26ac821ced4ef2cced9`.
Validation reports `VALID: 0 error(s), 1 warning(s)`; the warning is two degenerate
(zero-area) collision triangles, which is allowed. `tests/test_examples.py` checks that the
committed file still validates and matches a fresh build; on other platforms, where the
maths library may differ in the last float bit, it compares every member structurally
(including the GLB's JSON and buffer contents) with a 1e-4 tolerance on floats. After an intentional format or
generator change, regenerate the sample and commit it.

Licensing: the fixture is not OpenStreetMap data, so the build passes `--osm-license` and the sample's `sources[]` and `NOTICES.txt` carry that SYNTHETIC statement, not an OpenStreetMap/ODbL attribution. Omit `--osm-license` for real OSM extracts; they are then credited as OpenStreetMap (ODbL 1.0).

## `csharp/MbmapReader`

This is a reference reader for consumers; see
[docs/UNITY_CORE_HANDOFF.md](../docs/UNITY_CORE_HANDOFF.md). It uses only the BCL and
System.Text.Json, with C# 8 code that also compiles for netstandard2.1. It:

* verifies the container, `files[]` (one-to-one, byte counts and SHA-256) and `package_id`;
* parses `.mbcol`, `.mbhf` and the GLB with the spec's bounds checks;
* checks the visual/collision name binding;
* runs the orientation probes through a simulated X-negating importer, with negative controls;
* checks the passage-probe capsules against the collision with the validator's shared work budget
  (2,000,000 visits; probes left when it runs out are reported as unchecked), plus self-test
  controls on fixed geometry built in code;
* cross-checks the heightfield against the terrain triangles.

```powershell
dotnet run -c Release --project examples\csharp\MbmapReader -- examples\synthetic_sample.mbmap
```

It exits with 0 and prints `OK`. An invalid package prints `INVALID: …` and exits with 1; for
example, a member with one flipped byte gives `INVALID: collision/map.mbcol: SHA-256 mismatch`.
The project targets net8.0 so it can run. To use the code in a netstandard2.1 library, add the
`System.Text.Json` package.
