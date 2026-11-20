# Real-data demo (v0.4.0)

How to rebuild and check the two v0.4.0 real-data maps, textured and
untextured, with the recorded numbers. Images and the comparisons are in the
[v0.4.0 demo](demo/v0.4.0/README.md). Raw evidence is in
[evidence.json](demo/v0.4.0/evidence.json). The v0.3.0 recipe and numbers are in
the [v0.3.0 demo](demo/v0.3.0/README.md).

| Preset | Area | Structures |
|---|---|---|
| `pittsburgh` | 40.437 N, 80.016 W, 1200 x 1000 m | Fort Pitt Bridge (double deck, piers), Fort Pitt Tunnel |
| `munich-altstadt` | 48.1395 N, 11.5764 E, 400 x 400 m | Elevated building part, Rid Passage (building passage), road tunnel, gabled and hipped roofs on non-rectangular footprints |

Presets: [tools/demo/presets/](../tools/demo/presets/). Options for both
areas: seed 1, DSM correction on, terrain spacing 10 m, heightfield 2 m,
`created_utc` fixed at `2026-11-20T00:00:00Z`.

## Recorded results (RC, main e266a1b + release changes)

Built offline from the v0.3.0 acquisition caches (2026-11-20 UTC).

| | Munich Altstadt | Pittsburgh |
|---|---|---|
| package_id, textured | `sha256:178c1328…ac3ec3f` | `sha256:c605727a…5c1d40` |
| package_id, `--no-textures` | `sha256:b4b8a9a0…c3a37a` | `sha256:69cf9a3a…703b45` |
| Objects | 389 | 3290 |
| Collision triangles (degenerate) | 23,378 (59) | 144,108 (76) |
| Passage probes exported / blocked | 3 / 26 | 13 / 29 |
| Tagged non-flat roofs built as tagged | 29 / 67 (v0.3.0: 1 / 67) | |
| Build, excluding download, median of 3: textured / untextured | **4.304 s** / 3.596 s | **20.020 s** / 18.489 s |
| Python validator | `VALID`, 1 warning | `VALID`, 1 warning |
| C# reference reader | `OK`, 3/3 probes PASS | `OK`, 13/13 probes PASS |
| Headless Blender (generate + export), textured and untextured | `VALID`; 3/3 PASS, same probe ids | `VALID`; 13/13 PASS, same probe ids |

The build target is 120 s or less, so both areas pass. `.mbcol` and the
heightfield are byte-identical with textures on or off. Live OSM changes over
time, so a fresh acquisition gives different package_ids.
## 1. Build from live data (CLI path)

Run from the source root with Python 3.12. The first build downloads from
Overpass and Copernicus into `cache-<area>` under `MB_ROOT` (a fresh temp
directory unless `MB_ROOT` is already set). To replay offline, keep the same
`MB_ROOT`, set `MB_OFFLINE=1` and run the block again: it rebuilds from that
cache with network access forbidden. Set `MB_TEXTURES=0` to build untextured
(`--no-textures`); the default is textured.

```powershell
if (-not $env:MB_ROOT) { $env:MB_ROOT = Join-Path $env:TEMP ("map-builder-demo-" + [guid]::NewGuid().ToString("N")) }
New-Item -ItemType Directory -Force $env:MB_ROOT | Out-Null
@'
import copy, os, statistics, sys, time
from pathlib import Path
from map_builder.core.generate import PlanOptions, build_plan
from map_builder.core.geodesy import Area
from map_builder.core.pipeline import Settings, acquire, elevation_correction_note, plan_to_package

AREAS = {"pittsburgh": (Area(40.437, -80.016, 1200, 1000), "pittsburgh"),
         "munich": (Area(48.1395, 11.5764, 400, 400), "munich_altstadt")}

class NoNetwork:
    def fetch(self, url, *a, **k):
        raise RuntimeError("cache miss: " + url.split("?")[0])

root = Path(os.environ["MB_ROOT"]); root.mkdir(parents=True, exist_ok=True)
textures = os.environ.get("MB_TEXTURES", "1") != "0"
suffix = "" if textures else "-notex"
for key in sys.argv[1:]:
    area, name = AREAS[key]
    settings = Settings(cache_dir=str(root / f"cache-{key}"), terrain_spacing=10.0, dsm_correction=True)
    client = NoNetwork() if os.environ.get("MB_OFFLINE") == "1" else None
    grid, classified, sources = acquire(area, settings, **({"client": client} if client else {}))
    times = []
    for run in range(3):
        t = time.perf_counter()
        plan = build_plan(area, copy.deepcopy(grid), copy.deepcopy(classified), PlanOptions(seed=1),
                          dsm_correction=True)
        src = copy.deepcopy(sources)
        note = elevation_correction_note(plan.report["terrain_correction"])
        for s in src:
            if note and s.get("kind") == "elevation":
                s["processing"] = note
        _, result = plan_to_package(plan, str(root / f"{key}{suffix}.mbmap"), name, src, textures=textures,
                                    heightfield_spacing=2.0, created_utc="2026-11-20T00:00:00Z")
        times.append(time.perf_counter() - t)
        if not result.ok:
            raise RuntimeError(result.summary())
    print(key, result.summary(), "median build s:", round(statistics.median(times), 3))
'@ | Set-Content "$env:MB_ROOT\build.py"
$env:PYTHONPATH = (Get-Location).Path
py -3.12 "$env:MB_ROOT\build.py" munich pittsburgh
$sfx = if ($env:MB_TEXTURES -eq "0") { "-notex" } else { "" }
foreach ($k in "munich", "pittsburgh") {
    py -3.12 tools\mbmap_cli.py validate "$env:MB_ROOT\$k$sfx.mbmap"
    dotnet run -c Release --project examples\csharp\MbmapReader -- "$env:MB_ROOT\$k$sfx.mbmap"
}
```

