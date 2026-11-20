# S4-FORMAT-POLICY: publish the `.mbmap` format-stability policy

Owner: dev · sprint S4 · lane C · after S4-PERF-PKG · D57, D65, D101

## Background

Draft policy (D101, in [../roadmap.md](../roadmap.md#sprint-4-decisions)). The current validator already
rejects a different schema major and accepts any minor (`core/package.py:1436`). The frozen v0.3.0 Python and
C# readers accept 2.1 packages in CI (D57, D65). The simulator needs a written guarantee it can pin to.

## Scope

1. Add a "Compatibility and stability policy" section to `docs/PACKAGE_FORMAT.md` that matches D101: what may
   change in patch, minor and major versions; reader rules; deprecation; how `.mbcol`/`.mbhf` format numbers
   relate to the package major. Mark it **draft until the user confirms it at v1.0**.
2. Add a reader-side section to `docs/UNITY_CORE_HANDOFF.md`: pin major 2, ignore unknown fields.
3. Write policy tests against the real validator, plus the C# reader where cheap:
   * a 2.(current minor + 1).0 package with an unknown top-level manifest field, an unknown member and glTF
     `extras` is accepted;
   * a 3.0.0 package is rejected with the "unsupported schema major" error;
   * an unknown `.mbcol` format number is rejected.
   Any validator behaviour that differs from the policy is fixed in this task (after S4-PERF-PKG) or reported
   to the coordinator.

## Acceptance criteria

1. The policy text matches D101, and each rule has a test, a CI step or an explicit "documentation only" note.
2. The three cases above pass in Python. The C# reader is covered for the major-version rejection (one CLI
   run).
3. No change to the schema constant, the sample or any written package.

## Performance considerations

None. Tests ≤ 5 s total (synthetic in-memory packages).

## Expected tests

`tests/test_format_policy.py` (new).

## Conflict domain

Hard: `docs/PACKAGE_FORMAT.md` (new section), `docs/UNITY_CORE_HANDOFF.md` (new section),
`tests/test_format_policy.py` (new). Only if behaviour must change: `core/package.py` (after S4-PERF-PKG) and
`examples/csharp/MbmapReader/**` (serialise with S4-TEST-HYGIENE).
