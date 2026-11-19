# map-builder

A Blender 4.2 LTS add-on and a headless CLI that turn real terrain and OpenStreetMap data into an
editable, georeferenced map of about 1 × 1 km. They export a validated, engine-neutral `.mbmap`
package containing:

* GLB visuals, baked from the final evaluated triangles;
* authoritative neutral collision (`.mbcol`), bound one-to-one to the GLB nodes by name;
* an optional terrain heightfield (`.mbhf`);
* `manifest.json` with the georeference, SHA-256 hashes, orientation probes, provenance and licences;
* `NOTICES.txt` and `report.json`.

The contract is [docs/PACKAGE_FORMAT.md](docs/PACKAGE_FORMAT.md). Test coverage and its gaps are in
[docs/VALIDATION.md](docs/VALIDATION.md). The guide for consumers (Unity presentation and a
physics Core) is [docs/UNITY_CORE_HANDOFF.md](docs/UNITY_CORE_HANDOFF.md).

## Install (Blender 4.2 LTS or newer)

```powershell
blender --command extension build --source-dir map_builder --output-dir dist
```

In Blender, go to **Edit › Preferences › Get Extensions**, open the **⌄** menu and choose
**Install from Disk…**, then pick the zip from `dist/`. Online sources also need
**Preferences › System › Network › Allow Online Access**. Without it, Generate refuses and names
the problem; local files still work.

The panel is in **3D Viewport › Sidebar (N) › Map Builder**.

## Workflow

1. **Area:** enter either the WGS84 centre (lat/lon) and width/height in metres, or a bounding
   box. The default is 1000 × 1000 m. Sides must be between 50 m and 2000 m (the hard cap is
   5000 m), and |lat| ≤ 84°.
2. **Sources:**
   * Elevation: *Copernicus GLO-30 (online)*, or a *Local file* (GeoTIFF or ESRI ASCII grid, in
     EPSG:4326 or WGS84 UTM, with its vertical datum and licence declared).
   * Features: *Overpass API (online)*, or a *Local .osm file*.
3. **Generate Map:** this builds terrain, buildings, roads, vegetation and water as ordinary
   Blender objects in a dedicated collection. Unsupported or invalid features are listed in the
   report rather than silently dropped. If elevation is missing or fails, Generate stops; it never
   substitutes flat ground.
4. **Edit** normally: move, scale, mirror, delete, duplicate, model new geometry, or change
   modifiers. Each object keeps a stable `mb_id` and a collision class.
5. **Export Map Package:** this bakes the evaluated scene into GLB, collision and an optional
   heightfield, then writes the `.mbmap` atomically. A failed export leaves the previous package
   untouched.
6. **Validate Package:** this runs the full validator (structure, hashes, binding, geometry,
   probes and policy) and prints the errors and warnings.

## Credentials and privacy

* There is no free-text endpoint field. A private Overpass instance is read from the
  **`MAP_BUILDER_OVERPASS_URL`** environment variable when you click Generate (endpoint option
  *From $MAP_BUILDER_OVERPASS_URL*). The URL is never stored in the `.blend`, the preferences, the
  cache or the package.
* Every recorded URL is reduced to its origin (`scheme://host[:port]`).
* Text fields are scrubbed of credential-like content when you edit them, and checked again on
  Generate and Export.
* The validator enforces this policy on the manifest, `report.json`, the collision object table
  and the glTF JSON.
* The download cache is used only for public endpoints.

## Data licences

The package records each source and its licence in `manifest.json` and `NOTICES.txt`. **Ship
NOTICES.txt (or equivalent attribution) with any product that uses a map.**

* **OpenStreetMap** data is © OpenStreetMap contributors, under the
  [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/). A map built from OSM is a
  *Produced Work*: display the attribution, and know that the ODbL share-alike terms apply to
  derived *databases* (for example, if you publicly distribute the extracted data). The ODbL does
  **not** require your game or application code to be open source.
* **Copernicus DEM GLO-30** is © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018,
  provided under COPERNICUS by the European Union and ESA. It allows free use, modification and
  redistribution, including commercial use, with attribution. GLO-30 is a surface model (it
  includes canopy and buildings) with EGM2008 heights. The tiles come from the public AWS Open
  Data bucket, with no account needed.
* **Local files:** you declare the licence and vertical datum yourself, and they are recorded
  verbatim.
* No Google (Maps/Earth/3D Tiles) content is used or supported.

## CLI (no Blender)

The CLI runs the same core pipeline on local files and exports the *generated* plan. Use the
add-on for edited maps.

```powershell
py -3.12 tools\mbmap_cli.py build --osm area.osm --dem dem.tif --datum EGM2008 --dem-license "..." `
    --lat 47.0 --lon 8.0 --width 400 --height 300 --heightfield 2 --out out.mbmap
py -3.12 tools\mbmap_cli.py validate out.mbmap      # exit 0 if VALID
```

`--created-utc 2026-01-01T00:00:00Z` fixes the timestamp. With the same inputs on the same
platform, the package and its `package_id` are then byte-identical (other platforms' maths
libraries may differ in the last float bit). [examples/README.md](examples/README.md) gives the command
for the committed synthetic sample and shows the C# reference reader.

## Tests

```powershell
py -3.12 -W error::ResourceWarning -m unittest discover -s tests -t .     # unit + acceptance + CLI (Python 3.11+)
& "C:\path\to\blender.exe" --background --factory-startup --python tests\blender\run_integration.py -- "$env:TEMP\mb_it"
dotnet run -c Release --project examples\csharp\MbmapReader -- examples\synthetic_sample.mbmap
```

CI runs the unit tests on Python 3.11 and 3.12, plus a CLI build and validate of the synthetic
fixtures. The headless Blender run is manual. See [docs/VALIDATION.md](docs/VALIDATION.md).

## Limits

* **Flight under bridges, through tunnels or beneath elevated building parts is not generated
  yet; the format is ready.** Package format 2.0.0 has `bridge`, `tunnel` and `structure`
  collision classes and `passage_probes`, but the generator still omits bridges and tunnels and
  builds elevated volumes as closed solids. All of these are listed under
  `unsupported_features` in `report.json`.
* Each building is a set of closed, outward-facing, positive-volume shells with no interior
  cavities: no rooms, passages or flyable interiors.
* The GLB is flat-shaded with face normals and PBR colour factors. It has no textures, UVs or
  custom normals.
* The target size is about 1 × 1 km. There is no streaming, no LOD generation and no
  frame-rate or performance guarantee.
* The online paths (Copernicus download, Overpass, and online acquisition inside Blender) are
  not tested in CI. CI and the committed sample use synthetic fixtures only.
* A consumer that can use the triangle collision does not exist yet; see the handoff document.

## Licence

The add-on's `blender_manifest.toml` declares `GPL-3.0-or-later` as a provisional default
matching Blender's own licence. This is an **assumption that the repository owner
must confirm**. There is no `LICENSE` file in the repository yet. Data licences (above) are
separate from the code licence.
