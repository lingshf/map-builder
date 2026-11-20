# v0.4.0 demo: real roofs and textures

**Release candidate; not a published release.** Both areas use the real OSM
and Copernicus GLO-30 data acquired for v0.3.0 on 2026-11-20 (UTC), replayed
offline, so every difference below comes from the code, not from new data.
Every map image is a real Blender 4.2.23 Cycles **CPU** render (1280 x 720,
64 samples). The sidebar is a real Blender window captured with Mesa software
OpenGL, and the viewer images are the real three.js bundle in headless Edge.
No UI is mocked. To reproduce, see [docs/DEMO.md](../../DEMO.md).

Each Munich camera has three images, so each change is shown on its own:

- **roofs**: v0.3.0 vs v0.4.0 with `--no-textures` (only the roofs differ);
- **textures**: v0.4.0 with `--no-textures` vs v0.4.0 textured (same v0.4.0
  geometry; only the appearance differs. Collision and heightfield are
  byte-identical; the GLB, `manifest.json` and `NOTICES.txt` change).

The close-up cameras ([munich-altstadt-v040.json](munich-altstadt-v040.json))
are aimed at the buildings named in the S3 review.

## Example 1: gabled roofs on non-rectangular footprints (way 91268712)

| v0.3.0 (flat fallback) | v0.4.0, no textures | v0.4.0, textured |
|---|---|---|
| ![v0.3.0: the non-rectangular buildings have flat roofs](munich-gabled-skeleton-v030.png) | ![v0.4.0: the same buildings get gabled roofs that follow the footprint](munich-gabled-skeleton-v040-notex.png) | ![v0.4.0 textured: tiled gabled roofs and plastered facades](munich-gabled-skeleton-v040.png) |

## Example 2: hipped roofs (way 79401262)

| v0.3.0 | v0.4.0, no textures | v0.4.0, textured |
|---|---|---|
| ![v0.3.0: flat roofs](munich-hipped-skeleton-v030.png) | ![v0.4.0: hipped roofs on every footprint edge](munich-hipped-skeleton-v040-notex.png) | ![v0.4.0 textured](munich-hipped-skeleton-v040.png) |

## Example 3: a gable that falls back to hipped (way 91268710)

| v0.3.0 | v0.4.0, no textures | v0.4.0, textured |
|---|---|---|
| ![v0.3.0: flat](munich-gabled-fallback-v030.png) | ![v0.4.0: built hipped, because the ridge would meet the gable edge outside it](munich-gabled-fallback-v040-notex.png) | ![v0.4.0 textured](munich-gabled-fallback-v040.png) |

This building is tagged gabled. Its gable end cannot be represented, so it is
built **hipped** and `provenance.roof_shape` says why. 30 Munich gables do
this.

## Example 4: the roofs view and the overview

| | v0.3.0 | v0.4.0, no textures | v0.4.0, textured |
|---|---|---|---|
| `roofs` | ![v0.3.0](munich-roofs-v030.png) | ![v0.4.0 untextured](munich-roofs-v040-notex.png) | ![v0.4.0 textured](munich-roofs-v040.png) |
| `overview` | ![v0.3.0](munich-overview-v030.png) | ![v0.4.0 untextured](munich-overview-v040-notex.png) | ![v0.4.0 textured](munich-overview-v040.png) |

### Roofs in numbers (Munich, 148 buildings, 67 tagged non-flat)

| | v0.3.0 | v0.4.0 |
|---|---|---|
| Built as tagged (same geometric checker) | 1 | **29** (17/52 gabled, 11/12 hipped, 1/1 skillion) |
| Fallback with a named reason | | 30 gabled -> hipped, 4 -> flat |
| Not counted, **no named reason** | | 4 near-rectangle analytic gables (S3-F1) |

29/67 meets the D82 floor but not the original goal of 40 or more. Skillion
was already built on any footprint in v0.3.0. Source: the S3 review, section
1.1.

## Example 5: textures on and off, Pittsburgh

| Camera | `--no-textures` | Textured |
|---|---|---|
| `overview` | ![untextured](pittsburgh-overview-v040-notex.png) | ![textured terrain, roads and roofs](pittsburgh-overview-v040.png) |
| `dsm-ground` | ![untextured](pittsburgh-dsm-ground-v040-notex.png) | ![textured](pittsburgh-dsm-ground-v040.png) |
| `bridge-under` | ![untextured](pittsburgh-bridge-under-v040-notex.png) | ![textured: concrete deck and piers](pittsburgh-bridge-under-v040.png) |
| `tunnel-portal` | ![untextured](pittsburgh-tunnel-portal-v040-notex.png) | ![textured](pittsburgh-tunnel-portal-v040.png) |

Untextured Pittsburgh is byte-identical to v0.3.0 apart from `manifest.json`
(Pittsburgh has no roofs that v0.4.0 builds differently), so here the left
column is also the v0.3.0 look. That is not true for Munich, where
`--no-textures` keeps the new v0.4.0 roofs.

## The three.js viewer (textured)

| Munich Altstadt | Pittsburgh |
|---|---|
| ![Viewer: textured Munich, 3 passage probes PASS](viewer-munich.png) | ![Viewer: textured Pittsburgh, 13 passage probes PASS](viewer-pittsburgh.png) |

## Real Blender interface

![Real Map Builder sidebar with the new Textures checkbox, over the Munich map](panel.png)

**Content > Textures** is on. The "Online access is disabled" line appears
because the screenshot is taken with online access off, after generation.

## Recorded evidence

