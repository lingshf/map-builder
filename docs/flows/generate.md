# Generate: source and failure flow

The report is Blender's **MapBuilder Report** text block. Online failures never
silently become synthetic or flat maps. Optional DSM mask/correction failure
warns and keeps the original surface model; required source failures stop.
Tagged roofs that cannot be built as tagged fall back with a named reason in
`provenance.roof_shape`; a gabled roof whose gable end is not representable
falls back to hipped (since v0.4.0). The Textures setting only changes the
viewport look here; the package follows the setting at export.

```mermaid
flowchart TD
  A[Area and content] --> B[Choose sources]
  B --> C{Online sources?}
  C -->|Yes| D{Online allowed?}
  D -->|No| E[Show error]
  D -->|Yes| F[Fetch DEM and OSM]
  C -->|No| G[Read local files]
  F --> H{Inputs valid?}
  G --> H
  H -->|No| E
  H -->|Yes| N[Optional inferred DSM correction]
  N --> I[Generate scene plan]
  I --> R{Roof shape buildable for this footprint?}
  R -->|Yes| S[Roof as tagged: eligible non-rectangles use the straight skeleton]
  R -->|No, even for a valid simple ring| U[Named fallback: hipped or flat]
  S --> V{Textures on?}
  U --> V
  V -->|Yes| W[CC0 textured materials and UVs]
  V -->|No| X[Plain colour materials]
  W --> J{Build succeeds?}
  X --> J
  J -->|No| K[Roll back new data]
  K --> E
  J -->|Yes| L[New editable collection]
  L --> M[Read source and feature report]
```
