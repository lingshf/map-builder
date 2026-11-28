# Generate a map

## First try: offline synthetic area

Download or clone the **same release's source** as well as installing its extension
zip. The test fixtures are in the source checkout, not a separate release asset.
They describe an invented place, not real Switzerland or OpenStreetMap data.

In **3D Viewport > Sidebar (N) > Map Builder**, enter:

| Group | Setting | Value |
|---|---|---|
| Area (WGS84) | Area | Centre + size |
| Area | Latitude / Longitude | 47.0 / 8.0 |
| Area | Width / Height | 400 / 300 m |
| Sources | Elevation | Local file |
| Sources | Elevation file | Choose `tests\fixtures\synthetic_dem.asc` from the checkout |
| Sources | CRS (.asc) | EPSG:4326 |
| Sources | Vertical datum | SYNTHETIC |
| Sources | Licence | SYNTHETIC test data (no licence required) |
| Sources | Terrain spacing | 10 m |
| Sources | DSM correction | Auto (off for this local elevation file) |
| Sources | Features | Local .osm file |
| Sources | OSM file | Choose `tests\fixtures\synthetic_area.osm` |
| Content | Map name | synthetic_preview |

Leave the content toggles and seed at their defaults, then click **Generate Map**.
A new collection appears containing independently editable terrain, buildings,
roads, water and vegetation. Existing scene objects are not cleared.

Open Blender's **Text Editor** and select **MapBuilder Report**. Review sources,
unsupported features, invalid features and warnings before using the map. A
successful generation can still have warnings; it does not mean every OSM
feature was generated.

**Synthetic attribution caveat:** the current Blender UI assumes local OSM files
are OSM data; it has no synthetic OSM licence override. For a correctly labelled,
redistributable synthetic package, use the
[release demo](../demo/v0.1.0/README.md), which declares synthetic attribution
through the shared pipeline, or the [CLI sample command](../../examples/README.md),
which supplies `--osm-license`. Do not present the fixture as real OSM data.

## Real data: online or your own files

Use a WGS84 centre and a roughly 1000 x 1000 m area. Supported normal side
lengths are 50-2000 m and latitude must satisfy |lat| <= 84 degrees. A bounding
box is an alternative. This is a small-area workflow, not a world streamer.

Choose **Copernicus GLO-30 (online)** and **Overpass API (online)**, enable
Blender's online access, then Generate. Downloads can fail because of provider
availability, coverage or connectivity; fix the reported cause and retry.
There is no fabricated or flat-ground fallback.

