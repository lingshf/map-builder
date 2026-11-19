# Demo summary: synthetic

* package: `probe_sample`, id `sha256:8c51963e042640061e81e2ea60a539fae43980de87b6f59b1912d9ce26870e39`, format 2.0.0
* objects: 74, collision triangles: 4945, orientation probes: 3, passage probes: 3
* before: id `sha256:3bcc75e25368d71ec5c866233969e67fba03a0302594d61ca4767ca22165b0a2`, objects: 74, passage probes: 0

## Images

* `render-overview-after.png`
* `render-overview-before.png`
* `render-street-after.png`
* `render-street-before.png`
* `render-top-after.png`
* `render-top-before.png`
* `panel.png`
* `panel.png`: the real Map Builder sidebar in Blender's UI (software OpenGL via Mesa llvmpipe)

## Passage probes

| id | kind | feature | radius m | result |
|---|---|---|---|---|
| clear-overhead | bridge | osm:way/1007 | 1.0 | PASS |
| through-building | tunnel | osm:way/1007 | 1.5 | BLOCKED |
| <img src=x onerror=alert(1)> & co | elevated | osm:way/1007 | 1.0 | PASS |

## Viewer

`viewer/` (also `viewer.zip`): `py -3 -m http.server 8780 --directory viewer`, then open http://localhost:8780/

Attribution: see `viewer/NOTICES.txt`.
