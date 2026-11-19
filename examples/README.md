# Examples

## `synthetic_sample.mbmap`

This is a **synthetic** package. It is built with the CLI from the hand-written fixtures in
[tests/fixtures](../tests/fixtures/README.md), and it is not a real place or real data. It has a
400 × 300 m area, 74 objects, 4945 collision triangles, a 2 m heightfield and 3 orientation
probes. Regenerate it from the repository root:

```powershell
py -3.12 tools\mbmap_cli.py build --osm tests\fixtures\synthetic_area.osm --dem tests\fixtures\synthetic_dem.asc `
    --datum SYNTHETIC --dem-license "SYNTHETIC test data (no licence required)" `
    --osm-license "SYNTHETIC test fixture (hand-written OSM-format XML, not OpenStreetMap data; no licence required)" --lat 47.0 --lon 8.0 `
    --width 400 --height 300 --heightfield 2 --created-utc 2026-01-01T00:00:00Z `
    --name synthetic_sample --out examples\synthetic_sample.mbmap
py -3.12 tools\mbmap_cli.py validate examples\synthetic_sample.mbmap
```

The build is deterministic. With the fixed `--created-utc`, it is byte-identical and gives
`package_id = sha256:33ca4bc6b0f058ce3c175914a580fd2e52c657b9c75fb258e634c1b3496597b6`.
Validation reports `VALID: 0 error(s), 1 warning(s)`; the warning is two degenerate
(zero-area) collision triangles, which is allowed. `tests/test_examples.py` checks that the
committed file still validates and matches a fresh build. After an intentional format or
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
* cross-checks the heightfield against the terrain triangles.

```powershell
dotnet run -c Release --project examples\csharp\MbmapReader -- examples\synthetic_sample.mbmap
```

It exits with 0 and prints `OK`. An invalid package prints `INVALID: …` and exits with 1; for
example, a member with one flipped byte gives `INVALID: collision/map.mbcol: SHA-256 mismatch`.
The project targets net8.0 so it can run. To use the code in a netstandard2.1 library, add the
`System.Text.Json` package.
