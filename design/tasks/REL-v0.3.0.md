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

Common release criteria, plus: each demo package (Pittsburgh and the S2-F2 preset) built with live Copernicus GLO-30 + Overpass via the CLI
and in headless Blender, `VALID`; a drone capsule (r = 1 m) passes under a real bridge, through
the real tunnel and beneath an elevated part (validator + C#). If the S2-F2 area decision fell back to option (c),
the elevated-part case uses the synthetic sample and the release notes say so.

**Assets (S2-F4):** besides the extension zip, the release attaches the real-data demo
`.mbmap` (GLB inside) for each preset, with ODbL attribution in the notes and the package.

## Performance considerations

Build time (excluding download) ≤ 120 s; triangles, objects and probe-check visits recorded in
`docs/DEMO.md` and VALIDATION.md. A miss is recorded with a profile and becomes a follow-up
task, not optimisation here.

## Conflict domain

Hard: version files, `CHANGELOG.md`, `docs/user/`, `docs/flows/`, `docs/demo/v0.3.0/`,
`docs/releases/v0.3.0.md`, `docs/DEMO.md` (new). Soft: VALIDATION. Runs alone.
