# Fly-through check: export, validate, probe results

v0.2.0. Detail: [bridges, tunnels and passages](../user/structures.md).

```mermaid
flowchart TD
  A[Generate map] --> B[Read report counts]
  B --> C[Review blocked probes list]
  C --> D[Edit map collection]
  D --> E[Export Map Package]
  E --> F[Validate Package]
  F --> G{VALID, no errors?}
  G -->|No| H[Validation error, keep previous package]
  H --> I[Undo edit or regenerate]
  I --> D
  G -->|Yes| P{Any blocked or unchecked probe warning?}
  P -->|Yes| Q[Package was still written: do not fly, fix edit]
  Q --> I
  P -->|No| J[Run C# reference reader]
  J --> K{All probes checked and PASS?}
  K -->|Blocked or not checked| Q
  K -->|Yes| M[Open viewer, fly to probes]
  M --> N[Hand package to simulator adapter]
```

There are two kinds of missing or failing probe:

- **Generator omission:** a probe that is blocked when the map is generated is
  never exported. It is listed in `report.json` `passage_probes_blocked` with
  its blocker.
- **Export-time warning:** validation tests only the exported probes. A probe
  that an edit blocks (`passage probe N is blocked ...`), or that runs out of
  query budget (`... probes A..B were not checked`), is a **warning**. The
  package is still `VALID` and replaces the previous one.

Stop on either kind of warning, even when the package is `VALID`.
