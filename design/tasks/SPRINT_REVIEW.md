# Sprint review (common definition)

Decision D17: remaining v2 has **two sprints**; each ends with **one** small `sprint-N-review`
task that combines the demo, the design/milestone review, the test audit and the GitHub
pre-release. No release per task. Owner: Dev runs the demo and release; Design writes the review.

## Steps

1. **Demo (Dev):** build the demo-area package with the CLI, then run
   `tools/demo/run_demo.py --preset <area> --before <previous release's demo.mbmap> --after
   <new demo.mbmap> --out out/v0.N.0` (S1-DEMOKIT). No new tooling in review tasks.
2. **Review + test audit (Design):** in `design/reviews/sprint-N.md`:
   * design conformance — code follows the task docs and decisions (deviations with file:line);
   * SOLID without over-engineering — single-responsibility modules, no duplicated geometry,
     no speculative abstractions;
   * performance — fixture build, unit suite, PR CI (≤ 10 min), demo build time vs targets;
   * test audit — every acceptance criterion maps to a test or recorded run; probes PASS in
     Python and the C# reader; Blender headless checks; no tests that restate constants;
   * docs consistent (PACKAGE_FORMAT, README Limits, UNITY_CORE_HANDOFF, VALIDATION).
   Problems become `design/tasks/SN-Fn.md` rows: release blockers are fixed before the tag,
   the rest go to the next sprint.
3. **Release (Dev):** bump `map_builder/__init__.py` and `blender_manifest.toml` to `0.N.0`,
   write `docs/releases/v0.N.0.md` (what's new, 2–3 examples from `summary.md` with input area,
   command and before/after images, known limits, **How to try it**: Install from Disk → allow
   online access → enter area → *Generate Map* → *Export Map Package* → *Validate Package*, plus
   the CLI one-liner), merge, push tag `v0.N.0` (release workflow attaches the zip), then
   `gh release upload`: `demo-v0.N.0.mbmap`, `demo-v0.N.0.glb`, the PNGs, `viewer.zip`,
   `NOTICES.txt`.

## Acceptance criteria

* Pre-release `v0.N.0` exists with all assets; the zip installs in Blender 4.2.23 and the panel
  appears; the attached `.mbmap` is `VALID` with the CLI and the C# reader.
* Every example's command reproduces its "after" image.
* Every passage probe in the demo package PASSes (or is explained in the notes).
* Review file written; findings filed as tasks; OSM and Copernicus attribution in notes and viewer.

## Conflict domain

Hard: version files, `docs/releases/v0.N.0.md`, `design/reviews/`. Soft: `README.md`,
`docs/VALIDATION.md`. Runs after all sprint code is merged; nothing else merges between its
version PR and the tag.
