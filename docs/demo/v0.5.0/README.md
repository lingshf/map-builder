# v0.5.0 demo: rivers, banks and roof ends

Release-candidate assets rebuilt from the rebased REL-v0.5.0 head (after #77
and #81) on frozen v0.4.0 caches.

Both areas use the frozen v0.4.0 data caches (OSM and Copernicus GLO-30,
acquired 2026-11-20 UTC), replayed offline, so every difference below comes
from the code, not from new data. "Before" is the released v0.4.0 package
(same sha256 as the v0.4.0 release asset), "after" the v0.5.0 RC package, both
textured and seen from the same fixed cameras.
Every map image is a real Blender 4.2.23 Cycles **CPU** render (1280 x 720,
64 samples). The sidebar is a real Blender window captured with Mesa software
OpenGL, and the viewer images are the real three.js bundle in headless Edge.
No UI is mocked. To reproduce, see [docs/DEMO.md](../../DEMO.md). Cameras:
[pittsburgh-v050-preset.json](pittsburgh-v050-preset.json) and
[munich-v050-preset.json](munich-v050-preset.json).

The neutral terrain texture (S4-TEX-WATER, D99) changes the ground in every
pair: untagged ground that read green/tan in v0.4.0 now reads grey (S4-F4).

## Example 1: the river under the Fort Pitt Bridge (Pittsburgh `bridge-under`)

| v0.4.0 | v0.5.0 |
|---|---|
| ![v0.4.0: the river is terrain painted blue-green that follows the elevation dip, with a stepped edge](pittsburgh-bridge-under-v040.png) | ![v0.5.0: a flat blue water surface; piers reach into the water and the bank meets it cleanly](pittsburgh-bridge-under-v050.png) |

In v0.4.0 there was no water surface: the terrain was coloured, so the river
followed the dip in the elevation data. In v0.5.0 the river is its own flat
mesh (one of three `water:` objects in Pittsburgh) over a bed carved 1.5 m
below it, and it is collision class 5.

## Example 2: the bank (Pittsburgh `bank`)

| v0.4.0 | v0.5.0 |
|---|---|
| ![v0.4.0: water-coloured terrain climbs the bank in a saw-tooth](pittsburgh-bank-v040.png) | ![v0.5.0: the bank keeps its landcover colour down to the flat water line](pittsburgh-bank-v050.png) |

The bank camera looks at the north bank of the Monongahela by the Fort Pitt
Bridge, where S4-REVIEW found water-coloured terrain triangles above the water
(S4-F1). With S4-WATER-BANK the bank keeps its landcover colour. The green and
grey squares on the bank are landcover painted per 10 m cell (S4-F6, a
pre-existing limit).

## Example 3: the overview (Pittsburgh `overview`)

| v0.4.0 | v0.5.0 |
|---|---|
| ![v0.4.0 overview](pittsburgh-overview-v040.png) | ![v0.5.0 overview: the Monongahela and Ohio are flat blue surfaces](pittsburgh-overview-v050.png) |

## Example 4: vertical-cut gable ends (Munich)

| Camera | v0.4.0 | v0.5.0 |
|---|---|---|
| `vcut-2edge` (way 80965543) | ![v0.4.0: the gabled roofs whose ends could not be represented are built hipped](munich-vcut-2edge-v040.png) | ![v0.5.0: the same roofs get vertical gable walls at both ends](munich-vcut-2edge-v050.png) |
| `vcut-3edge` (way 80965639) | ![v0.4.0](munich-vcut-3edge-v040.png) | ![v0.5.0: a vertical gable wall cut across three edges](munich-vcut-3edge-v050.png) |
| `named-fallback` (way 79401261) | ![v0.4.0](munich-named-fallback-v040.png) | ![v0.5.0: still hipped, with the reason named in provenance](munich-named-fallback-v050.png) |
| `roofs` | ![v0.4.0](munich-roofs-v040.png) | ![v0.5.0](munich-roofs-v050.png) |
| `overview` | ![v0.4.0](munich-overview-v040.png) | ![v0.5.0](munich-overview-v050.png) |

The roof changes are small in each frame. `vcut-2edge` shows them most
clearly: several gables that v0.4.0 built hipped now have vertical end walls.
The `named-fallback` roof is still hipped in v0.5.0 (no end is representable
even with a vertical cut), and `provenance.roof_shape` names why.

### Roofs in numbers (Munich, 67 tagged non-flat)

| | v0.4.0 | v0.5.0 |
|---|---|---|
| Built as tagged | 29 (17/52 gabled) | **45** (33/52 gabled, 11/12 hipped, 1/1 skillion) |
| Fallback with a named reason | 34 | 22 (18 gabled -> hipped, 4 -> flat) |
| No named reason | 4 (S3-F1) | 0 |

Source: S4-REVIEW section 1.1. Mixed roof ends are covered by synthetic tests
only; no Munich roof has one.

## Known issue

`tools/floating_audit.py` still reports the disclosed pre-existing Pittsburgh
CLI singleton (`osm:way/537242388`) as `buried_collision` (S4-F8). All rebuilt
Munich packages and all rebuilt Blender packages are clean for
`floating_collision`, `water_above_bank`, and `water_buried`.

## The three.js viewer (v0.5.0, textured)

| Munich Altstadt | Pittsburgh |
|---|---|
| ![Viewer: Munich, 3 passage probes PASS](viewer-munich.png) | ![Viewer: Pittsburgh, flat blue rivers, 11 passage probes PASS](viewer-pittsburgh.png) |

## Real Blender interface

![Real Map Builder sidebar over the generated Munich map](panel.png)

The "Online access is disabled" line appears because the screenshot is taken
with online access off, after generation.

## Recorded evidence

Machine-readable: [evidence.json](evidence.json). Kit summaries:
[summary-munich.md](summary-munich.md), [summary-pittsburgh.md](summary-pittsburgh.md).

| Check | Munich Altstadt | Pittsburgh |
|---|---|---|
| package_id (textured) | `sha256:d191a94de5663d106bc89cde24f105af72e678941e2f8ebe38dcdcccc1762976` | `sha256:3124bbeeaf660cffe4f810fe0d7235608db2bfc86fd8d830e4c38c64fc3c1ead` |
| package_id (untextured) | `sha256:d526920678a4868e63ad3bdd6f0b4029d2da6bdf48d682d165d6f201dfe60e5d` | `sha256:c16cde538d489567d6feef26ce6a0364b646405814a3ed7dc272249c92d487fc` |
| Objects | 389: terrain 1, building 148, road 197, tunnel 26, vegetation 17 | 3296: terrain 1, water 3, building 987, road 258, bridge 33, tunnel 5, structure 6, vegetation 2000 |
| Collision triangles | 23,372; 57 degenerate (v0.4.0: 59) | 145,650 (288 water); 73 degenerate (v0.4.0: 76) |
| Build, textured, 3 runs | 3.297 / 3.260 / 3.325 s, **median 3.297 s** | 17.828 / 15.887 / 16.031 s, **median 16.031 s** |
| Build, untextured, 3 runs | 4.187 / 3.014 / 3.019 s, **median 3.019 s** | 15.029 / 15.197 / 15.334 s, **median 15.197 s** |
| Python validator | `VALID: 0 error(s), 1 warning(s)` (degenerate triangles) | `VALID: 0 error(s), 1 warning(s)` (degenerate triangles) |
| Passage probes | 3 exported, all PASS; 26 blocked and reported | 11 exported, all PASS; 31 blocked and reported (v0.4.0: 13 and 29) |
| C# reference reader | `OK`, 3/3 PASS, 0 `mb_id` warnings | `OK`, 11/11 PASS, 0 `mb_id` warnings |
| Headless Blender, generate + export | textured and untextured `VALID` (56 degenerate); C# `OK`, 3/3 PASS, same probe ids as the CLI | textured and untextured `VALID` (71 degenerate); C# `OK`, 11/11 PASS, same probe ids as the CLI; export 23.3 s textured, 19.4 s untextured |
| CPU renders | 10 renders + panel: 268 s | 6 renders: 150 s |

All renders together took 7 min 0 s on the CPU (budget 30 min). Each CLI
package was built 3 times and the runs were byte-identical. The frozen caches
were hashed before and after every build and did not change. The two
Pittsburgh probes that v0.4.0 exported and v0.5.0 does not
(`osm:way/11950069:under`, `osm:way/121593794:deck`) are listed in
`passage_probes_blocked`; see the [release notes](../../releases/v0.5.0.md).

## Release asset candidates

Built from the RC (preliminary until S4-COL-FLOAT); only the PNGs, summaries,
the camera presets, the evidence and this README are committed. The release
notes list sizes and package_ids.

| Asset | Path | Textures | sha256 |
|---|---|---|---|
| `munich-altstadt-0.5.0.mbmap` | CLI | on | `49C42B79F4C3A8C72F0AF2188F309350CEE268232DF32603C63401206AAA72D8` |
| `pittsburgh-0.5.0.mbmap` | CLI | on | `BE4374B0EC3A02DDB58895AD0CFD4E80E7395365D67AAF5238B1E7463A547AAE` |
| `munich-altstadt-0.5.0-notex.mbmap` | CLI | off | `FDC561E9428F6058701B162D1E4BBC45F976B20AD3F88DD1371DB5564B29D68F` |
| `pittsburgh-0.5.0-notex.mbmap` | CLI | off | `DF89A8E7E405E07C321D6216EE49EDC477122AA240F92875DB7E715FBC2C4A3D` |
| `munich-altstadt-0.5.0-blender.mbmap` | headless Blender | on | `91A48B4C9AC4D58FF96A0A0ADE8552C62E3F3EDF1DBD36FD8876ABBA0FC69671` |
| `munich-altstadt-0.5.0-blender-notex.mbmap` | headless Blender | off | `0FA83406C096F9770DD87301CAD4B73C3E6F40EAA7790EB21963FCBC0BDF230A` |
| `pittsburgh-0.5.0-blender.mbmap` | headless Blender | on | `8E11533D27836DC522118EFFE639FD5704D219730154523B66C047535608CF7F` |
| `pittsburgh-0.5.0-blender-notex.mbmap` | headless Blender | off | `C7BB0436CB6BE2080859F85CAA40E13EDBB18B8E35B9D076BFFBF44B4B4E9230` |
| `map_builder-0.5.0.zip` (local clean build from this head) | | | `075825556339EAFEA58496F7273D55E1E54AF09CC43BF055E2BB36DBCC0910D6` (886,813 bytes) |

**Credits:** (c) OpenStreetMap contributors, ODbL 1.0. Copernicus DEM
GLO-30 / WorldDEM-30: (c) DLR e.V. 2010-2014 and (c) Airbus Defence and Space
GmbH 2014-2018, provided under COPERNICUS by the European Union and ESA; all
rights reserved. Textures: CC0 1.0, map-builder contributors.
