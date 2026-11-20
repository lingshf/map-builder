# Demo summary: munich-altstadt-v040

* package: `munich_altstadt`, id `sha256:178c1328e90e3d83a3a38ac2144e12a4c81726a768bd0b62398927647ac3ec3f`, format 2.1.0
* objects: 389, collision triangles: 23378, orientation probes: 3, passage probes: 3
* before: id `sha256:2caff942c8f528111e229415047f5e926375d94fe2ac4595c3ddf0e7940eea64`, objects: 389, passage probes: 3

## Images

* `render-overview-after.png`
* `render-overview-before.png`
* `render-roofs-after.png`
* `render-roofs-before.png`
* `render-gabled-skeleton-after.png`
* `render-gabled-skeleton-before.png`
* `render-hipped-skeleton-after.png`
* `render-hipped-skeleton-before.png`
* `render-gabled-fallback-after.png`
* `render-gabled-fallback-before.png`
* `panel.png`
* `panel.png`: the real Map Builder sidebar in Blender's UI (software OpenGL via Mesa llvmpipe)

## Passage probes

| id | kind | feature | radius m | result |
|---|---|---|---|---|
| osm:way/879138845:under | elevated | osm:way/879138845 | 1.0 | PASS |
| osm:way/1163022325:passage | elevated | osm:way/1163022325 | 1.0 | PASS |
| osm:way/405100898:bore | tunnel | osm:way/405100898 | 1.5 | PASS |

## Viewer

`viewer/` (also `viewer.zip`): `py -3 -m http.server 8780 --directory viewer`, then open http://localhost:8780/

Attribution: see `viewer/NOTICES.txt`.
