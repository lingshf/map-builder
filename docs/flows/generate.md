# Generate: source and failure flow

The report is Blender's **MapBuilder Report** text block. Online failures never
silently become synthetic or flat maps. Optional DSM mask/correction failure
warns and keeps the original surface model; required source failures stop.
Tagged roofs that cannot be built as tagged fall back with a named reason in
`provenance.roof_shape`; a gabled roof whose gable end is not representable
is cut by a vertical wall through that end (since v0.5.0) and falls back to
hipped only when that is not possible either. Each water body inside the
terrain becomes a flat water surface on a carved bed (since v0.5.0); a body
that cannot be built keeps water-coloured terrain cells and the report names
why. Style (since v0.6.0; default Stylized) is fixed here and reused at
export; it changes only materials, never geometry or collision. Textures
applies only to Classic, and only changes the viewport look here; the package
follows the setting at export.

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
  R -->|End not representable| Q[Vertical-cut gable end]
  R -->|No, even for a valid simple ring| U[Named fallback: hipped or flat]
  S --> Y{Water body inside the terrain?}
  Q --> Y
  U --> Y
  Y -->|Built| Z[Flat water surface, carved bed, bank keeps landcover colour]
  Y -->|Named fallback| ZF[Water-coloured terrain cells]
  Y -->|None| ST{Style?}
  Z --> ST
  ZF --> ST
  ST -->|Stylized, default| SP[Flat stylized palette, no textures]
  ST -->|Classic| V{Textures on?}
  V -->|Yes| W[CC0 textured materials and UVs]
  V -->|No| X[Plain colour materials]
  SP --> J{Build succeeds?}
  W --> J
  X --> J
  J -->|No| K[Roll back new data]
  K --> E
  J -->|Yes| L[New editable collection]
  L --> M[Read source and feature report]
```
