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

## Documentation

Start at the **[documentation entry](docs/README.md)**: reading paths, the page inventory and the coverage matrix.

* [User guide](docs/user/README.md): install, generate, export, CLI, presets and consumption.
* [Developer guide](docs/dev/README.md): repository layout, checks and contribution workflow.
* [Architecture overview](docs/architecture/README.md): pipeline, decisions and package format.
* [Release notes](docs/releases/README.md), [demos](docs/DEMO.md) and [workflow diagrams](docs/flows/overview.md).

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

### DSM terrain correction

Copernicus GLO-30 is a surface model (DSM): its heights include buildings, tree canopy and bridge
decks. The **DSM correction** setting (*DSM correction* under the elevation source in the panel: Auto / On / Off; CLI
`--dsm-correction` / `--no-dsm-correction`) pushes the terrain under those features back toward
the surrounding ground before the terrain, roads and buildings are built.

* **Auto** (the default) is ON for the Copernicus source and OFF for local elevation files.
  On or Off overrides that for either source.
* Masked DEM points are those within 15 m of a building footprint (all buildings, including
  courtyards), within 6 m of a `natural=tree`, inside `landuse=forest`/`natural=wood`, or within
  width/2 + 15 m of a `highway`/`railway` way with `bridge=*` (not `no`).
* Only valid polygons are masked: building footprints and forest areas whose rings fail the same
  topology check as generation (e.g. a hole crossing its outer ring), or exceed the footprint
  vertex limit, are left out and counted in `mask.excluded_invalid`. Only surface features are
  masked, inside or outside the area: footprints and forests that generation leaves out as below
  ground or not supported (`location=underground`, `layer<0`, `tunnel=*`, `covered=yes`, bridges)
  never lower the terrain. Identical geometries (e.g. relations sharing their rings) are validated
  and masked once, so `mask.features` counts distinct polygons.
* Mask candidates are selected against the terrain grid extent, not the area: buildings, trees and
  bridge ways just outside the area still mask the edge samples within their buffer, but are not
  generated. Online acquisition always fetches OSM for the area plus 30 m, and that response alone
  is the content. Only when the correction is enabled does it make a second Overpass request, the
  same query with a wider bbox: the grid's overshoot of the area (below one spacing) plus 45 m, the
  farthest a mask can reach (a bridge centreline: at most 30 m half deck width plus its 15 m
  buffer), rounded up to a whole metre, plus the forest areas enclosing the area centre (Overpass
  `is_in`: a forest whose boundary lies wholly outside the bbox would otherwise be missing, and its
  canopy taken for ground). The normal request is byte-identical to the one made with
  the correction off (it shares its cache entry), and it is classified exactly as then, so the
  selected buildings, `building:part` ownership, multipolygon outer suppression, landcover, roads,
  trees, and the classification's counts, `invalid_features` and `unsupported_features` come from
  it alone. The wider request is
  recorded in the features source as `dsm_mask_query`. Its elements (ways, relations, tree nodes)
  that the normal response lacks, including relations that merely reference content ways, only
  add mask candidates — surface building
  footprints, forest/wood polygons, bridge ways and trees, wherever they lie (inside the area too,
  e.g. a tree added to OSM between the two requests): they are never generated, never colour the
  terrain, drive scatter, or appear in counts, `invalid_features` or `unsupported_features`, and their ring
  topology is checked only by the budgeted, deduplicated mask validation below. A content way that
  is the outer of a multipolygon known only to the wider response (same area family, or an
  untagged one with inner rings) is still generated as in the normal response, but its solid
  footprint is left out of the mask, so it never fills that multipolygon's courtyard or clearing.
  The two requests may see slightly different OSM data (minutes apart, or a cached normal
  response); that only affects the mask. If the wider request fails (HTTP error, rate limit, size
  limit, a server-side error remark, malformed XML or an unsupported encoding), the content stands
  and the correction is skipped with a
  warning (`reason: mask candidates unavailable`, the uncorrected surface model);
  `dsm_mask_query` then records only `error_class`, a fixed `error` summary and, for an HTTP
  error, `error_status` — never the parser or server text, which may quote the response. A
  `<meta osm_base>` value (either response, or a local file) that is not an ISO-8601 UTC
  timestamp is not recorded (`osm_base_timestamp_note` instead). The DSM mask candidates (from
    either response) have their own feature allowance (50 000 by default), counted separately from
    the scene content, which alone can fail the build with a feature-limit error; rather than failing
    the build, mask candidates beyond the allowance (enforced as they are collected) are dropped and the correction is skipped with the
    same warning (also with the correction off, mask-only features never fail a build), and a member way
    listed more than once in a multipolygon is used once. Wide-only forest mask areas keep only a
    minimal `_class` tag, not the relation's tags. If only its
  cache write fails (full disk, unwritable cache), its response is still used, uncached, with a
  warning and `dsm_mask_query.cache_write_error`; a failed cache write of the normal request still
  fails acquisition, as with the correction off. So the input OSM content and its selection are
  the same with the correction on or off. What depends on the terrain uses the corrected terrain:
  heights and placement, and terrain-dependent eligibility. A building whose roof a DSM spike
  pierces (the terrain under the footprint rises above the roof underside) is rejected as invalid
  with the correction off but generated with it on, once the spike is lowered; recovering
  buildings that their own DSM surface wrongly rejects is part of the correction's purpose.
