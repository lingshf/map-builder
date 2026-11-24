# Demo summary: munich-altstadt-v050

* package: `munich_altstadt`, id `sha256:d191a94de5663d106bc89cde24f105af72e678941e2f8ebe38dcdcccc1762976`, format 2.1.0
* objects: 389, collision triangles: 23372, orientation probes: 3, passage probes: 3
* before: id `sha256:1ebda7540784c688e19c77ec7ba88d8a9672b91fa676abb9c98317129f21aaf2`, objects: 389, passage probes: 3

## Images

* `render-overview-after.png`
* `render-overview-before.png`
* `render-roofs-after.png`
* `render-roofs-before.png`
* `render-vcut-3edge-after.png`
* `render-vcut-3edge-before.png`
* `render-vcut-2edge-after.png`
* `render-vcut-2edge-before.png`
* `render-named-fallback-after.png`
* `render-named-fallback-before.png`
* Panel screenshot: `panel.png` not produced: no Mesa (llvmpipe) Blender copy configured, and background Blender has no window or OpenGL context (see tools/demo/README.md, "Panel screenshot")

## Passage probes

| id | kind | feature | radius m | result |
|---|---|---|---|---|
| osm:way/879138845:under | elevated | osm:way/879138845 | 1.0 | PASS |
| osm:way/1163022325:passage | elevated | osm:way/1163022325 | 1.0 | PASS |
| osm:way/405100898:bore | tunnel | osm:way/405100898 | 1.5 | PASS |

## Viewer

`viewer/` (also `viewer.zip`): `py -3 -m http.server 8780 --directory viewer`, then open http://localhost:8780/

Attribution: see `viewer/NOTICES.txt`.
