# Consumer handoff: preview, not simulator integration

This is the required loading sequence for an eventual adapter, not an already
delivered UI in the simulator. The reference reader exercises package checks.
Schema 2.1 textures are optional: a 2.0 reader ignores the UVs, images and
`asset_notices`, and collision does not depend on them.

```mermaid
flowchart TD
  A[Open mbmap ZIP] --> B[Check container bounds]
  B --> C[Check schema major]
  C --> D[Verify files and hashes]
  D --> E{Integrity valid?}
  E -->|No| F[Reject package]
  E -->|Yes| G[Accept package identity]
  G --> H[Load Core collision]
  G --> I[Load GLB presentation, textures optional]
  H --> J[Check orientation and probes]
  I --> J
  J --> K{Checks pass?}
  K -->|No| F
  K -->|Yes| L[Show data and CC0 asset attribution]
  L --> M[Adapter and flight work pending]
```
