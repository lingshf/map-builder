# Real-data demo (v0.3.0)

How to rebuild and check the two v0.3.0 real-data maps, with the recorded
numbers. Images and the comparison are in the
[v0.3.0 demo](demo/v0.3.0/README.md). Raw evidence is in
[evidence.json](demo/v0.3.0/evidence.json).

| Preset | Area | Structures |
|---|---|---|
| `pittsburgh` | 40.437 N, 80.016 W, 1200 x 1000 m | Fort Pitt Bridge (double deck, piers), Fort Pitt Tunnel |
| `munich-altstadt` | 48.1395 N, 11.5764 E, 400 x 400 m | Elevated building part, Rid Passage (building passage), road tunnel, tagged roofs |

Presets: [tools/demo/presets/](../tools/demo/presets/). Options for both
areas: seed 1, DSM correction on, terrain spacing 10 m, heightfield 2 m,
`created_utc` fixed at `2026-11-20T00:00:00Z`.

## Recorded results (RC, main 5867f4c + release changes)

| | Munich Altstadt | Pittsburgh |
|---|---|---|
| package_id | `sha256:2caff942…0eea64` | `sha256:094fb730…846d16` |
| Objects | 389 | 3290 |
| Collision triangles (degenerate) | 22,608 (59) | 144,108 (76) |
| Passage probes exported / blocked | 3 / 26 | 13 / 29 |
| Probe-check visits (capsule work) | 2,648 | 121,457 |
| Build, excluding download, median of 3 | **3.499 s** | **18.704 s** |
| Live acquisition (Overpass + GLO-30) | 107 s | 127 s |
| Python validator | `VALID`, 1 warning | `VALID`, 1 warning |
| C# reference reader | `OK`, 3/3 probes PASS | `OK`, 13/13 probes PASS |
| Headless Blender (live generate + export) | `VALID` (385 objects, 1/1 probes PASS in C#) | `VALID` (3313 objects, 14/14 probes PASS in C#); fixed by S2-F6 (#37) |

The build target is 120 s or less, so both areas pass. Probe-check visits are
the capsule query work units that the validator counts (`WorkBudget`). The C#
reader counts them the same way. Live OSM changes over time, so a fresh
acquisition gives a different package_id: the Munich Blender build an hour
later had 385 objects instead of 389.

## 1. Build from live data (CLI path)

Run from the source root with Python 3.12. The first build downloads from
Overpass and Copernicus into `cache-<area>` under `MB_ROOT` (a fresh temp
directory unless `MB_ROOT` is already set). To replay offline, keep the same
`MB_ROOT`, set `MB_OFFLINE=1` and run the block again: it rebuilds from that
cache with network access forbidden.

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
        _, result = plan_to_package(plan, str(root / f"{key}.mbmap"), name, src,
                                    heightfield_spacing=2.0, created_utc="2026-11-20T00:00:00Z")
        times.append(time.perf_counter() - t)
        if not result.ok:
            raise RuntimeError(result.summary())
    print(key, result.summary(), "median build s:", round(statistics.median(times), 3))
'@ | Set-Content "$env:MB_ROOT\build.py"
$env:PYTHONPATH = (Get-Location).Path
py -3.12 "$env:MB_ROOT\build.py" munich pittsburgh
foreach ($k in "munich", "pittsburgh") {
    py -3.12 tools\mbmap_cli.py validate "$env:MB_ROOT\$k.mbmap"
    dotnet run -c Release --project examples\csharp\MbmapReader -- "$env:MB_ROOT\$k.mbmap"
}
```

If Overpass answers 429, 502 or 504, wait a minute and run the script again.
The acquired parts stay in the cache.

## 2. Build in headless Blender

In Blender, use the sidebar (**Area: Centre + size**, the values above,
**Copernicus GLO-30**, **Overpass API**, seed 1), then **Generate Map**,
**Export Map Package** and **Validate Package**. For a headless run, set the
same values on `bpy.context.scene.map_builder`, set `export_path`, and call
`bpy.ops.map_builder.generate()`, `bpy.ops.map_builder.export()` and
`bpy.ops.map_builder.validate()`. Start Blender with `--online-mode`. Both
presets validate `VALID`. Pittsburgh failed here before S2-F6 (#37) on one
downward-facing road triangle. Blender downloads fresh OSM data, so its object
and probe counts can differ from the cached CLI build.

## 3. Renders, panel and viewer

```powershell
$blender = "C:\path\to\blender.exe"
$env:BLENDER_USER_RESOURCES = "$env:MB_ROOT\blender-profile"
& $blender --background --factory-startup --python-exit-code 1 `
    --python tools\demo\run_demo.py -- --preset tools\demo\presets\munich-altstadt.json `
    --after "$env:MB_ROOT\munich.mbmap" --out "$env:MB_ROOT\demo-munich" `
    --panel --mesa-blender "C:\path\to\blender-mesa\blender.exe"
& $blender --background --factory-startup --python-exit-code 1 `
    --python tools\demo\run_demo.py -- --preset tools\demo\presets\pittsburgh.json `
    --after "$env:MB_ROOT\pittsburgh.mbmap" --out "$env:MB_ROOT\demo-pittsburgh"
Remove-Item Env:\BLENDER_USER_RESOURCES
```

Add `--before <package>` to render the same cameras for a comparison. The
v0.3.0 demo used the v0.1.0 package of the same acquisition for the passage,
and a build with every `roof:*` tag removed for the roofs; see
[why not v0.2.0](demo/v0.3.0/README.md). Rendering is Cycles CPU, 1280 x 720,
64 samples. All 14 renders and the panel together took 9 min 28 s, within the
30-minute budget. To view a bundle (never port 8765):
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
