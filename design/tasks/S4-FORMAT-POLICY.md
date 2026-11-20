# S4-FORMAT-POLICY: publish the `.mbmap` format-stability policy

Owner: dev · sprint S4 · lane C · after S4-TEST-HYGIENE (hard: C# harness), after S4-PERF-PKG only for a
`package.py` edit · D57, D65, D101

## Background

Draft policy (D101, in [../roadmap.md](../roadmap.md#sprint-4-decisions)). The current validator already
rejects a different schema major and accepts any minor (`core/package.py:1436`). The frozen v0.3.0 Python and
C# readers accept 2.1 packages in CI (D57, D65). The simulator needs a written guarantee it can pin to.

## Scope

1. Add a "Compatibility and stability policy" section to `docs/PACKAGE_FORMAT.md` that matches D101: what may
   change in patch, minor and major versions; reader rules; deprecation; how `.mbcol`/`.mbhf` format numbers
   relate to the package major. Mark it **draft until the user confirms it at v1.0**. State today's limits as
   part of the policy (a minor may not relax them): every member listed in `files[]` with SHA-256 (unlisted
   files are an error in both readers); ≤ 64 entries; ≤ 1.5 GiB uncompressed; manifest ≤ 32 MiB; ratio ≤ 200;
   names ≤ 255 bytes; one GLB-stored buffer, no external or data-URI buffers; no `extensionsRequired`; the C#
   glTF caps (GLB ≤ 1 GiB, ≤ 8 M visual triangles, ≤ 1 M nodes, depth ≤ 64); every embedded image listed in
   `asset_notices[]`. Quote each limit from `core/package.py` / `MbmapReader.cs`, not from this doc.
1a. Replace the stale paragraph at the top of `docs/PACKAGE_FORMAT.md` ("The writer default stays 2.0.0 until
   the generator emits textures") and the 2.0.0 title and example: the current writer default is **2.1.0**
   (since #49) and stays 2.1.0 in this sprint.
2. Add a reader-side section to `docs/UNITY_CORE_HANDOFF.md`: pin major 2, ignore unknown fields.
3. Write policy tests against the real validator, plus the C# reader where cheap:
   * **positive future-minor fixture:** a 2.(current minor + 1).0 package with an unknown top-level manifest
     field, an extra member that is **listed in `files[]` with its SHA-256 and inside every limit above**, and
     glTF `extras` (no `extensionsRequired`), is accepted by the current validator **and by the frozen v0.3.0
     Python and C# readers** (D57, D65). If a frozen reader rejects any part (for example an unknown member
     role), that part is not additive under the policy: drop it from the fixture and write the rule down;
     never change a frozen reader;
   * a 3.0.0 package is rejected with the "unsupported schema major" error;
   * an unknown `.mbcol` format number is rejected.
   Any validator behaviour that differs from the policy is fixed in this task (after S4-PERF-PKG) or reported
   to the coordinator.

## Acceptance criteria

1. The policy text matches D101, and each rule has a test, a CI step or an explicit "documentation only" note.
2. The three cases above pass in Python. The current C# reader rejects the 3.0.0 package, and the **frozen**
   C# reader loads the positive future-minor fixture, both through the S4-TEST-HYGIENE shared build (one build
   per run, D92).
3. No change to the schema constant (stays 2.1.0), the sample or any written package. No validator change is
   made to "implement" a draft guarantee: a mismatch is reported to the coordinator.

## Performance considerations

None. Tests ≤ 5 s total (synthetic in-memory packages).

## Expected tests

`tests/test_format_policy.py` (new). C# cases reuse the S4-TEST-HYGIENE build helper.

## Conflict domain

Hard: `docs/PACKAGE_FORMAT.md` (new section, stale 2.0.0 paragraph), `docs/UNITY_CORE_HANDOFF.md` (new
section), `tests/test_format_policy.py` (new), and the C# test harness from S4-TEST-HYGIENE (use only; any edit
to `tests/test_csharp_parity.py` or the reader project is serialised after it: hard edge). Only if a
coordinator-approved behaviour change is needed: `core/package.py` (after S4-PERF-PKG).
