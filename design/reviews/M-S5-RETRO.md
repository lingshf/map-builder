# M-S5-RETRO: milestone "stylized look" (Sprint 5, v0.6.0)

Owner: Team Leader (facts from every role) · record drafted by Product/Design · acceptance in
[tasks/README.md § Milestone retros](../tasks/README.md#milestone-retros) · decisions D195–D200 in the
[roadmap](../roadmap.md#sprint-5-decisions).

Window: from the REL-v0.5.0 RC merge (6535f38, 2026-11-23) to the REL-v0.6.0 RC merge (b04b769, #111), plus #112.
The `v0.6.0` tag is pending (a user decision).

## 1. Outcomes against the goal baseline (D169)

Goal: the stylized low-poly look by default, classic mode byte-identical, flight data exact (G0), within the
low-end budgets. **Technically met**: S5-STYLE-REVIEW is GO at 850a772 ([#108](https://github.com/lingshf/map-builder/issues/108)).
**D169 step 1 conditions are now satisfied**: every must item has a QA `accepted` verdict (PALETTE and WATER via
RETRO-I4, done) and every deferrable item is accepted or deferred with an owner (DOC-TOOLS-F1 via RETRO-I5, done).
The Team Leader records goal attainment and accepts this retro.

| Item | Class | Outcome | Evidence |
|---|---|---|---|
| S5-STYLE-BASE | must | accepted, done | QA R3 acceptance at 850a772 ([#108](https://github.com/lingshf/map-builder/issues/108#issuecomment-7231128550)); D186(f) |
| S5-PERF-GATE | must | accepted, done | [QA 7203624794](https://github.com/lingshf/map-builder/pull/91#issuecomment-7203624794) under D182; Team Leader DoD 2026-11-27 |
| S5-F3 | must | accepted, done | [QA 7201074044](https://github.com/lingshf/map-builder/pull/97#issuecomment-7201074044); D184 |
| S5-F4 | must | accepted, done | [QA 7147309581](https://github.com/lingshf/map-builder/pull/94#issuecomment-7147309581); D171 |
| S5-STYLE-PALETTE | must | accepted, done | [QA 7231809953](https://github.com/lingshf/map-builder/pull/100#issuecomment-7231809953) (merged 4cb17fb, integrated evidence through 850a772); D186 m1–m4 |
| S5-STYLE-WATER | must | accepted, done | [QA 7231810312](https://github.com/lingshf/map-builder/pull/103#issuecomment-7231810312) at 850a772, after the #109 shoreline fix (merged 852a137); D187 |
| S5-PERF-WATER | must | accepted, done | [QA 7231537377](https://github.com/lingshf/map-builder/pull/105#issuecomment-7231537377); AC3 an accepted shortfall (D188) |
| S5-STYLE-REVIEW | must | GO | [#108](https://github.com/lingshf/map-builder/issues/108); T4 fixed by #107, R3 by #109 (D194) |
| S5-DECOR | deferrable | deferred | D185: step 1b needs Unity and glTFast; draft #101 kept; owner Developer, Sprint 6 candidate 6 |
| DOC-PERF | deferrable | accepted, done | [QA review 6080515258](https://github.com/lingshf/map-builder/pull/99#pullrequestreview-6080515258); Team Leader DoD 2026-11-27 |
| DOC-TOOLS-F1 | deferrable | deferred | Coordinator ruling on #113: deferred to Sprint 6 (candidate 5a), owner Developer / Knowledge Lead; reason: tools-only error handling in a deferrable item, no effect on the M-S5 goal or flight data; not blocking M-S5 |
| M-S5-RETRO | must | this record (draft under PR review) | Awaiting Team Leader acceptance (D169 steps 1–2; RETRO-I4 and RETRO-I5 done); per-role self-checks below are `not collected` (non-blocking) |
| Added: S5-T4 (#107), S5-PONDS-FIX (#109) | must (STYLE-REVIEW NO-GO fixes) | merged; closed by the GO | [#108](https://github.com/lingshf/map-builder/issues/108) |

Counts (must delivery items, excluding the retro):

* Original must subtotal (8): `merged` 8 of 8; `accepted` with a QA verdict 8 of 8 (BASE, PERF-GATE, F3, F4,
  PALETTE, WATER, PERF-WATER, STYLE-REVIEW GO). PALETTE and WATER were coordinator `done` first and QA `accepted`
  later (RETRO-I4).
* NO-GO fixes added to the baseline by D169 (2): T4 and PONDS-FIX, `merged` 2 of 2 and QA `accepted` 2 of 2 (T4 PASS
  and ponds ACCEPTED in [#108](https://github.com/lingshf/map-builder/issues/108)).
* Expanded must set (10): `merged` 10 of 10; QA `accepted` 10 of 10.
* Deferrable (3): 1 `accepted` (DOC-PERF), 2 deferred with owner (DECOR, DOC-TOOLS-F1).

RETRO-I4 and RETRO-I5 are done, so nothing in the Backlog blocks D169 step 1 or retro acceptance (step 2).

Release: REL-v0.6.0 merged at b04b769 (#111). The PO review rejected the first RC head (7012d86) for a missing panel
screenshot and viewer captures; both were added, and QA passed the scoped delta.

## 2. Metrics

| Metric | Value |
|---|---|
| PRs merged in the window | 27 (#82–#112): 11 product code (including the RC), 13 `design/`, 3 `docs/` |
| Review verdicts posted (`VERDICT:` reviews) | 70; mean 2.6 per PR |
| Approved in round 1 | 1 (#107) |
| More than 3 verdict reviews (D89 cap) | #100 (5), #103 (4), #105 (4); including scoped re-reviews after coordinator rulings |
| PRs whose last `VERDICT:` review on GitHub is CHANGES_REQUESTED | 9 (#82, #83, #84, #85, #87, #88, #91, #93, #94); see the D200 audit below |
| GLB size, classic → stylized | Munich 4.37 → 2.34 MB (−46.5 %), Pittsburgh 15.25 → 9.15 MB (−40.0 %), Bellevue-Factoria 25.75 → 15.32 MB (−40.5 %) |
| Flight data | `.mbcol`, `.mbhf`, georeference and probes identical between styles (G1 16/16); classic identity G3 8/8; floating audit 0 (G13) |

D200 audit (2026-11-27, `gh api repos/lingshf/map-builder/pulls/N/reviews`): none of the 9 PRs has a review whose
body starts `VERDICT: APPROVED` with `commit_id` equal to the merged head. Each has only `VERDICT: CHANGES_REQUESTED`
reviews on earlier heads.

| PR | Merged head | Last verdict review (head) |
|---|---|---|
| #82 | 340a2d8 | [6035375122](https://github.com/lingshf/map-builder/pull/82#pullrequestreview-6035375122) (a3b3d8a) |
| #83 | e3d8009 | [6044811397](https://github.com/lingshf/map-builder/pull/83#pullrequestreview-6044811397) (b8384c7) |
| #84 | 8f0f2ff | [6044726082](https://github.com/lingshf/map-builder/pull/84#pullrequestreview-6044726082) (db470cd) |
| #85 | a001772 | [6047527473](https://github.com/lingshf/map-builder/pull/85#pullrequestreview-6047527473) (1787ac9) |
| #87 | c982f9a | [6047364171](https://github.com/lingshf/map-builder/pull/87#pullrequestreview-6047364171) (99e7e73) |
| #88 | 1d543d2 | [6047594274](https://github.com/lingshf/map-builder/pull/88#pullrequestreview-6047594274) (4c77a66) |
| #91 | d889d97 | [6051300251](https://github.com/lingshf/map-builder/pull/91#pullrequestreview-6051300251) (98963de) |
| #93 | 7736f05 | [6048289125](https://github.com/lingshf/map-builder/pull/93#pullrequestreview-6048289125) (00152ca) |
| #94 | 5aacb7b | [6048710912](https://github.com/lingshf/map-builder/pull/94#pullrequestreview-6048710912) (e9a2ab7) |

Finding (historical, non-blocking): 9 Sprint 5 merges lack a D200 review record. RETRO-I3 prevents a repeat.

## 3. Deviations

| Deviation | Cause | Impact |
|---|---|---|
| S5-DECOR not delivered | Step 1b needs Unity and glTFast, unavailable on this host (D185) | Visual decoration missing; no flight-data impact |
| STYLE-REVIEW NO-GO before GO (T4, R3) | Default-style not pinned in tests; ponds shallow band conflicted with the 6 m shore bank | Two extra fix PRs (#107, #109) and a checklist window change (D194) |
| G10 Munich façade parity fails | Pre-existing since v0.5.0 (D191) | Non-gating for S5; [#106](https://github.com/lingshf/map-builder/issues/106) is Sprint 6 candidate 2 |
| PERF-WATER AC3 counters short of target | Three counters stay above target; recorded as known limits (D188) | Accepted shortfall; Sprint 6 candidate 8 |
| First RC head rejected by PO | The RC compared prose, not the previous release's demo set | One extra RC round; D196 |
| Internal labels in release prose | No check on public prose before review | Rework in the RC; D195 |
| Review rounds above the D89 cap; 9 merges without a D200 review record | Not determined from the GitHub record | The approval trail is incomplete for 9 historical merges (finding below; non-blocking) |

## 4. Lessons and decisions

* **D195** Public release and demo prose carries no internal process labels; REL greps its added lines before review.
* **D196** Every RC ships `panel.png` for any new UI control plus viewer captures for each showcase city; REL checks
  against the previous release's demo set before opening the RC.
* **D197** Prose-only RC edits carry the prior exact-head QA PASS forward; Review still approves the exact head.
* **D198** Visual QA windows are checked against geometry ownership before acceptance; QA metric windows are pinned in
  the checklist and change only with a D-number (as D194).
* **D199** Sprint 6 starts from the ordered [Sprint 6 candidates](../roadmap.md#sprint-6-candidates-ordered-from-the-v060-po-review);
  Product/Design proposes the Sprint 6 goal and must list in a follow-up PR.
* **D200** The canonical review record for a merge is a review whose body starts `VERDICT: APPROVED` and whose
  `commit_id` equals the merged head; its GitHub state may be COMMENTED (shared owner account).

## 5. Self-checks by role

Coordinator ruling on #113: self-checks are non-blocking for M-S5; roles without one are recorded as `not collected`.

| Role | Self-check of own outputs | Status |
|---|---|---|
| Product/Design | Task table and roadmap statuses brought current (#112, this PR); REL-v0.6.0 spec added late, after the RC opened (now in place); D-log complete to D199; Sprint 6 candidates recorded. Outdated: none known. Needs refine: PALETTE/WATER were recorded `done` before a per-task QA verdict; closed by RETRO-I4. | done |
| Team Leader | Consistency per member; the D200 audit finding; DOC-TOOLS-F1 deferral (ruled on #113) | not collected |
| Developers | Code, tests and docs of #83, #85, #91, #94, #97, #100, #103, #105, #107, #109 | not collected |
| QA | Verdicts and pinned windows (D194, D198) | not collected |
| Code Reviewer | Round counts above the D89 cap | not collected |
| Delivery/Release | #111 and the D195/D196 pre-RC checks | not collected |
| Knowledge Lead | Coverage matrix and learning paths in `docs/README.md` | not collected |

## 6. Improvements

Entered in the canonical Backlog: [tasks/README.md § M-S5-RETRO improvements](../tasks/README.md#m-s5-retro-improvements)
(owner, priority, acceptance and target milestone per row).

Milestone record: open until the Team Leader accepts this retro (D169 step 3).