* Masked points are filled by harmonic (Laplace) interpolation from the unmasked ground. The
  equation is solved coarse to fine (multigrid: a nested-iteration guess from coarsened grids, with
  semi-coarsening along the long axis of elongated grids, then V- or W-cycles of red-black
  Gauss-Seidel until the largest update is below 5 mm). The work is linear in the grid size and
  bounded. A plane, such as a uniform slope, is reproduced under a masked area that is enclosed by
  unmasked ground; where the mask reaches the grid edge, the fill is levelled towards that edge.
  The fill is smooth and never goes above or below the surrounding unmasked heights. The result is
  `min(original, filled)`: terrain is never raised and unmasked points are not changed.
* The correction is skipped with a warning, and the uncorrected surface model used, if fewer than
  5 % of the points are unmasked, if assembling the margin-only mask candidates (ring joining and
  hole-to-outer assignment) plus validating the mask polygons' ring topology would exceed their
  shared cumulative work budget (5 000 000 geometric tests, checked as it goes;
  `reason: mask validation work budget exceeded`), if the mask rasterisation would exceed its work budget
  (20 000 000 edge and row-crossing units), or if the fill does not converge within its bounded
  cycles (a fill that has not converged is never applied). These do not fail the build; the hard
  input limits (feature count, grid size) still do.
* `report.json` gets a `terrain_correction` entry (`applied`, `setting`, `reason`,
  `masked_points`, `lowered_points`, `total_points`, `max_lowering_m`, `mean_lowering_m`,
  `fill_cycles`, `fill_residual_m`, `fill_converged`, mask parameters and feature counts,
  `validation_work`, `rasterisation_work`).
  `lowered_points` counts the masked points that actually went down; the `processing` note says
  so, or that the correction ran but lowered no points. When applied, the terrain's `surface` provenance becomes
  `inferred:DSM corrected (…)` and the elevation source carries a `processing` note, also shown in
  `NOTICES.txt`. Source hashes and the raw elevation provenance are unchanged.

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
* **Textures** in `map_builder/assets/textures/` (facade, roof tiles, flat-roof gravel, asphalt,
  terrain and concrete) are our own work. They are generated procedurally by a seeded script,
  `python -m tools.textures.make_textures`, and dedicated to the public domain under
  [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/); see `LICENSE-textures.txt`
  there. They contain no photographs and no third-party or map imagery.
* No Google (Maps/Earth/3D Tiles) content is used or supported.

## CLI (no Blender)

The CLI runs the same core pipeline on local files and exports the *generated* plan. Use the
add-on for edited maps.

```powershell
py -3.12 tools\mbmap_cli.py build --osm area.osm --dem dem.tif --datum EGM2008 --dem-license "..." `
    --lat 47.0 --lon 8.0 --width 400 --height 300 --heightfield 2 --out out.mbmap
