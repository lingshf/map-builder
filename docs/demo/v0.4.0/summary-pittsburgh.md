# Demo summary: pittsburgh

* package: `pittsburgh`, id `sha256:c605727a7037d60fde16604526208c5559da267eebc7f45362adabc80c5d1b40`, format 2.1.0
* objects: 3290, collision triangles: 144108, orientation probes: 3, passage probes: 13
* before: id `sha256:69cf9a3a84d4c535c0f457587aa632d442a3a63d2b0dff60b1452a6ec0703b45`, objects: 3290, passage probes: 13

## Images

* `render-overview-after.png`
* `render-overview-before.png`
* `render-dsm-ground-after.png`
* `render-dsm-ground-before.png`
* `render-bridge-under-after.png`
* `render-bridge-under-before.png`
* `render-tunnel-portal-after.png`
* `render-tunnel-portal-before.png`
* Panel screenshot: `panel.png` not produced: no Mesa (llvmpipe) Blender copy configured, and background Blender has no window or OpenGL context (see tools/demo/README.md, "Panel screenshot")

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
