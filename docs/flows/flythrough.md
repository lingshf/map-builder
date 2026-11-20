# Fly-through check: export, validate, probe results

v0.2.0. Detail: [bridges, tunnels and passages](../user/structures.md).

```mermaid
flowchart TD
  A[Generate map] --> B[Read report counts]
  B --> C[Review blocked probes list]
  C --> D[Edit map collection]
  D --> E[Export Map Package]
  E --> F[Validate Package]
  F --> G{Every exported probe clear?}
  G -->|No| H[Validation error, keep previous package]
  H --> I[Undo edit or regenerate]
  I --> D
  G -->|Yes| J[Run C# reference reader]
  J --> K{All probes checked and PASS?}
  K -->|Not checked| L[Budget warning, not a pass]
  K -->|Yes| M[Open viewer, fly to probes]
  M --> N[Hand package to simulator adapter]
```

A blocked probe is never exported. It is listed in `report.json`
`passage_probes_blocked` with its blocker. Validation tests only the exported
probes, so read the report as well.
