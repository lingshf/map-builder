# M-S5-RETRO: milestone "stylized look" (Sprint 5, v0.6.0)

Owner: Team Leader (facts from every role) · record drafted by Product/Design · acceptance in
[tasks/README.md § Milestone retros](../tasks/README.md#milestone-retros) · decisions D195–D199 in the
[roadmap](../roadmap.md#sprint-5-decisions).

Window: from the REL-v0.5.0 RC merge (6535f38, 2026-11-23) to the REL-v0.6.0 RC merge (b04b769, #111), plus #112.
The `v0.6.0` tag is pending (a user decision).

## 1. Outcomes against the goal baseline (D169)

Goal: the stylized low-poly look by default, classic mode byte-identical, flight data exact (G0), within the
low-end budgets. **Technically met**: S5-STYLE-REVIEW is GO at 850a772 ([#108](https://github.com/lingshf/map-builder/issues/108)).
**D169 goal attainment is not yet recorded**: S5-STYLE-PALETTE and S5-STYLE-WATER have no QA `accepted` verdict of
their own, and DOC-TOOLS-F1 has no disposition. Both are Backlog items below (RETRO-I4, RETRO-I5).

| Item | Class | Outcome | Evidence |
|---|---|---|---|
| S5-STYLE-BASE | must | accepted, done | QA R3 acceptance at 850a772 ([#108](https://github.com/lingshf/map-builder/issues/108#issuecomment-7231128550)); D186(f) |
| S5-PERF-GATE | must | accepted, done | [QA 7203624794](https://github.com/lingshf/map-builder/pull/91#issuecomment-7203624794) under D182; Team Leader DoD 2026-11-27 |
| S5-F3 | must | accepted, done | [QA 7201074044](https://github.com/lingshf/map-builder/pull/97#issuecomment-7201074044); D184 |
| S5-F4 | must | accepted, done | [QA 7147309581](https://github.com/lingshf/map-builder/pull/94#issuecomment-7147309581); D171 |
| S5-STYLE-PALETTE | must | done (coordinator) | D186 m1–m4; carry-overs closed by PERF-WATER AC5 and the STYLE-REVIEW QA run |
| S5-STYLE-WATER | must | done (coordinator) | D187; verified in the STYLE-REVIEW QA run |
| S5-PERF-WATER | must | accepted, done | [QA 7231537377](https://github.com/lingshf/map-builder/pull/105#issuecomment-7231537377); AC3 an accepted shortfall (D188) |
| S5-STYLE-REVIEW | must | GO | [#108](https://github.com/lingshf/map-builder/issues/108); T4 fixed by #107, R3 by #109 (D194) |
| S5-DECOR | deferrable | deferred | D185: step 1b needs Unity and glTFast; draft #101 kept; owner Developer, Sprint 6 candidate 6 |
| DOC-PERF | deferrable | accepted, done | [QA review 6080515258](https://github.com/lingshf/map-builder/pull/99#pullrequestreview-6080515258); Team Leader DoD 2026-11-27 |
| DOC-TOOLS-F1 | deferrable | **unfinished** (status `ready`) | Needs an explicit deferral with owner and reason before the milestone record closes (D169 step 1) |
| M-S5-RETRO | must | this record | Acceptance pending the per-role self-checks below |
| Added: S5-T4 (#107), S5-PONDS-FIX (#109) | must (STYLE-REVIEW NO-GO fixes) | merged; closed by the GO | [#108](https://github.com/lingshf/map-builder/issues/108) |

Counts: 10 must delivery items (8 in the baseline, 2 added fixes), all `merged`. With a QA verdict: 6 (BASE,
PERF-GATE, F3, F4, PERF-WATER, and the STYLE-REVIEW GO). Closed by the coordinator on the STYLE-REVIEW QA evidence
without a per-task QA verdict: 2 (PALETTE, WATER). Closed by the GO: 2 (T4, PONDS-FIX). Deferrable: 1 accepted
(DOC-PERF), 1 deferred (DECOR), 1 unfinished (DOC-TOOLS-F1).

Release: REL-v0.6.0 merged at b04b769 (#111). The PO review rejected the first RC head (7012d86) for a missing panel
screenshot and viewer captures; both were added, and QA passed the scoped delta.

## 2. Metrics

| Metric | Value |
|---|---|
| PRs merged in the window | 27 (#82–#112): 11 product code (including the RC), 13 `design/`, 3 `docs/` |
| Review verdicts posted (`VERDICT:` reviews) | 70; mean 2.6 per PR |
| Approved in round 1 | 1 (#107) |
| More than 3 verdict reviews (D89 cap) | #100 (5), #103 (4), #105 (4); including scoped re-reviews after coordinator rulings |
| PRs whose last `VERDICT:` review on GitHub is CHANGES_REQUESTED | 9 (#82, #83, #84, #85, #87, #88, #91, #93, #94); merged without an `APPROVED` verdict on GitHub; the GitHub record does not show what closed the final round (to be confirmed by the Team Leader) |
| GLB size, classic → stylized | Munich 4.37 → 2.34 MB (−46.5 %), Pittsburgh 15.25 → 9.15 MB (−40.0 %), Bellevue-Factoria 25.75 → 15.32 MB (−40.5 %) |
| Flight data | `.mbcol`, `.mbhf`, georeference and probes identical between styles (G1 16/16); classic identity G3 8/8; floating audit 0 (G13) |

## 3. Deviations

| Deviation | Cause | Impact |
|---|---|---|
| S5-DECOR not delivered | Step 1b needs Unity and glTFast, unavailable on this host (D185) | Visual decoration missing; no flight-data impact |
| STYLE-REVIEW NO-GO before GO (T4, R3) | Default-style not pinned in tests; ponds shallow band conflicted with the 6 m shore bank | Two extra fix PRs (#107, #109) and a checklist window change (D194) |
| G10 Munich façade parity fails | Pre-existing since v0.5.0 (D191) | Non-gating for S5; [#106](https://github.com/lingshf/map-builder/issues/106) is Sprint 6 candidate 2 |
| PERF-WATER AC3 counters short of target | Three counters stay above target; recorded as known limits (D188) | Accepted shortfall; Sprint 6 candidate 8 |
| First RC head rejected by PO | The RC compared prose, not the previous release's demo set | One extra RC round; D196 |
| Internal labels in release prose | No check on public prose before review | Rework in the RC; D195 |
| Review rounds above the D89 cap; 9 merges without an `APPROVED` verdict on GitHub | Not determined from the GitHub record (Team Leader to confirm) | The approval trail is not complete on GitHub |

## 4. Lessons and decisions

* **D195** Public release and demo prose carries no internal process labels; REL greps its added lines before review.
* **D196** Every RC ships `panel.png` for any new UI control plus viewer captures for each showcase city; REL checks
  against the previous release's demo set before opening the RC.
* **D197** Prose-only RC edits carry the prior exact-head QA PASS forward; Review still approves the exact head.
* **D198** Visual QA windows are checked against geometry ownership before acceptance; QA metric windows are pinned in
  the checklist and change only with a D-number (as D194).
* **D199** Sprint 6 starts from the ordered [Sprint 6 candidates](../roadmap.md#sprint-6-candidates-ordered-from-the-v060-po-review);
  Product/Design proposes the Sprint 6 goal and must list in a follow-up PR.

## 5. Self-checks by role

| Role | Self-check of own outputs | Status |
|---|---|---|
| Product/Design | Task table and roadmap statuses brought current (#112, this PR); REL-v0.6.0 spec added late, after the RC opened (now in place); D-log complete to D199; Sprint 6 candidates recorded. Outdated: none known. Needs refine: PALETTE/WATER have no per-task QA verdict (recorded as coordinator `done`). | done |
| Team Leader | Consistency per member; the 9 merges without an `APPROVED` verdict on GitHub; DOC-TOOLS-F1 deferral | pending |
| Developers | Code, tests and docs of #83, #85, #91, #94, #97, #100, #103, #105, #107, #109 | pending |
| QA | Verdicts and pinned windows (D194, D198) | pending |
| Code Reviewer | Round counts above the D89 cap | pending |
| Delivery/Release | #111 and the D195/D196 pre-RC checks | pending |
| Knowledge Lead | Coverage matrix and learning paths in `docs/README.md` | pending |

## 6. Improvements

Entered in the canonical Backlog: [tasks/README.md § M-S5-RETRO improvements](../tasks/README.md#m-s5-retro-improvements)
(owner, priority, acceptance and target milestone per row).

Milestone record: open until the pending self-checks are recorded and the Team Leader accepts this retro (D169 step 3).