Machine-readable: [evidence.json](evidence.json). Kit summaries:
[summary-munich.md](summary-munich.md), [summary-pittsburgh.md](summary-pittsburgh.md).

| Check | Munich Altstadt | Pittsburgh |
|---|---|---|
| package_id (textured) | `sha256:178c1328e90e3d83a3a38ac2144e12a4c81726a768bd0b62398927647ac3ec3f` | `sha256:c605727a7037d60fde16604526208c5559da267eebc7f45362adabc80c5d1b40` |
| package_id (`--no-textures`) | `sha256:b4b8a9a0f33b82fc21bdfcef4b59b1b561590baf2b7b5c61f1bcc8a5e9c3a37a` | `sha256:69cf9a3a84d4c535c0f457587aa632d442a3a63d2b0dff60b1452a6ec0703b45` |
| Objects | 389: terrain 1, building 148, road 197, tunnel 26, vegetation 17 | 3290: terrain 1, building 987, road 258, bridge 33, tunnel 5, structure 6, vegetation 2000 |
| Collision triangles | 23,378 (v0.3.0: 22,608); 59 degenerate | 144,108; 76 degenerate |
| Build, textured, 3 runs | 4.313 / 4.304 / 4.027 s, **median 4.304 s** | 19.814 / 20.020 / 20.179 s, **median 20.020 s** |
| Build, `--no-textures`, 3 runs | 3.596 / 3.585 / 3.657 s, **median 3.596 s** | 18.235 / 18.489 / 18.894 s, **median 18.489 s** |
| Build, v0.3.0 code, 3 runs | median 3.744 s | 18.535 / 18.919 / 19.198 s, **median 18.919 s** |
| Python validator (strict) | `VALID: 0 error(s), 1 warning(s)` (degenerate triangles) | `VALID: 0 error(s), 1 warning(s)` (degenerate triangles) |
| Passage probes | 3 exported, all PASS; 26 blocked and reported | 13 exported, all PASS; 29 blocked and reported |
| C# reference reader | `OK`, 3/3 PASS, 0 `mb_id` warnings | `OK`, 13/13 PASS, 0 `mb_id` warnings |
| Headless Blender, generate + export | textured and untextured `VALID`; C# `OK`, 3/3 PASS, same probe ids as the CLI | textured and untextured `VALID`; C# `OK`, 13/13 PASS, same probe ids as the CLI; export 28.0 s textured, 21.4 s untextured |
| CPU renders | roofs 10 + panel: 329 s; textures 10: 306 s | 8 renders: 231 s |
| Release zip, clean-profile install (G4) | `map_builder-0.4.0.zip` built from the RC passes `extension validate`; in an empty `BLENDER_USER_RESOURCES` it imports as (0, 4, 0) and the Blender harness reports `OK: 0 failure(s)` (239 PASS) | (same zip) |

All renders together took 14 min 25 s on the CPU (budget 30 min). Each CLI
package was built 3 times and the runs were byte-identical. The v0.3.0 code on
the same caches rebuilds the released v0.3.0 assets byte-for-byte. Textured
packages embed 5 images (511,404 bytes); `.mbcol` and the heightfield are
byte-identical with textures on or off. The Blender scene count is one higher
than the map's object count because it includes the factory-startup cube.

## Release asset candidates

Built from the RC; only the PNGs, summaries, the camera preset, the evidence
and this README are committed. The release notes list sizes and package_ids.

| Asset | Path | Textures | sha256 |
|---|---|---|---|
| `munich-altstadt-0.4.0.mbmap` | CLI | on | `55655D90ED08E781C9354A7753F0F86F3AE8665FE9BE4BF940F5744C79A006D3` |
| `pittsburgh-0.4.0.mbmap` | CLI | on | `6D3DCCF74C3A956FB8735F0221C30A4B8F527498238065DF387F8C5118ECEBF7` |
| `munich-altstadt-0.4.0-notex.mbmap` | CLI | off | `F9EF4EA954FBEC0D55C83C33D07F01DCEC5690A6E4C4676DCE2FFC506B4BDF23` |
| `pittsburgh-0.4.0-notex.mbmap` | CLI | off | `F8C924B4A352A3F6B86915500029C2EA13426CE2F9674912148DD15C2D070A92` |
| `munich-altstadt-0.4.0-blender.mbmap` | headless Blender | on | `047EA375183ED4F604F3F807EFCA2591DCC636468E7D257511FDC8B3525C4754` |
| `munich-altstadt-0.4.0-blender-notex.mbmap` | headless Blender | off | `212CA300709D715A6348BE856C6B577F6B64EDF80823ED222C85C643012AAB80` |
| `pittsburgh-0.4.0-blender.mbmap` | headless Blender | on | `CA2641553778A7F8FCA3B299B82F2AEDE1BBEFE614FFD9A4F5923DF7F2BBA253` |
| `pittsburgh-0.4.0-blender-notex.mbmap` | headless Blender | off | `DDB921F0B65327593BEF5C4258BF85EE37FA7496D40976B2C133EE19DC87FC6C` |
| `map_builder-0.4.0.zip` (RC build; the release workflow rebuilds it from the tag) | | | `469AA5D7FD340C096A16832829AD16F88DAD9B8216A550C8D9CDB015AD671AAF` |

**Credits:** (c) OpenStreetMap contributors, ODbL 1.0. Copernicus DEM
GLO-30 / WorldDEM-30: (c) DLR e.V. 2010-2014 and (c) Airbus Defence and Space
GmbH 2014-2018, provided under COPERNICUS by the European Union and ESA; all
rights reserved. Textures: CC0 1.0, map-builder contributors.
