# S4-TEST-HYGIENE: hermetic C# tests, no leaked handles, a smaller bridge test

Owner: dev · sprint S4 · any lane · D92 · closes S3-F2, S3-F3

## Background (measured)

* With a private feed in the user-level NuGet config, the local suite gets **2 `setUpClass` errors** in
  `tests.test_csharp_parity` (`dotnet build`, NU1900 as error). When two suites run in parallel, the shared
  `bin/obj` output gives CS2012. Each C# test class runs its own `dotnet build` (`tests/test_csharp_parity.py`
  lines 70 and 135).
* `tests/test_demo_bundle.py:53` uses `json.load(open(...))`. The finalizer ResourceWarning escapes
  `-W error::ResourceWarning` (S3-F2).
* The 45° bridge-crossing test takes 2.82 s on this host and 5.47 s on others (S3-F3).

## Scope (D92)

1. Add a repo-local `NuGet.config` (`<clear/>` + nuget.org) used by the reader project and the tests. Do not
   treat NU1900 as an error in test builds.
2. Build the reader once per test run under a file lock, into a per-run output directory. Every C# test class
   reuses it.
3. Close the leaked handle, and make the suite fail on any finalizer ResourceWarning (for example, a test-run
   hook that turns `sys.unraisablehook` events into failures).
4. Shrink the bridge-crossing input while keeping its geometric assertion (D39).

## Acceptance criteria

1. With a user-level NuGet config pointing at an unreachable feed (simulated in the test or documented as a
   manual check in the PR), the suite has 0 errors.
2. Two full suites started in parallel on one checkout both pass (manual check recorded in the PR).
3. `dotnet build` runs once per suite run (counted in the PR or by a test).
4. No finalizer ResourceWarning; a deliberately leaked handle in a scratch test fails the run (shown in the
   PR).
5. The bridge test is ≤ 1.5 s on this host and still fails on the pre-#21 bug it guards (mutation shown in the
   PR).
6. PR CI ≤ 10 min; the C# job grows by ≤ 30 s.

## Performance considerations

The suite should get faster (one C# build instead of one per class).

## Expected tests

Changes to existing tests only, plus the unraisable-hook guard.

## Conflict domain

Hard: `tests/test_csharp_parity.py`, `tests/test_demo_bundle.py`, `tests/test_bridges.py` (the 45° test only),
`NuGet.config` (new, repo root or `examples/csharp/`), `examples/csharp/MbmapReader/*.csproj` (build
properties only), `.github/workflows/ci.yml` (C# job only), the test bootstrap (for example
`tests/__init__.py`).
