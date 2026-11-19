# S1-DEMOKIT: one-command demo script

Sprint S1 · no dependencies (uses current main) · decision D17

## Goal

One reusable command, built once, that turns "previous package + current package" into the
whole visual part of a sprint review, so each review only *runs* it. Low overhead is a user
requirement ("注意不要太频繁，以免影响进度").

## Scope

* `tools/demo/run_demo.py` — run with headless Blender (`blender -b --python-exit-code 1
  --python tools/demo/run_demo.py -- --preset <name> --after <pkg.mbmap> [--before <pkg.mbmap>]
  --out <dir>`). It writes to `<dir>`:
  * `render-<camera>-after.png` (and `-before.png` when `--before` is given) with **Cycles CPU**,
    1280 × 720, 64 samples, denoise, sun + sky;
  * `panel.png`: the Map Builder sidebar panel (see below);
  * `viewer/`: a static three.js page (`index.html`, `viewer.js`, `map.glb`, `probes.json`,
    `NOTICES.txt`) and `viewer.zip`;
  * `summary.md`: image list, probe results, counts — pasted into the release notes.
* **Fixed camera presets** committed as `tools/demo/presets/<name>.json` (area lat/lon/size and
  named cameras: `overview`, plus one per feature to show, e.g. `bridge-under`, `tunnel-portal`).
  Presets for `synthetic` and the demo area (D26). Identical cameras give before/after pairs.
* **Panel screenshot:** without hardware OpenGL, try Mesa llvmpipe (`opengl32.dll`) in a
  **separate copy** of portable Blender (never modify `C:\tools\blender-4.2.23-windows-x64\`)
  with `bpy.ops.screen.screenshot`. If that fails within ~1 h of effort, ship without
  `panel.png`, record it as a known limit and tell the coordinator; do not fake the UI.
* Viewer: three.js pinned (vendored with its MIT licence, or CDN with SRI), probes drawn as
  capsules (green PASS / red blocked), orbit + fly camera, OSM/Copernicus attribution.
  Serve with `py -3 -m http.server 8780` (never port 8765).
* `tools/demo/README.md`: the one command and the preset format.

## Acceptance criteria

1. One command on the synthetic sample produces all outputs above (panel.png or a recorded
   limit) in ≤ 10 min on the dev machine; re-running is deterministic in file names and cameras.
2. The viewer page opens via the serve command and lists probe ids with their results.
3. The pure-Python parts (preset loading, probes.json, NOTICES, zip listing) have a small unit
   test adding < 1 s; PR CI otherwise unchanged (renders are never run in CI).

## Performance considerations

≤ 6 cameras per preset × 2 (before/after) at 64 samples keeps a sprint review's rendering
≤ 30 min of unattended CPU time. No per-sprint code changes expected: only new presets.

## Expected tests

`tests/test_demo_bundle.py`; the manual run recorded in the PR (images attached).

## Conflict domain

Hard: `tools/demo/` (new), `tests/test_demo_bundle.py`. Parallel with everything.
