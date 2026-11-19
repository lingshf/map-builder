# Sprint close (common definition)

Decisions D17, D28, D29. Each sprint closes in this fixed order; nothing else merges between
the RC merge and the tag.

1. **RC PR — `REL-v0.N.0`** (owner: release manager). One PR that contains:
   * version bump in `map_builder/__init__.py` and `map_builder/blender_manifest.toml`;
   * `CHANGELOG.md` entry; user docs under `docs/user/`; user flows under `docs/flows/`
     (install → generate → export → validate, plus each new feature);
   * demo under `docs/demo/v0.N.0/`, produced with `tools/demo/run_demo.py` (S1-DEMOKIT) on the
     sprint's preset (D26 Pittsburgh from v0.2.0 on): panel screenshot, 2–3 feature examples
     with input area, command and before/after renders from identical cameras, viewer bundle,
     `summary.md`;
   * release notes `docs/releases/v0.N.0.md` with **How to try it** (Install from Disk → allow
     online access → area → *Generate Map* → *Export Map Package* → *Validate Package*, CLI
     one-liner) and OSM/Copernicus attribution.
   Proposes the tag commit (the RC merge SHA).
2. **Demo check** (release manager): the demo assets and commands reproduce on the RC merge.
3. **Milestone review + test audit — `S<N>-REVIEW`** (owner: Design), after the RC merges.
   Findings become `design/tasks/S<N>-Fn.md` rows; release blockers are fixed (and the RC
   re-cut) before the tag, the rest go to the next sprint.
4. **Retro** (coordinator).
5. **Tag + GitHub pre-release** `v0.N.0` on the proposed commit: the release workflow (#13)
   attaches the extension zip; the release manager uploads the demo `.mbmap` + `.glb`, renders,
   viewer zip and `NOTICES.txt`.

## Acceptance criteria (every release)

* Pre-release exists with all assets; the zip installs in Blender 4.2.23 and the panel appears;
  the attached `.mbmap` is `VALID` with the CLI and the C# reader.
* Every example's command reproduces its "after" image; every passage probe in the demo package
  PASSes (or is explained in the notes).
* The design review is written and its blocker findings are closed.

## Performance considerations

Demo rendering ≤ 30 min unattended CPU per release (≤ 6 cameras × before/after, 64 samples);
never run in PR CI. The release workflow runs only on tags.
