# Demo summary: munich-altstadt-v050

* package: `munich_altstadt`, id `sha256:62e08fd1ff5e284fef9b5341e4d1ad2fcb99b3125b228e74351982a79da488af`, format 2.1.0
* objects: 389, collision triangles: 23372, orientation probes: 3, passage probes: 3
* before: id `sha256:178c1328e90e3d83a3a38ac2144e12a4c81726a768bd0b62398927647ac3ec3f`, objects: 389, passage probes: 3

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
