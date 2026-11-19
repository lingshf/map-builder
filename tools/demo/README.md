# Demo kit

One command turns a package (and optionally the previous one) into the visual part of a sprint
review: before/after renders, a three.js viewer with probe results, and `summary.md`.

```powershell
& C:\tools\blender-4.2.23-windows-x64\blender.exe -b --factory-startup --python-exit-code 1 `
    --python tools\demo\run_demo.py -- --preset synthetic --after examples\synthetic_sample.mbmap `
    [--before old.mbmap] --out demo-out
py -3 -m http.server 8780 --directory demo-out\viewer     # then open http://localhost:8780/
```

Output in `--out` (names are fixed): `render-<camera>-after.png` (+ `-before.png`), `viewer/`
(`index.html`, `viewer.js`, `map.glb`, `probes.json`, `NOTICES.txt`, `vendor/` = three.js r160, MIT)
and `viewer.zip`, `summary.md`. `--bundle-only` skips the renders (also runs under plain Python).
Renders use Cycles CPU, 1280 x 720, 64 samples, denoised, sky + sun (about 30 s per image for the
synthetic area; 3 cameras x 2 packages is about 3 minutes). Never port 8765.

**Probe results** are computed with the package's own collision (`capsule_hits`, same query as the
validator): green PASS / red BLOCKED capsules in the viewer, a table in `summary.md`.

**Panel screenshot (`panel.png`): known limit.** Background Blender has no window or OpenGL context
(EEVEE/Workbench crash too), so `bpy.ops.screen.screenshot` cannot capture the sidebar; `summary.md`
records this instead of faking the UI. Trying Mesa llvmpipe in a separate Blender copy is left as a
follow-up if a UI screenshot becomes necessary.

## Preset format (`presets/<name>.json`)

```json
{"name": "synthetic", "description": "...",
 "area": {"lat": 47.0, "lon": 8.0, "width_m": 400, "height_m": 300},
 "cameras": [{"name": "overview", "eye": [x, y, z], "target": [x, y, z], "lens_mm": 28}]}
```

Coordinates are the map frame (metres, +X east, +Y north, +Z up). 1 to 6 cameras with unique
`[a-z0-9-]` names; identical cameras for before and after make comparable pairs. Add a camera per
feature to show (`bridge-under`, `tunnel-portal`, ...). Presets: `synthetic`, `sf-fidi` (demo area;
cameras are starting points).
