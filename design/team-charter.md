# Team charter (map-builder)

Maintained by the Team Leader (operating model §3); written by Product/Design + Knowledge Lead as executor.
The affected owners confirm changes to it. It records **process and authority only**. Product decisions stay in
the [roadmap decision record](roadmap.md#decision-record), and tasks stay in the single Backlog.

## 1. Profile and roles

* **Profile:** `unified-agile-v1` (agile-ai-team). It was migrated from `ai-dev-team` on 2026-11-24, with the user's
  confirmation in the Project conversation. Work already in flight at migration, **#85** (S5-STYLE-BASE) and **#86**,
  keeps the previous rules until it merges. The new rules apply from the next task onward.
* **Role bindings:**

| Role | Bound to | Notes |
|---|---|---|
| Team Leader | Project map-builder session `4b9ee088` | Coordinates the team, routes approvals, records execution facts and Sprint notes; reports to the user (and Manager2 if one exists) |
| Product/Design + Knowledge Lead | session `0988fb39` | Combined, non-conflicting duties. Owns the Product Goal, Backlog order and meaning, acceptance baselines, `design/`, the docs entry and coverage matrix. Writes no production code |
| Developer | S5-STYLE-BASE session `5f60b426`, plus new Developer sessions per task (≤ 3 at a time) | Implementation, tests, facts for docs; never self-merges |
| Code Reviewer + QA | session `8fab5c04` | Non-author. Gives **separate** verdicts: code review (`VERDICT:` on the exact head) and QA behavioral acceptance |
| Delivery/Release | on demand | A dedicated session starts only when a release is authorized. Until then the Team Leader records release facts |

The review model family differs from Dev (D5).

## 2. Single sources of truth

| Authority | Path | Owner |
|---|---|---|
| Backlog and task authority (one only) | [`design/tasks/README.md`](tasks/README.md) | Product/Design owns order and meaning. The Team Leader records execution evidence on the same task IDs |
| Goals, requirements, decisions, architecture facts | [`design/roadmap.md`](roadmap.md), `design/tasks/*.md` | Product/Design |
| Reviews and milestone audits | `design/reviews/` | Product/Design (written); Team Leader (retro) |
| System documentation entry and coverage matrix | [`docs/README.md`](../docs/README.md) | Knowledge Lead (structure); module owners (facts) |
| Package contract | [`docs/PACKAGE_FORMAT.md`](../docs/PACKAGE_FORMAT.md) | Developer (facts), Product/Design (format decisions) |
| CHANGELOG, `docs/releases/`, `docs/demo/<ver>/` | release files | Delivery/Release (D28) |
| This charter, Sprint notes | `design/team-charter.md` | Team Leader |

Sprint selections, role queues and dashboards are views of the Backlog. They are not separate task tables.

## 3. Cadence, milestones and versions

These three are recorded separately; none maps one-to-one onto another.

* **Sprint 5:** two weeks, **2026-11-24 to 2026-12-08**. This is the Team Leader's decision under the user's
  delegation ("其他的你先尽量选择最优，推进项目，不要等我"), and the user may change it.
  * **Goal:** deliver the stylized look of the M-S5 milestone, with flight data exact (G0).
  * **Selected:** S5-STYLE-BASE, S5-PERF-GATE, S5-STYLE-PALETTE and S5-STYLE-WATER, in the D156 order. S5-PERF-WATER,
    S5-STYLE-REVIEW and S5-DECOR follow if capacity allows.
  * **WIP:** at most 3 Developer sessions.
* **Milestone M-S5, "stylized look":** an outcome checkpoint. It is reached at the S5-STYLE-REVIEW GO
  ([spec](tasks/S5-STYLE.md)) and may span Sprints.
* **Version:** not decided. The next version number and its contents are **not tied to Sprint 5**. A release needs
  its own user decision (§6).

Events: Sprint Review and Retro at the end of the Sprint, as short written summaries. There are no simulated
daily meetings, and no automation or recurring schedule.

## 4. Definition of Done

This section is the **single canonical Definition of Done** and is owned by the Team Leader. Other pages link here;
they do not copy it. It applies to every code, design and docs PR unless an item is marked "where relevant".

A task is `done` only when the Team Leader verifies every applicable item against the exact merged revision. Record
each lifecycle fact separately: `implementation_complete`, `merged`, `accepted`, `done`, then `released` and
`deployed`. Use the states `unknown`, `pending`, `passed`, `failed`, `blocked` or `not_applicable`. Each
`not_applicable` needs a reason and cannot bypass a required item.

**Acceptance and verdicts**

1. **Acceptance tested and traceable.** Every criterion ID in the task spec maps to an automated test or a recorded
   run, linked in the PR. Complex geometry tasks commit their acceptance cases first: real-data excerpts (OSM ids
   from the demo areas) plus counterexamples, before the implementation.
2. **Code review.** A non-author reviewer posts `VERDICT: APPROVED` on the exact head (D5, D33). Findings are fixed
   and rechecked, not dismissed.
3. **QA behavioral acceptance.** A separate non-author QA verdict against the spec's criterion IDs, on the exact
   artifact. Visual tasks need actual renders or journeys (contact sheets, D140), not code inspection alone.

**CI and tests**

4. **CI green on the exact head.** That means Python 3.11 and 3.12 unit tests, the CLI build and validation of the
   synthetic fixture, and the C# reader job with its format-policy and frozen-reader steps. On the 3.12 leg it also
   includes the mypy step. Local evidence may support a review, never a merge (D38).
5. **Test rules.** Nothing is silently skipped, and no assertion, threshold or coverage is weakened. No wall-clock
   or p95 gates in the PR suite. New tests ≤ 5 s each, with no Blender and no network in PR CI. PR CI stays ≤ 10 min
   (D134). Performance is measured and quoted in the PR, not asserted in CI.
6. **Performance gate.** The project gate in §5 (D153, with D147 as the sanity check) passes, along with the task's
   own performance criteria. Design and implementation quality evidence follows the shared quality standard.

**PR evidence and Backlog**

7. **PR body.** It contains:
   * the CI time;
   * a **behavior-change table** (before / after / why, including sample and report changes);
   * a **"User-visible changes"** section, written "none" if there are none.
8. **Backlog row updated.** The merging PR updates its task row in [tasks/README.md](tasks/README.md): status, PR
   and merge SHA.

**Project-specific evidence (where relevant)**

9. **Flight data.**
   * **G0:** `.mbcol` and `.mbhf` are byte-identical, and the georeference, passage probes and blocked and dropped
     lists are exactly equal; this applies to S5 tasks and any task that declares it.
   * **Probes and collision:** a task that touches passage probes, collision or query work accounting attaches
     Python **and** C# reader runs of the real Pittsburgh package (D47).
10. **Sample.** `examples/synthetic_sample.mbmap` is regenerated only under the D103 merge-time slot, with the
    command in `examples/README.md`, and `tests/test_examples.py` is green.
11. **Blender.** Headless Blender 4.2.23 (`tests/blender/run_integration.py`) reports `OK: 0 failure(s)` when the
    task touches generation or Blender code; the result is appended to `docs/VALIDATION.md`.
12. **Package and reader compatibility.** Format changes follow D101 and D110, with a positive frozen-reader fixture
    for any minor bump.
13. **Knowledge.** The changed scope's facts are updated in the canonical page: `PACKAGE_FORMAT.md`, README Limits,
    `UNITY_CORE_HANDOFF.md`, `VALIDATION.md` or the page the [coverage matrix](../docs/README.md) names. The page
    has a non-author review, and no required gap is left unresolved.
14. **Usable and recoverable.** The increment works on `main` after merge. Where the change has state or format
    consequences (sample, package format, caches, release assets), the PR states how to recover: revert, rebuild
    or regenerate. Being ready to deploy is not permission to deploy; see §6.
15. **Ownership limits.** Feature PRs do not include a release, demo render, CHANGELOG entry or version bump; those
    belong to the release manager (D28). Dev PRs do not edit `design/` (D125).

Quality approval is never merge, release or deployment authorization.

## 5. Retained project rules (exceptions to the shared defaults)

| Rule | Decision | Summary |
|---|---|---|
| Performance gating | D147, D153 | Deterministic work-vector gate (F1–F3, with F4 and F6 in review) against merge-base plus counter commit C. D147 CPU time is the F5 sanity check only. Munich and Pittsburgh are the gating presets. Until S5-PERF-GATE merges, D147 applies |
| Sample slot | D103 | One writer at a time for `examples/synthetic_sample.mbmap`, under a merge-time slot from the Team Leader |
| Design ownership | D125 | Dev PRs do not edit `design/`; measurements and spec gaps go in the PR body |
| Review cap | D89, D133 | The cap limits the **number of review rounds and the scope** only; it never authorises a merge. Every merge still needs the D133 gate (non-author approval on the exact head, green CI, mergeable, coordinator authorisation), and unresolved blockers still block. In the past the coordinator merged some PRs on a personally verified final commit without an exact-head approval: #77 (D146), #79 (D146), #82 (D155, after R2), #84 (D158, after R2) and #83 (D159). Each was a **separately recorded one-off exception**, not the default outcome of reaching the cap, and it is no precedent. Any future exception needs its own coordinator record |
| Flight-data gate | G0 ([S5-STYLE](tasks/S5-STYLE.md#g0-the-flight-data-gate-every-s5-task-no-waivers)) | `.mbcol` and `.mbhf` byte-identical; georeference, passage probes, blocked and dropped probes exactly equal; no waivers. Geometry changes need explicit user approval |

## 6. Operation permissions (separate records)

| Operation | Permission | Source |
|---|---|---|
| **Merge** | Coordinator-gated squash merges after the exact-head gate: non-author approval, green CI, mergeable and fresh. The Team Leader authorises; the authorised session runs `gh pr merge --squash --delete-branch --match-head-commit <sha>`. No self-merge | User-approved policy **T1, 2026-11-23** (D6, D33, D34) |
| **Tag and release** | An explicit user decision **per version**. Nothing is tagged or published without it | User |
| **Deployment, repository settings, schedules and automations** | **None granted** | — |

This migration grants **no new permission**. A role title never supplies authority.

## 7. Protected state

* The primary checkout `C:\GithubCopilot\map-builder`, pre-existing worktrees and sessions, running services, local
  data, caches and frozen release inputs are read-only.
* Frozen caches stay outside the repository, in the custody of the release manager or Team Leader on the team build
  host.
* The drone-flight-simulator repository is read-only.
