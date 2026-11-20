# S1-REVIEW: sprint 1 (v0.2.0) milestone review + test audit

Reviewer: Design (product owner) · inputs: main `b97f3a3` (#23, #24, #22, #21, #26 merged),
RC PR #28 head `1ace70a` (`docs/demo/v0.2.0/`, `docs/releases/v0.2.0.md`, CHANGELOG, version
0.2.0), open PR #27 (FIX-CS-PROBE-PARITY, D46). Procedure: [SPRINT_CLOSE.md](../tasks/SPRINT_CLOSE.md).

## Verdict

**GO for tag v0.2.0 only after #27 merges and the C# reader re-check shows all 13 Pittsburgh
probes PASS within budget (D46).** No other blocker. Until then: NO-GO.

## Milestone acceptance criteria

| # | Criterion (REL-v0.2.0 / SPRINT_CLOSE) | Verdict | Evidence |
|---|---|---|---|
| 1 | ≥ 1 bridge generated in the Pittsburgh package | met | 33 bridge deck objects; Fort Pitt Bridge ways 11950069, 24957029, 121593794 (double deck, layers 2/3); 20 piers on 3 bridges |
| 2 | The Fort Pitt Tunnel generated | met | twin bores 11965424 / 28411466, 5 tubes, 6 headwalls; leak test 0 hits below ground |
| 3 | Their probes PASS in the Python validator | met | 13 exported probes (11 bridge, 2 tunnel) PASS; strict `VALID: 0 error(s), 7 warning(s)` |
| 4 | Their probes PASS in the C# reader | **partially met** | probes 0–8 PASS; 9–12 (`264591820:deck`, `550018192:deck`, both tunnel bores) not checked (2 M query-unit budget). Fixed by #27 → **blocker** |
| 5 | Panel screenshot (D27) | met | `panel.png`, real sidebar (Mesa llvmpipe) |
| 6 | Pittsburgh build ≤ 120 s, excl. download | met | median 20.2 s over 3 runs, byte-identical |
| 7 | 2–3 examples with before/after | met | bridge (`bridge-under`, `overview`), tunnel (`tunnel-portal`), synthetic elevated/passage; DSM ground pair as a bonus |
| 8 | Viewer page | met | `viewer.png`, 13 probes listed |
| 9 | Release notes with "how to try it", limits; version files 0.2.0 | met | `docs/releases/v0.2.0.md`; `blender_manifest.toml` and `__init__.py` = 0.2.0 |
| 10 | Every demo probe PASS in Python **and** C# (SPRINT_CLOSE) | partially met | same as #4 |
| 11 | Demo reproduces on the RC merge | not yet checked | SPRINT_CLOSE step 2, after #28 merges |
| 12 | Strict validator warnings explained | partially met | 6 `unrecognised mb_id form` warnings for headwall ids; fixed by #27 (D46) |

## Task conformance (summary)

| Task | Verdict | Notes |
|---|---|---|
| S1-DEMOKIT #14 | met | presets incl. Pittsburgh (#23), `--panel`, before/after, viewer |
| S1-SEAMS #19 | met | stage hooks in `generate.py`; Blender checks split into modules |
| S1-BRIDGE #21 | met | D21/D22 profile; blocked probes reported (29 in `passage_probes_blocked`), not emitted. Non-blocking finding → [S1-F1](../tasks/S1-F1.md) |
| S1-PIERS #26 | met | Pittsburgh: 20 piers on 3 bridges |
| S1-TUNNEL #22 | met | terrain cut + leak test (D23); probe check on the finished scene. Triangle-bound wording in the task doc corrected in this review (2 triangles per quad, 2 headwalls) |
| S2-ELEV #24 (early) | met | `#k` split ids, elevated/passage probes, 256 probe cap shared with tunnel probes |
| S2-ROOF #18 (early) | met | ships in v0.2.0; the S2 demo still has to show it on real data |

SOLID / over-engineering: one module per structure kind (`bridges`, `tunnels`, `passages`,
shared `structures` / `query`); no speculative registries seen. The tunnel terrain cut grew a
segment-hull fast path with a per-tile fallback (#22); justified by measured cost and covered by
its regression test.

## Test audit (main `b97f3a3` + RC `1ace70a`)

* Unit suite: **575 tests OK in 89 s locally**; CI 56 s per Python job, C# job 16 s (PR CI ≤ 10 min met).
* Slowest test 3.75 s (`HarmonicFillTest.test_largest_grid_is_reproduced_in_bounded_time`); **no test > 5 s** (v0.1.0 finding F1 closed by #23).
* Feature tests present: `test_bridges.py`, `test_tunnels.py`, `test_passages.py`, `test_demo_bundle.py`, Blender checks under `tests/blender/`.

| Gap | Severity | Action |
|---|---|---|
| G1 C# reader does not check probes 9–12 within budget | blocker | #27 (D46), then re-run the RC evidence |
| G2 C#/Python probe-accounting parity not tested in CI | blocker (same fix) | #27 adds `tests/test_csharp_parity.py` |
| G3 Three wall-clock gates remain in `tests/test_terrain_sources.py` (lines 1051, 1072, 1132; since #2) | next sprint | [S1-F2](../tasks/S1-F2.md) |
| G4 Headless Blender harness (bake, mirrored-tunnel tube rule) runs only locally, quoted in PR bodies | accepted (D9, no Blender in PR CI) | re-run once before the tag with the release zip |
| G5 Unsplit approach way → extra clearance warning: no test | next sprint | [S1-F1](../tasks/S1-F1.md) |
| G6 "Fixture build ≤ +20 %" per task: quoted in PR bodies, not re-measured here | info | measure in S2-REVIEW against v0.2.0 |

## Retro notes (max 5)

1. Coordinator decisions D30–D46 live outside `design/roadmap.md`; copy them in with the next design PR so the record stays in one place.
2. The C# budget problem only showed up in the RC demo; a real-data probe check in the task PR (not only the synthetic sample) would have caught it earlier.
3. CI was unavailable for part of #22 (billing) and local evidence was used meanwhile; keep requiring a green CI run on the final head before merge.
4. Task-table statuses went stale again; the merging PR should update its own row (soft domain).
5. The cheap demo worked: demokit plus the Pittsburgh preset produced all evidence in one run.