py -3.12 tools\mbmap_cli.py validate out.mbmap      # exit 0 if VALID
```

`--style stylized` (default since v0.6.0) writes a flat-shaded, low-poly palette with no textures, no
`NORMAL` attribute and no CC0 texture notices; `--style classic` keeps the v0.5.0 look. With classic,
`--textures` (default) embeds the CC0 textures and writes world-scaled UVs (package format 2.1.0, about
+23 % GLB on Pittsburgh plus fixed texture bytes); `--no-textures` writes the untextured GLB of earlier
versions; stylized ignores `--textures`. Collision data is identical either way. The vertex colour of a textured face is divided by its
texture's mean albedo, so the face keeps its palette colour on average and the texture adds only detail.

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

* **Road tunnels, highway bridges, elevated building parts and building passages are generated.**
  `highway=*` ways with `tunnel=yes` (and similar) become flyable tubes (floor = road width + 2 m, 4.5 m walls
  plus a 1 m arch, or `maxheight`; linear floor profile between the portal heights) with a bore passage probe,
  a terrain cut of the bore volume only (terrain between the floor and the roof; ground below the floor stays)
  and 1 m portal headwalls where the terrain rises above the roof. No tree stands in a portal or cut zone.
  Cut-and-cover or underpass tunnels with almost no cover are generated as tubes with a warning. Railway
  tunnels, `tunnel=culvert` and `man_made=tunnel` stay unsupported.
* **Highway bridges.** `bridge=*` (not `no`) highways are generated as `bridge` solids with a `deck`
  and an `under` passage probe. The `under` probe is emitted only where the clearance over the ground
  or crossing road is at least 4 m, so a low bridge has a `deck` probe only. Trees inside the deck
  footprint are not generated; a clearance or grade shortfall is a report warning. Decks have 1 m high, 0.3 m wide
  parapets on both edges (part of the deck shell; the `deck` probe runs between them, so a deck narrower than
  2.7 m has none). Where the deck stands more than 6 m above the ground it also gets concrete piers (1.5 m x deck
  width - 1 m, evenly spaced at most 40 m apart, from 1 m below the ground to the deck underside) as extra closed
  shells of the same `bridge` object; a pier moves up to 5 m along the deck, else is skipped, to stay at least 3 m
  from the `under` probe and off at-grade road ribbons. `PlanOptions.bridge_piers=False` turns piers off.
* **Elevated building parts and building passages.** A part with `min_height` at least 2.6 m above
  the ground gets an `elevated` passage probe along its longest edge, and a
  `tunnel=building_passage` way through a building cuts a straight corridor: the building becomes two
  lower parts (`<id>#1`, `#2`) and an upper part (`<id>#3`) with a `building_passage` probe. A
  passage that cannot be cut cleanly (dead end, bend, courtyard, several passages, too low) is listed
  under `unsupported_features` and the building stays solid. A probe that is blocked by other geometry is
  not exported and is listed under `passage_probes_blocked` in `report.json`.
* Each building is a set of closed, outward-facing, positive-volume shells with no interior
  cavities: no rooms, passages or flyable interiors.
* The GLB is flat-shaded with PBR colour factors and no custom normals or normal maps. The default stylized
  look stores no `NORMAL` attribute (glTF flat shading) and no textures. The classic look stores face normals and,
  with textures on, world-scaled UVs and embedded CC0 base-colour textures.
* **DSM correction is an approximation, not a DTM.** It only knows the features mapped in OSM:
  unmapped buildings, trees or hedges stay in the terrain. Inside masked areas the fill is the
  smoothest surface through the surrounding ground. It follows uniform slopes, but it cannot
  reveal ground that differs from the surrounding points, such as hills or hollows inside a big
  forest, cuttings, or river banks under a bridge. Where a masked area touches the edge of the
  area, the fill there is levelled towards the edge (zero slope across it). `man_made=bridge`
  outlines are not masked (only the bridge ways are). Features outside the area mask the edge only
  if they are in the OSM input: online, with the correction enabled, that covers every mask reach
  around the grid (see above); a local OSM file is used in full (all of it is content), so it should
  extend about 45 m beyond the area for full edge masking. Invalid and
  below-ground footprints and forest polygons are not masked; `natural=tree` nodes are masked as
  generation uses them (no surface check). A scene whose mask polygons are too costly to validate
  within the budget is left uncorrected rather than partly corrected.
* The target size is about 1 × 1 km. There is no streaming, no LOD generation and no
  frame-rate or performance guarantee.
* The online paths (Copernicus download, Overpass, and online acquisition inside Blender) are
  not tested in CI. CI and the committed sample use synthetic fixtures only.
* A consumer that can use the triangle collision does not exist yet; see the handoff document.

## Licence

The code is under a split licence (decision D13, option B):

| Path | Licence |
|---|---|
| `map_builder/blender/`, `map_builder/blender_manifest.toml`, `map_builder/__init__.py` (add-on bootstrap; the one exception in the otherwise-Apache package) and any first-party file that imports `bpy` (`tests/blender/`, `tools/demo/`, `docs/demo/` scripts) | GPL-3.0-or-later (`LICENSE-GPL-3.0.txt`) |
| `map_builder/core/`, `tools/` (CLI), `pyproject.toml`, `examples/` (C# reader), `docs/` (incl. the `.mbmap` format spec), `design/`, `tests/`, `.github/` | Apache-2.0 (`LICENSE`) |
| `map_builder/assets/textures/` | CC0 1.0 (`LICENSE-textures.txt`) |
| `tools/demo/viewer/vendor/` (three.js) | MIT (`LICENSE-three.txt`) |

Every first-party source file carries an SPDX header; see `NOTICE`. The Blender extension's licence is declared in `map_builder/blender_manifest.toml`; there is no published Python distribution, so no packaging licence metadata yet. The Blender extension zip
ships the licence texts and `NOTICE` inside `map_builder/`.

**Generated data is not covered by the code licences.** `.mbmap` packages and GLB files you
generate carry their own data-source attribution in `NOTICES.txt`: OpenStreetMap contributors
(ODbL 1.0), Copernicus GLO-30 DEM, and the CC0 textures (see Data licences above).
