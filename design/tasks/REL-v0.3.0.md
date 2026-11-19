# REL-v0.3.0: "passages, roofs and the real-data v2 demo" (end of v2)

Owner: release manager · depends on S2-ELEV, S2-ROOF merged, S1-REVIEW done · follows
[SPRINT_CLOSE.md](SPRINT_CLOSE.md) · demo area D26 (Pittsburgh)

## Scope

RC PR: version 0.3.0, CHANGELOG, `docs/user/` (elevated parts, building passages, roof shapes),
`docs/flows/`, `docs/demo/v0.3.0/` (before = v0.2.0 package), `docs/releases/v0.3.0.md`, and
`docs/DEMO.md` (reproduce steps, numbers, attribution).

## Examples (2–3)

1. Elevated part / building passage — before (v0.2.0) / after, with its probe result.
2. Roof shapes close-up — before (flat fallbacks) / after.
3. Drone-eye tour: under a bridge, through the tunnel, beneath an elevated part.

## Acceptance criteria

Common release criteria, plus: package built with live Copernicus GLO-30 + Overpass via the CLI
and in headless Blender, `VALID`; a drone capsule (r = 1 m) passes under a real bridge, through
the real tunnel and beneath an elevated part (validator + C#).

## Performance considerations

Build time (excluding download) ≤ 120 s; triangles, objects and probe-check visits recorded in
`docs/DEMO.md` and VALIDATION.md. A miss is recorded with a profile and becomes a follow-up
task, not optimisation here.

## Conflict domain

Hard: version files, `CHANGELOG.md`, `docs/user/`, `docs/flows/`, `docs/demo/v0.3.0/`,
`docs/releases/v0.3.0.md`, `docs/DEMO.md` (new). Soft: VALIDATION. Runs alone.