For local elevation use a supported GeoTIFF or ESRI ASCII grid in EPSG:4326 or
WGS84 UTM, declare its true vertical datum and licence, and provide covering OSM
XML. See [source-data licensing](../../README.md#data-licences).

Never put credentials in the scene. The optional private Overpass endpoint is
read from `MAP_BUILDER_OVERPASS_URL` at generation time, not entered in a URL
field. Reports retain only sanitized source information.

## DSM terrain correction (inferred ground)

GLO-30 is a roughly 30 m **surface model**: rooftops, tree canopy and bridge decks
can appear as raised ground. The **Sources > DSM correction** control lowers
terrain under OSM-mapped buildings, trees, forests and bridge decks toward a
smooth fill of surrounding ground **before** placing buildings and vegetation.
It never raises terrain. Collision and the exported terrain follow this result.

| Setting | Behavior |
|---|---|
| Auto (default) | On for Copernicus GLO-30; off for local elevation files |
| On | Request correction, including for a local DSM |
| Off | Keep the source surface unchanged; suitable for an already corrected local DTM |

For a real Copernicus map, leave **Auto**, generate and read
**MapBuilder Report**. To compare, set **Off** and generate a second, separately
named collection; each Generate adds a new collection. Inspect one collection
at a time and select the intended **Map collection** explicitly when exporting.
Do not expect the offline fixture's default Auto setting to demonstrate DSM
lowering: it deliberately leaves local data unchanged.

In the CLI, append `--dsm-correction` to force On or
`--no-dsm-correction` to force Off; omit both for Auto. All normal input and
licensing arguments still apply.

When correction is enabled with online Overpass features, a second, wider
**mask-only** request covers nearby and enclosing features. The normal response
still determines scene content; cold-cache generation can take longer. If this
optional request fails or its mask budgets are exceeded, generation continues
with the **original surface model and a warning**. Correction is also skipped
if fewer than 5% of samples are unmasked or the bounded fill does not converge.
This differs from a required DEM/content download failure, which still stops
generation. NoData remains an error; neither case invents replacement terrain.

Check `report.json`'s `terrain_correction` for `applied`, `reason`,
`masked_points`, `lowered_points`, `total_points`, `max_lowering_m` and
`mean_lowering_m`. `dsm_mask_query` records the optional request in source
provenance. Applied correction is labelled inferred and receives a processing
note in package `NOTICES.txt`; raw source hashes are unchanged. DSM correction
does not change the package schema.

**Limits:** this is not survey-quality bare earth or a true DTM. Hidden hills
and hollows inside large masks are smoothed, fills touching an area edge level
off, and buildings or trees missing from OSM remain uncorrected. Highway bridges are generated
separately as deck solids.

## Roof shapes and road-export diagnostics

OSM `roof:shape` is built as follows:

| Shape | Footprints |
|---|---|
| flat, skillion | any, including courtyards |
| hipped, gabled | eligible simple polygons up to 64 vertices, no courtyard (L, T, U, trapezoid...), from the straight skeleton (since v0.4.0; before, rectangles only). An eligible footprint can still fall back; see below |
| pyramidal, dome, onion | convex |
| half-hipped, gambrel, mansard, round, saltbox | rectangles only |

A gabled roof on a non-rectangular footprint gets a vertical gable wall on
each end the skeleton can represent. Since v0.5.0, an end the plain cut cannot
represent (the ridge would meet the gable edge outside it, or the gable end
would be a sliver) is cut by a vertical wall through that end edge instead;
the other ends stay hipped, and a gabled roof needs at least two gable ends.
Only if that is not possible does the roof fall back to **hipped**, not flat,
with the reason in `provenance.roof_shape`. A near-rectangle gable whose eave
edges are not parallel is built from the skeleton (planar) or falls back with a
named reason. `roof:direction` is the
direction the slope faces, and a ridge perpendicular to it is the target, not
a guarantee: on a skeleton gable the ridge bearing follows from the footprint.
If no emitted ridge is within 10° of perpendicular, `provenance.roof_direction`
reports `approximate: ridge NNN° vs tagged DDD°`. Roof orientation and
direction tags influence supported shapes. Unsupported or ill-fitting shapes
fall back with `fallback:` provenance; inspect the report rather than assuming
every tagged roof is reproduced. The synthetic sample's way/1043 demonstrates
a dome.

On real data, some tagged roofs still fall back. In the Munich Altstadt demo,
67 buildings have a tagged non-flat `roof:shape`. In v0.5.0, **45** are built
as tagged (v0.4.0: 29). The other 22 all name
their reason: 18 gabled roofs fall back to hipped (the gable end is not
representable, even with a vertical cut), and 4 to flat (courtyard,
quadruple_saltbox, roof height 0, a concave pyramidal). Mixed ends (a gable
wall on some ends, a hip on the others) are covered by tests but do not occur
in this area. Each building's `provenance.roof_shape` in
`manifest.json` says which: `measured:osm roof:shape` (built as tagged),
`fallback:...` with the reason, or `inferred:flat` (no tag);
`provenance.roof_construction` says how it was built. See the
[v0.5.0 demo](../demo/v0.5.0/README.md).

## Water (rivers and lakes)

Since v0.5.0, every OSM water polygon (`natural=water`, `waterway=riverbank`
and the other water area tags the area query already reads) that lies inside
the terrain becomes its own **flat water surface**: an object
`water:osm:<type>/<id>`, material **MB Water**, collision class `water`. The
surface is clipped to the polygon, at a level taken from the shore (rivers of
300 m or more step down along their course). The terrain under it is carved to
1.5 m below the surface, so the water no longer follows the elevation model's
dips and you do not see a painted "mat" of terrain. Banks keep their landcover
colour; only water bodies that cannot be built keep the old water-coloured
terrain cells.

Roads, buildings and bridge decks stand on the ground before carving. Decks are
never lowered; a deck the water would touch is raised just above it
(`report.json` `water_decks_raised`). Bridge piers and building walls reach
down to the carved bed. `report.json` `water_bodies` lists each body and its
outcome (`built(flat)`, `built(profile, N stations)` or a named fallback,
for example `fallback(no shore samples)` for a body outside the terrain).

**MB Water** uses colour rather than a dedicated water texture. Stylized
packages contain no textures; water appears blue in Classic. The heightfield
(`.mbhf`) shows the riverbed, not the water;
to land on or detect water, query the collision mesh (`.mbcol`), where water
is class 5 `water`. Packages with no water are unchanged.

## Style

**Content > Style** chooses the look. **Stylized** (the default since v0.6.0)
is a low-poly, flat-shaded palette with no embedded textures; the package is
smaller and carries no CC0 texture notices. **Classic** is the v0.5.0 look,
with the optional textures below. The style is fixed when you generate and
Export reuses it; regenerate to switch. Geometry, collision, heightfield and
passage probes are the same in both styles. The CLI equivalent is
`--style stylized` / `--style classic`.

## Textures (Classic style only)

With **Style: Classic**, **Content > Textures** (default on) gives the generated buildings, roofs,
roads and terrain CC0 base-colour textures (facade, roof tiles, flat-roof
gravel, asphalt, a neutral terrain detail, concrete) with world-scaled UVs. The
vertex colour keeps each object's palette colour on average; the texture adds
detail. Since v0.5.0 the terrain texture is grey detail only, so landcover keeps
its colour (water reads blue, not green). Turn
it off for the plain-colour look with the same geometry (it does not
bring back earlier roofs). Collision is the same
either way. The panel shows the CC0 attribution while Textures is on, and the
CLI equivalent is `--textures` / `--no-textures`. What ends up in the package
is decided at export; see [Export](export.md).

On steep real terrain, a road face thinner than float32 can represent may be
omitted if storing it would make it non-upward-facing. `slivers_dropped` in the
road's provenance records the count, maximum width and total area. This is
not general road simplification: wider folded faces remain invalid and package
validation is not relaxed. Railway tunnels are still omitted even though
internal structure routing is in place.

Road tunnels (`highway=*` with `tunnel=yes`) are generated as flyable tubes with
portal headwalls, a terrain cut and a bore passage probe; see the report's `counts.tunnels`.
Railway tunnels, culverts and `man_made=tunnel` stay unsupported.