If Overpass answers 429, 502 or 504, wait a minute and run the script again.
The acquired parts stay in the cache.

## 2. Build in headless Blender

In Blender, use the sidebar (**Area: Centre + size**, the values above,
**Copernicus GLO-30**, **Overpass API**, seed 1, **Content > Textures** on or
off), then **Generate Map**, **Export Map Package** and **Validate Package**.
For a headless run, set the same values on `bpy.context.scene.map_builder`
(`centre_lat` and `centre_lon` are text, e.g. `"40.437"`; `textures` is a
checkbox), set `export_path`, and call `bpy.ops.map_builder.generate()`,
`bpy.ops.map_builder.export()` and `bpy.ops.map_builder.validate()`. Start
Blender with `--online-mode`. Point **Cache folder** (`cache_dir`) at a copy of
`$env:MB_ROOT\cache-<area>` to build from the same data as the CLI: then
Blender exports the same passage probes (Munich 3, Pittsburgh 13), and both
presets validate `VALID` textured and untextured. Blender packages differ in
bytes from the CLI ones (Blender stores geometry as float32).

## 3. Renders, panel and viewer

```powershell
$blender = "C:\path\to\blender.exe"
$env:BLENDER_USER_RESOURCES = "$env:MB_ROOT\blender-profile"
& $blender --background --factory-startup --python-exit-code 1 `
    --python tools\demo\run_demo.py -- --preset docs\demo\v0.4.0\munich-altstadt-v040.json `
    --after "$env:MB_ROOT\munich.mbmap" --before "$env:MB_ROOT\munich-notex.mbmap" `
    --out "$env:MB_ROOT\demo-munich" --panel --mesa-blender "C:\path\to\blender-mesa\blender.exe"
& $blender --background --factory-startup --python-exit-code 1 `
    --python tools\demo\run_demo.py -- --preset tools\demo\presets\pittsburgh.json `
    --after "$env:MB_ROOT\pittsburgh.mbmap" --before "$env:MB_ROOT\pittsburgh-notex.mbmap" `
    --out "$env:MB_ROOT\demo-pittsburgh"
Remove-Item Env:\BLENDER_USER_RESOURCES
```

Build both with and without `MB_TEXTURES=0` first. `--before` renders the
same cameras from a second package. The v0.4.0 demo also rendered the Munich
cameras with the released `munich-altstadt-0.3.0.mbmap` as `--before`, for the
roof comparison. Rendering is Cycles CPU, 1280 x 720, 64 samples. All 28
renders and the panel together took 14 min 25 s, within the 30-minute budget.
To view a bundle (never port 8765):
`py -3.12 -m http.server 8793 --bind 127.0.0.1 --directory "$env:MB_ROOT\demo-munich\viewer"`.
## Attribution

Both packages and their `NOTICES.txt` carry the required credits. Ship or
display `NOTICES.txt` with any map you use.

- **OpenStreetMap:** (c) OpenStreetMap contributors,
  [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/);
  [copyright and attribution](https://www.openstreetmap.org/copyright).
- **Copernicus DEM GLO-30:** (c) DLR e.V. 2010-2014 and (c) Airbus Defence
  and Space GmbH 2014-2018, provided under COPERNICUS by the European Union
  and ESA; all rights reserved. Produced using Copernicus WorldDEM-30,
  (c) DLR e.V. 2010-2014 and (c) Airbus Defence and Space GmbH 2014-2018,
  provided under COPERNICUS by the European Union and ESA; all rights reserved.
- **Textures:** CC0 1.0, map-builder contributors; no attribution required.
