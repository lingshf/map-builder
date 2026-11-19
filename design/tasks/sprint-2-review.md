# sprint-2-review: v0.3.0 "passages, roofs and the real-data v2 demo" (end of v2)

Sprint S2 · depends on S2-ELEV, S2-ROOF merged and sprint-1-review done · follows
[SPRINT_REVIEW.md](SPRINT_REVIEW.md) · includes the end-of-v2 review (former M5-R) and the
real-data demo (former M5-DEMO)

## Examples (2–3)

1. Demo area (D26): elevated part / building passage — before (v0.2.0) / after, plus its
   probe result.
2. Roof shapes close-up: before (v0.2.0 flat fallbacks) / after.
3. Full drone-eye tour: under a bridge, through the tunnel, beneath an elevated part
   (renders + viewer).

## Additional acceptance criteria (end of v2)

1. Demo package built with live Copernicus GLO-30 + Overpass, with the CLI and in headless
   Blender; `VALID`; ≥ 1 bridge and ≥ 1 tunnel; a drone capsule (r = 1 m) passes under a real
   bridge, through the real tunnel and beneath an elevated part (validator + C# results).
2. Build time (excluding download) ≤ 120 s; triangles, objects, probe-check visits recorded in
   `docs/DEMO.md` (new: reproduce steps, numbers, attribution) and VALIDATION.md. A miss is
   recorded with a profile and becomes a follow-up task, not optimisation here.
3. End-of-v2 review additionally covers: D17–D26 honoured or superseded; all `S1-Fn` closed or
   deferred; dead code and stubs removed; v0.1.0–v0.3.0 releases each have their assets;
   UNITY_CORE_HANDOFF.md, PROJECT_BRIEF.md, README Limits updated; open items for v3 (railway
   structures if D25 stays, LOD, textures, licence D13); go/no-go for closing v2.

## Conflict domain

As SPRINT_REVIEW.md with N = 3, plus `docs/DEMO.md` (new). Runs alone.
