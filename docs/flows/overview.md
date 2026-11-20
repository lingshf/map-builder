# Map Builder overview

v0.4.0 preview. Detail: [generation](generate.md), [export](export.md),
[fly-through check](flythrough.md), [consumer handoff](consumer.md).

```mermaid
flowchart TD
  A[Install extension zip] --> B[Enable Map Builder]
  B --> C[Open sidebar]
  C --> D[Choose small area]
  D --> E[Choose sources]
  E --> T[Textures on or off]
  T --> F[Generate map]
  F --> G[Read report]
  G --> H[Edit map collection]
  H --> I[Export package]
  I --> J[Validate package]
  J --> K[Inspect GLB]
  J --> P[Check passage probes]
  P --> L[Check reference reader]
  L --> M[Consumer adapter pending]
```
