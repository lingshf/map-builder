# Demo summary: munich-altstadt

* package: `munich_altstadt`, id `sha256:2caff942c8f528111e229415047f5e926375d94fe2ac4595c3ddf0e7940eea64`, format 2.0.0
* objects: 389, collision triangles: 22608, orientation probes: 3, passage probes: 3
* before: id `sha256:44a8aafe5b8961cdd95052eff3119afc0d8b490ff68262fde12e48a90f768e46`, objects: 359, passage probes: 0

## Images

* `render-overview-after.png`
* `render-overview-before.png`
* `render-elevated-under-after.png`
* `render-elevated-under-before.png`
* `render-passage-after.png`
* `render-passage-before.png`
* `render-roofs-after.png`
* `render-roofs-before.png`
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
