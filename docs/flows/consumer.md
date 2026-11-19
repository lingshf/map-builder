# Consumer handoff: preview, not simulator integration

This is the required loading sequence for an eventual adapter, not an already
delivered UI in the simulator. The reference reader exercises package checks.

```mermaid
flowchart TD
  A[Open mbmap ZIP] --> B[Check container bounds]
  B --> C[Check schema major]
  C --> D[Verify files and hashes]
  D --> E{Integrity valid?}
  E -->|No| F[Reject package]
  E -->|Yes| G[Accept package identity]
  G --> H[Load Core collision]
  G --> I[Load GLB presentation]
  H --> J[Check orientation and probes]
  I --> J
  J --> K{Checks pass?}
  K -->|No| F
  K -->|Yes| L[Show attribution]
  L --> M[Adapter and flight work pending]
```
