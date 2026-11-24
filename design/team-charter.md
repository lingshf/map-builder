# Team charter (map-builder)

Maintained by the Team Leader (operating model §3); written by Product/Design + Knowledge Lead as executor.
The affected owners confirm changes to it. It records **process and authority only**. Product decisions stay in
the [roadmap decision record](roadmap.md#decision-record), and tasks stay in the single Backlog.

## 1. Profile and roles

* **Profile:** `unified-agile-v1` (agile-ai-team). It was migrated from `ai-dev-team` on 2026-11-24, with the user's
  confirmation in the Project conversation. Work already in flight at migration (#86) finished under the previous
  rules. The new rules apply from the next task onward.
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

A task is `done` only when the Team Leader verifies all of the following against the exact merged revision. Each
item is recorded as a separate fact (`implementation_complete`, `merged`, `accepted`, `done`; then `released` and
`deployed` separately), using states `unknown`, `pending`, `passed`, `failed`, `blocked` or `not_applicable` with a
reason.

1. **Acceptance traceable and independently validated.** Every criterion ID in the task spec maps to an automated
   test or a recorded run, linked in the PR.
2. **Code review:** a non-author `VERDICT: APPROVED` on the exact head (D33). Findings are fixed and rechecked.
3. **QA behavioral acceptance:** a separate non-author QA verdict against the spec's criterion IDs, on the exact
   artifact. Visual tasks need actual renders or journeys (contact sheets, D140), not code inspection alone.
4. **CI green on the exact head.** Nothing is silently skipped, and no assertions, thresholds or coverage are
   weakened. PR CI stays ≤ 10 min, with no new test over 5 s and no wall-clock asserts (D134).
5. **Design, performance and implementation quality** evidence per the shared quality standard is current, and the
   project performance gate (§5) passes.
6. **Knowledge:** the changed scope's facts are updated in the canonical page, checked against the coverage matrix
   in [`docs/README.md`](../docs/README.md), and have no unresolved required gap.
7. **Backlog row updated** with status, PR and merge SHA.
8. **Project rules where relevant:** the sample is regenerated only under the D103 slot; headless Blender is run
   when generation or Blender code changes; probe and collision tasks attach Python and C# Pittsburgh runs (D47).

Quality approval is never merge, release or deployment authorization.

## 5. Retained project rules (exceptions to the shared defaults)

| Rule | Decision | Summary |
|---|---|---|
| Performance gating | D147, D153 | Deterministic work-vector gate (F1–F3, with F4 and F6 in review) against merge-base plus counter commit C. D147 CPU time is the F5 sanity check only. Munich and Pittsburgh are the gating presets. Until S5-PERF-GATE merges, D147 applies |
| Sample slot | D103 | One writer at a time for `examples/synthetic_sample.mbmap`, under a merge-time slot from the Team Leader |
| Design ownership | D125 | Dev PRs do not edit `design/`; measurements and spec gaps go in the PR body |
| Review cap | D89 | At most 3 review rounds per PR. After that, the Team Leader rules, and a coordinator-verified final commit is recorded as a one-off D133 exception (D146, D155, D158, D159) |
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
