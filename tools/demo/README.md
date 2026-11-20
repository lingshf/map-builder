# Demo kit

One command turns a package (and optionally the previous one) into the visual part of a sprint
review: before/after renders, a three.js viewer with probe results, and `summary.md`.

```powershell
& C:\tools\blender-4.2.23-windows-x64\blender.exe -b --factory-startup --python-exit-code 1 `
    --python tools\demo\run_demo.py -- --preset synthetic --after examples\synthetic_sample.mbmap `
    --out demo-out
py -3 -m http.server 8780 --directory demo-out\viewer     # then open http://localhost:8780/
```

Optional flags (append to the first command): `--before <previous.mbmap>` adds `-before` renders and a
before/after comparison; `--panel` adds `panel.png` (see below); `--bundle-only` skips the renders.

Output in `--out` (names are fixed): `render-<camera>-after.png` (+ `-before.png`), `viewer/`
(`index.html`, `viewer.js`, `map.glb`, `probes.json`, `NOTICES.txt`, `vendor/` = three.js r160, MIT)
and `viewer.zip`, `summary.md`. `--bundle-only` skips the renders (also runs under plain Python).
Renders use Cycles CPU, 1280 x 720, 64 samples, denoised, sky + sun (about 30 s per image for the
synthetic area; 3 cameras x 2 packages is about 3 minutes). Never port 8765.

**Probe results** are computed with the package's own collision (`capsule_hits`, same query as the
validator): green PASS / red BLOCKED capsules in the viewer, a table in `summary.md`.

**Panel screenshot (`panel.png`, optional `--panel`).** Background Blender has no window or OpenGL
context, so the sidebar is captured by a second, windowed Blender run (`panel_shot.py`) on a separate
Blender copy that uses Mesa llvmpipe (software OpenGL). One-time setup:

1. Download `release-msvc.7z` from https://github.com/pal1000/mesa-dist-win/releases and extract it.
2. Copy a portable Blender 4.2 folder to a new location (never modify your main install).
3. Copy everything from the extracted `x64` folder next to the copy's `blender.exe`
   (`opengl32.dll` is the important one).
4. Pass `--mesa-blender <path>\blender.exe` or set `MB_DEMO_BLENDER_MESA`.

Add `--panel` to the command above (after `--out demo-out`) to also write `panel.png` (Map Builder tab
open, map in the viewport; about 20 s). `panel.png` is deleted at the start of every run, so an old image
is never left behind; without a configured copy, or if the run fails, the step is skipped and
`summary.md` records why instead of faking the UI. The tab click is a simulated event
calibrated on a 1920 x 1129 window, so other screen sizes may need adjusting in `panel_shot.py`.

`make_probe_sample.py out.mbmap` derives a small package with three passage probes (PASS, BLOCKED, and
an id containing markup) from the synthetic sample, for viewer smoke tests.

## Preset format (`presets/<name>.json`)

```json
{"name": "synthetic", "description": "...",
 "area": {"lat": 47.0, "lon": 8.0, "width_m": 400, "height_m": 300},
 "cameras": [{"name": "overview", "eye": [x, y, z], "target": [x, y, z], "lens_mm": 28}]}
```

Coordinates are the map frame (metres, +X east, +Y north, +Z up). 1 to 6 cameras with unique
`[a-z0-9-]` names; identical cameras for before and after make comparable pairs. Add a camera per
feature to show (`bridge-under`, `tunnel-portal`, ...). Presets: `synthetic`, `pittsburgh` (Fort Pitt Bridge/Tunnel, 1200 x 1000 m), `sf-fidi` (demo area;
cameras are starting points), `munich-altstadt` (400 x 400 m: elevated part, building passage and roof shapes on real
data, S2-F2).
