# S2-REVIEW: end-of-v2 milestone review and test audit

Reviewer: Design (product owner) · main `2de9024` (includes #31 S1-F2 at `c9fd1aa` and #32 S1-F1
at `2de9024`) · checklist: [tasks/S2-REVIEW.md](../tasks/S2-REVIEW.md) · order per **D48**:
this review runs **before** REL-v0.3.0, and its findings define the remaining v0.3.0 scope.

## Verdict

**v2 close: NO-GO on `2de9024`. Go for the work that is done.** The v2 features are built and
tested: bridges, tunnels, elevated parts, building passages and roof shapes. Bridges and tunnels
are proven on real data, shipped in `v0.2.0`. Three things block closing v2 with `v0.3.0`:

1. Elevated parts and building passages have **no real-data evidence**. The D26 Pittsburgh area
   contains none of them.
2. Roof shapes have **no headless-Blender coverage**.
3. One flaky unit test undermines the green-CI gate.

The fixes are S2-F1, S2-F2 and S2-F3 (below), followed by one REL-v0.3.0 (D48).

## 1. v2 acceptance against the roadmap

| Roadmap criterion | Evidence | Verdict |
|---|---|---|
| Drone capsule (r = 1 m) passes **under a real bridge** (Python + C#) | v0.2.0 Pittsburgh: 11 bridge probes PASS in Python and C#, `VALID` (docs/demo/v0.2.0) | **met** |
| … **through the real tunnel** | v0.2.0 Pittsburgh: 2 tunnel probes PASS in Python and C# | **met** |
| … **beneath an elevated part / passage**, synthetic | `osm:way/1048:under` and `1098:passage` PASS in Python and C#. Unit tests cover: along/across rays, dead end, courtyard, no building, already elevated, road ownership. Blender `checks_passages` passes. | **met** |
| … beneath an elevated part / passage, **real data** (S2 exit, REL-v0.3.0 AC, S2-REVIEW item 1) | Pittsburgh has none of either ([v0.2.0 demo README](../../docs/demo/v0.2.0/README.md) line 53) | **not met**, see S2-F2 |
| New roof shapes closed and bound | `tests/test_roofs.py` covers dome/onion, direction, saltbox, skillion, unsupported → flat fallback, concave/courtyard dome. `test_scene_generation` covers across and along/hipped. | **met** (unit) |
| Roof shapes in headless Blender (item 5) | `tests/blender/` has `checks_core/bridges/tunnels/passages`; `grep roof` finds **0** hits | **not met**, see S2-F3 |
| Roof shapes on real data | Not verified. Pittsburgh `roof:shape` counts are unknown: the Overpass count query timed out or returned nothing during this review. | **partially met**, folded into S2-F2 |
| Real-data build ≤ 120 s | v0.2.0 Pittsburgh median 18.95 s | **met** |
| PR CI ≤ 10 min | 3 jobs, ≈ 85 s / 82 s / 20 s | **met** |
| Design conformance: D24 `#k` ids; one roof entry point | Passages split as `{id}#{k}` (`core/passages.py:237,244`). Roofs enter only through `roofs.build_roof` (`core/generate.py:574`). S1 findings closed: S1-F1 #32, S1-F2 #31. | **met** |
| Release audit (item 6) | `v0.1.0` and `v0.2.0` are published and each has "How to try it". The roadmap's assets column lists a real-data `.mbmap` + `.glb`, but both releases carry **only** the extension zip. | **partially met**, see S2-F4 |

**SOLID / size.** No stubs or dead code are left in the new modules. Every `pass` in `core/` is
a deliberate `except` or no-op. Module sizes:

| Module | Lines |
|---|---|
| `generate.py` | 1912 |
| `osm.py` | 1661 |
| `tunnels.py` | 811 |
| `bridges.py` | 714 |
| `passages.py` | 522 |
| `structures.py` | 385 |
| `roofs.py` | 340 |

The stage modules are cohesive. `generate.py` and `osm.py` are large but split by function.
Splitting them is a v3 refactor, not a v2 blocker (L3).

## 2. Test audit

* **Suite:** 586 unit tests, 104 s locally (Python 3.12). The slowest are 3.51 s
  (`test_dsm_correction … test_large_fine_grid_is_bounded`), 3.22 s and 3.14 s (bridge 45°
  clearance). No test exceeds the 5 s DoD limit.
* **Wall-clock gates:** none left. A grep for `assertLess/Greater` on
  `perf_counter|monotonic|elapsed|time.time|duration` under `tests/` finds no matches. S1-F2 is
  closed. `DeadlineProbe.assert_armed` checks *configured* timer intervals, not measured time,
  which is acceptable.
* **Flaky:** `test_terrain_sources.RoundFourTest.test_stalled_tls_handshake_hits_deadline`
  failed in the full local run and in 2 of 15 isolated runs. `assert_armed` requires
  `len(shutdowns) >= 1`. The test drives a real socket that sends one byte every 50 ms against
  `total_timeout` 0.6 s, so the timing race shows up under CPU load. This is S2-F1.
* **G6, fixture build re-measured against v0.2.0:** synthetic fixture through the CLI, 2 × 3
  interleaved runs, medians:

  | Build | Run 1 | Run 2 |
  |---|---|---|
  | `v0.2.0` (`4e0b0e2`) | 0.999 s | 0.981 s |
  | main (`2de9024`) | 1.003 s | 0.981 s |

  The change is **≈ 0 %**, within the D35 +20 % budget. The main output is byte-identical to the
  committed `examples/synthetic_sample.mbmap` (sha256 prefix `9463B7BEFF16`).
* **Coverage gaps:**
  * Blender harness has no roof checks (S2-F3).
  * No real-data passage or elevated-part probe (S2-F2).
  * The C# reader and the probes run in CI on the synthetic sample only. Pittsburgh is checked
    per PR under D47, which is acceptable.

## 3. Gaps

| id | Gap | Severity | v0.3.0 |
|---|---|---|---|
| S2-F1 | Flaky TLS-deadline test. A green-CI gate is only meaningful if the suite is deterministic. | medium | **blocker** |
| S2-F2 | No real-data elevated part / building passage, and roof shapes unverified on real data. A second demo preset is needed (user decision below). | high (v2 goal) | **blocker** |
| S2-F3 | Headless Blender harness has no roof checks. | medium | **blocker** (cheap) |
| S2-F4 | Releases attach only the zip. The roadmap promises a real-data `.mbmap` (GLB inside) with ODbL attribution. | low | **blocker for v0.3.0's own assets**, folded into the REL-v0.3.0 AC. Backfilling v0.1.0/v0.2.0 is *later* and optional. |
| L1 | 76 degenerate collision triangles warned on the Pittsburgh package | low | later |
| L2 | Unsplit through-way approach road: possible extra clearance warning (S1 follow-up) | — | closed by S1-F1 #32 |
| L3 | `generate.py` / `osm.py` size | low | later (v3) |
| L4 | v3 items: railway / culvert / `man_made=bridge` (D25), LOD/streaming, textures, licence (D13) | — | later |

## 4. Proposed v0.3.0 task list (D48)

| Order | Task | Owner | Conflict domain (hard) | Parallel with |
|---|---|---|---|---|
| 1 | [S2-F1](../tasks/S2-F1.md): make the TLS-deadline test deterministic | dev | `tests/test_terrain_sources.py` | F2, F3 |
| 1 | [S2-F2](../tasks/S2-F2.md): second real-data demo preset for elevated parts, passages and roofs | dev | `tools/demo/presets/<new>.json`, `tests/test_demo_bundle.py` (preset rows only) | F1, F3 |
| 1 | [S2-F3](../tasks/S2-F3.md): headless Blender roof checks | dev | `tests/blender/checks_roofs.py` (new), `tests/fixtures/synthetic_area.osm` (soft, append-only) | F1, F2 |
| 2 | [REL-v0.3.0](../tasks/REL-v0.3.0.md): RC with both presets; attaches the real-data `.mbmap` | release manager | per its doc | runs alone |
| 3 | Short S2 close check (design): confirm F1–F4 closed on the RC, then the coordinator retro and tag `v0.3.0` | design | `design/` | — |

If F2 turns up a defect in passages or roofs on real data, it becomes S2-F5 and is fixed before
the RC.

## 5. Decision needing the user (or the coordinator on the user's behalf)

**Real-data evidence for elevated parts and passages (S2-F2).**

* **(a) Recommended:** add a second, small real-data preset, at most 1 × 1 km. It must contain at
  least one `building:part` with `min_height`/`building:min_level`, at least one highway
  `tunnel=building_passage`, and some non-flat `roof:shape` tags. Pittsburgh stays the
  bridge/tunnel area (D26).
* **(b)** Enlarge the Pittsburgh area. This makes the build bigger and gives no guarantee it
  gains such features.
* **(c)** Accept synthetic-only evidence and amend the REL-v0.3.0 and S2 exit criteria.

If (a) finds no candidate within its time box, fall back to (c), and record that in the release
notes.

## 6. Retro notes

1. **Geometry beats proxies (reinforces D39).** S1-F1 tried proxies four times: OSM node
   sharing, then distance, then variants. Each was defeated by a real-data counterexample. The
   geometric two-sided check on the *exported* triangles held. Rule: decide geometric questions
   on exported geometry, and keep topology or IDs only as tie-breakers.
2. **Write real-data acceptance cases first** (DoD 10). F1 converged only once real Pittsburgh
   excerpts and counterexamples were tests.
3. **Pick the demo area against every sprint goal.** D26 was chosen for bridges and tunnels and
   silently lacks S2 features, which is why S2-F2 exists. Future area decisions list all target
   features with counts.
4. **Flaky timing tests erode the gate.** Real-socket timing races should use injected clocks or
   fakes. "Configured, not measured" (S1-F2) was right but not sufficient.
5. **D48 order worked.** Reviewing before the RC turned the review into scope and avoided an RC
   rerun, unlike v0.2.0, where D46 forced a re-run.
