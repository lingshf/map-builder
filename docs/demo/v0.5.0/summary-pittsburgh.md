# Demo summary: pittsburgh-v050

* package: `pittsburgh`, id `sha256:3124bbeeaf660cffe4f810fe0d7235608db2bfc86fd8d830e4c38c64fc3c1ead`, format 2.1.0
* objects: 3296, collision triangles: 145650, orientation probes: 3, passage probes: 11
* before: id `sha256:6fc57ee53e151a35a24a55c852d08064333b9ed5fd67c553dc4a390280dd9abf`, objects: 3290, passage probes: 13

## Images

* `render-overview-after.png`
* `render-overview-before.png`
* `render-bridge-under-after.png`
* `render-bridge-under-before.png`
* `render-bank-after.png`
* `render-bank-before.png`
* Panel screenshot: `panel.png` not produced: no Mesa (llvmpipe) Blender copy configured, and background Blender has no window or OpenGL context (see tools/demo/README.md, "Panel screenshot")

## Passage probes

| id | kind | feature | radius m | result |
|---|---|---|---|---|
| osm:way/24957029:under | bridge | osm:way/24957029 | 1.0 | PASS |
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
