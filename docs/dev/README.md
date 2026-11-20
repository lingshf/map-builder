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

Read the relevant task and [Definition of Done](../../design/tasks/README.md#definition-of-done-every-code-task-d28).
Use one branch and PR per feature or documentation batch (D6), with acceptance
evidence, user-visible changes, and relevant performance information. Complex
geometry work defines acceptance cases first. Code tasks update their task row.
Where applicable regenerate the sample rather than hand-merging it (D20), run
headless Blender, and update the contract and validation documentation.

Every PR, **including documentation-only PRs**, needs green CI and an
independent reviewer's `VERDICT: APPROVED` on the exact head; only the
coordinator authorizes merging (D33, D34, D38, D47). The coordinator gate
also checks mergeability and freshness (D53). Do not self-merge. Probe or
query-accounting changes require real Pittsburgh results from both validators
(D47). Check the task-specific criteria for details, rather than treating this
summary as a replacement for them.

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
