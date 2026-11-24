# Export: final edits to package

No scene modifiers are destructively applied. Validation errors block package
replacement; warnings require review. The Textures setting at export decides
materials, UVs, embedded CC0 images and the asset notice together; collision is
the same either way. Water surfaces (since v0.5.0) are exported like other
objects: one GLB node and class 5 `water` collision each. Degenerate collision
triangles that a probe could hit are kept and listed per object in
`report.json` (`degenerate_objects`).

```mermaid
flowchart TD
  A[Select map collection] --> B[Edit ordinary meshes]
  B --> C[Choose output path]
  C --> D[Export Map Package]
  D --> E[Evaluate meshes and transforms]
  E --> F[Resolve stable identities]
  F --> G{Geometry supported?}
  G -->|No| H[Report export error]
  G -->|Yes| I[Bake shared triangles]
  I --> T{Textures on at export?}
  T -->|Yes| U[GLB with UVs and CC0 images]
  T -->|No| V[Untextured GLB]
  I --> J[Collision, same either way]
  U --> K[Manifest, asset notices and NOTICES]
  V --> K
  J --> K
  K --> L{Package validates?}
  L -->|No| H
  H --> M[Keep previous package]
  L -->|Yes| N[Atomic package replacement]
```
