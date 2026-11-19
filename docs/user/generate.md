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

**Synthetic attribution caveat:** the v0.1.0 Blender UI assumes local OSM files
are OSM data; it has no synthetic OSM licence override. For a correctly labelled,
redistributable synthetic package, use the [CLI demo](../demo/v0.1.0/README.md),
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

GLO-30 is a roughly 30 m **surface model**, not survey-quality bare earth.
Buildings and canopy affect its heights. DSM correction from PR #11 is
**pending in this candidate**; it must be documented and demonstrated after merge
before the final baseline tag.

Never put credentials in the scene. The optional private Overpass endpoint is
read from `MAP_BUILDER_OVERPASS_URL` at generation time, not entered in a URL
field. Reports retain only sanitized source information.
