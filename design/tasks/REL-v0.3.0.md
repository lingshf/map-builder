# REL-v0.3.0: "passages, roofs and the real-data v2 demo" (end of v2)

Owner: release manager · depends on S2-ELEV, S2-ROOF, S1-F1, S1-F2 merged and on the
[S2-REVIEW](../reviews/S2-REVIEW.md) findings S2-F1, S2-F2, S2-F3 (D48: review first, then one
RC) · follows [SPRINT_CLOSE.md](SPRINT_CLOSE.md) · demo areas: D26 Pittsburgh (bridges,
tunnels) + the S2-F2 preset (elevated parts, passages, roofs)

## Scope

RC PR: version 0.3.0, CHANGELOG, `docs/user/` (elevated parts, building passages, roof shapes),
`docs/flows/`, `docs/demo/v0.3.0/` (before = v0.2.0 package), `docs/releases/v0.3.0.md`, and
`docs/DEMO.md` (reproduce steps, numbers, attribution).

## Examples (2–3)

1. Elevated part / building passage — before (v0.2.0) / after, with its probe result.
2. Roof shapes close-up — before (flat fallbacks) / after.
3. Drone-eye tour: under a bridge, through the tunnel, beneath an elevated part.

## Acceptance criteria

Common release criteria, plus the branch matching the S2-F2 outcome (D49):

* **S2-F2 outcome A (second area found):** both real-data packages (Pittsburgh and the S2-F2
  preset) are built with live Copernicus GLO-30 + Overpass via the CLI and in headless Blender,
  `VALID`. A drone capsule (r = 1 m) passes under a real bridge and through the real tunnel
  (Pittsburgh) and beneath a real elevated part or passage (S2-F2 preset), in the validator and
  in C#. **Assets (S2-F4):** besides the extension zip, both real-data `.mbmap` files (GLB
  inside) are attached.
* **S2-F2 outcome B (fallback (c)):** only Pittsburgh is required as real data: built as above,
  `VALID`, bridge and tunnel probes PASS in the validator and in C#. The elevated-part/passage
  case uses the committed synthetic sample (`1048:under`, `1098:passage` PASS in Python and C#).
  **Assets (S2-F4):** the extension zip and the Pittsburgh `.mbmap` only. The release notes and
  `docs/DEMO.md` state plainly that elevated parts, building passages and roof shapes are
  evidenced on synthetic data only, and link the S2-F2 search record.

Either way, real-data packages carry ODbL attribution in the notes and the package.

## Performance considerations

Build time (excluding download) ≤ 120 s; triangles, objects and probe-check visits recorded in
`docs/DEMO.md` and VALIDATION.md. A miss is recorded with a profile and becomes a follow-up
task, not optimisation here.

## Conflict domain

Hard: version files, `CHANGELOG.md`, `docs/user/`, `docs/flows/`, `docs/demo/v0.3.0/`,
`docs/releases/v0.3.0.md`, `docs/DEMO.md` (new). Soft: VALIDATION. Runs alone.
