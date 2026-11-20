# Demo summary: pittsburgh

* package: `pittsburgh`, id `sha256:882855ca2c0cf1b17294743c7f7865a5ede3b532999cdfd02f304d9a824c5b7c`, format 2.0.0
* objects: 3290, collision triangles: 144108, orientation probes: 3, passage probes: 13
* before: id `sha256:5abdabef613b43bbf62cb4eb6a2528e6d0857e55c708b26795638705f26fedba`, objects: 3246, passage probes: 0

## Images

* `render-overview-after.png`
* `render-overview-before.png`
* `render-dsm-ground-after.png`
* `render-dsm-ground-before.png`
* `render-bridge-under-after.png`
* `render-bridge-under-before.png`
* `render-tunnel-portal-after.png`
* `render-tunnel-portal-before.png`
* `panel.png`
* `panel.png`: the real Map Builder sidebar in Blender's UI (software OpenGL via Mesa llvmpipe)

## Passage probes

| id | kind | feature | radius m | result |
|---|---|---|---|---|
| osm:way/11950069:under | bridge | osm:way/11950069 | 1.0 | PASS |
| osm:way/24957029:under | bridge | osm:way/24957029 | 1.0 | PASS |
| osm:way/121593794:deck | bridge | osm:way/121593794 | 1.0 | PASS |
| osm:way/121593794:under | bridge | osm:way/121593794 | 1.0 | PASS |
| osm:way/173225719:under | bridge | osm:way/173225719 | 1.0 | PASS |
| osm:way/550018203:deck | bridge | osm:way/550018203 | 1.0 | PASS |
| osm:way/550018206:deck | bridge | osm:way/550018206 | 1.0 | PASS |
| osm:way/54223852:deck | bridge | osm:way/54223852 | 1.0 | PASS |
| osm:way/54210147:deck | bridge | osm:way/54210147 | 1.0 | PASS |
| osm:way/264591820:deck | bridge | osm:way/264591820 | 1.0 | PASS |
| osm:way/550018192:deck | bridge | osm:way/550018192 | 1.0 | PASS |
| osm:way/11965424:bore | tunnel | osm:way/11965424 | 1.5 | PASS |
| osm:way/28411466:bore | tunnel | osm:way/28411466 | 1.5 | PASS |

## Viewer

`viewer/` (also `viewer.zip`): `py -3 -m http.server 8780 --directory viewer`, then open http://localhost:8780/

Attribution: see `viewer/NOTICES.txt`.
