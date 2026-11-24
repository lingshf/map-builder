# Developer guide

This guide describes main as audited at `44cde701123a78f2cf714663f0f4b8605cb1e19d`
(after the skeleton module merged). The pure core and headless CLI need CPython
3.11+ and use the standard library. Blender integration targets Blender 4.2 LTS;
the reference reader targets .NET 8 and uses C# 8-compatible code and
`System.Text.Json`.

## Repository map

| Path | Responsibility |
|---|---|
| `map_builder/core/` | Pure acquisition, geometry, packaging and validation; no `bpy` |
| `map_builder/blender/` | Panel, scene generation, evaluated mesh export and operators |
| `map_builder/blender_manifest.toml` | Blender extension metadata and permissions |
| `tools/mbmap_cli.py` | Local-file, generated-plan build and validation |
| `tools/demo/` | Presets, renders and package viewer |
| `tests/`, `tests/blender/`, `tests/fixtures/` | Python tests, headless integration, synthetic inputs |
| `examples/csharp/MbmapReader/` | Reference package consumer |
| `docs/`, `design/` | Guides and contract; roadmap, task decisions and acceptance criteria |
| `.github/workflows/` | Pull-request CI and tag-triggered release automation |

Use the [architecture overview](../architecture/README.md) to trace a feature
through the code; see [validation coverage](../VALIDATION.md) for known gaps.

## Verified local checks

Run from the repository root in PowerShell. These commands were run on the
audited Windows checkout; the Blender path is machine-specific. Replace it
on other machines (the substituted command is unverified until run there).

```powershell
py -3.12 -W error::ResourceWarning -m unittest discover -s tests -t .
dotnet run -c Release --project examples\csharp\MbmapReader -- examples\synthetic_sample.mbmap
& 'C:\tools\blender-4.2.23-windows-x64\blender.exe' --background --factory-startup --python-exit-code 1 --python tests\blender\run_integration.py -- "$env:TEMP\map-builder-doc-integration"
```

The first command covers unit and acceptance tests, including the CLI; the
second checks the committed package and probes; the third exercises the
actual Blender integration and writes test artifacts to the specified folder.
See the [CLI guide](../user/cli.md) for the verified fixture build and validate
commands and [installation](../user/install.md) for extension packaging.

CI runs the Python suite on 3.11 and 3.12, builds and validates a synthetic
package, and runs the C# reader, Python/C# capsule parity and tamper rejection.
Headless Blender and network acquisition are not PR CI jobs. Release automation
is tag-triggered; consult the workflow files for the exact current commands.

## Workflow and Definition of Done

The single Definition of Done, the merge gate and the operation permissions are in the [team charter](../../design/team-charter.md#4-definition-of-done) (§4 DoD, §6 permissions). Read your task's spec in the [Backlog](../../design/tasks/README.md) for its acceptance criteria. Use one branch and PR per task (D6); do not self-merge.

## Adding a feature type

1. Define scope, acceptance and limits in the task/design process. Inspect
   `core/osm.py` classification and existing unsupported-feature reporting;
   decide how tags and geometry reach a classified list.
2. Follow the stage seam: `core/generate.py` creates the plan and
   `core/structures.py` supplies shared context and probe finalization.
   Existing bridge, tunnel and passage modules illustrate separate stage
   functions. Reserve scene budgets before allocating geometry.
3. Produce an `ObjectSpec` with stable identity, class and provenance, and
   account for invalid or unsupported features. Ensure mesh winding and
   visual/collision binding follow the [package contract](../PACKAGE_FORMAT.md).
   Passage features need appropriately checked probes, not assumed clearance.
4. Exercise classification, geometry, limits, reports and export in focused
   tests, including the production path. Include Blender checks if the change
   affects Blender behavior, and document user-visible limits.
5. Review format implications against D12/D19: additive report fields are not
   automatically a schema bump; changed package semantics may require one.

Prefer the existing plain-function stages and explicit resource/work budgets
over an unnecessary feature registry (D18). Preserve deterministic behavior,
fail clearly on required data errors, and do not persist credentials. The
core must remain usable without Blender. Tests should be bounded by work rather
than wall-clock gates; see the DoD for the full conventions.

## Licence

Split licence (D13): any first-party file that imports `bpy` (`map_builder/blender/`, and the `tests/blender/`, `tools/demo/` and `docs/demo/` scripts) is GPL-3.0-or-later, as is `map_builder/__init__.py` (the add-on bootstrap) and the manifest; everything else we wrote is Apache-2.0. Exceptions: `map_builder/assets/textures/` stays CC0 and `tools/demo/viewer/vendor/` (three.js) stays MIT. New `.py`/`.cs`/`.js`/`.html` files need an SPDX header (`# SPDX-License-Identifier: ...` plus `# Copyright 2026 lingshf`); `tests/test_licence.py` enforces it. Keep `map_builder/LICENSE-*.txt` and `map_builder/NOTICE` identical to the root copies, because the extension zip ships only `map_builder/`.
