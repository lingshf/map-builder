# map-builder documentation entry

This page is the **canonical system entry**. It links to the authoritative page for each topic and records what
the documentation covers. It explains nothing itself: each topic has one authoritative page, and other pages link
to it.

Maintained by the Knowledge Lead; facts are owned by the module owners listed in the matrix. The project overview
and quick start remain in the [root README](../README.md), which links here.

## Reading paths

| You are… | Read in this order |
|---|---|
| **A user** generating a map | [Install](user/install.md) → [Generate](user/generate.md) → [Export](user/export.md) → [CLI](user/cli.md) → [Structures](user/structures.md) → [Limits](../README.md#limits) |
| **A consumer** (Unity, simulator Core) | [Package contract](PACKAGE_FORMAT.md) → [Unity / Core handoff](UNITY_CORE_HANDOFF.md) → [reference reader](../examples/README.md) → [Simulator preview](user/simulator.md) |
| **A new developer or maintainer** | [Architecture](architecture/README.md) → [Developer guide](dev/README.md) → [Validation](VALIDATION.md) → [Backlog](../design/tasks/README.md) → [Definition of Done (charter §4)](../design/team-charter.md#4-definition-of-done) → [decision record](../design/roadmap.md#decision-record) |
| **Taking over the team** | [Team charter](../design/team-charter.md) → [Backlog](../design/tasks/README.md) → [latest close review](../design/reviews/REL-v0.5.0-close.md) → this matrix's gaps |
| **Preparing a release** | [Releases](releases/README.md) → [Demo recipe](DEMO.md) → [Platform submission](PLATFORM_SUBMISSION.md) → [Sprint close](../design/tasks/SPRINT_CLOSE.md) |

## Inventory

| Page | Purpose | Audience | Owner of facts |
|---|---|---|---|
| [../README.md](../README.md) | Overview, install, workflow, privacy, licences, CLI, tests, limits | users, all | Product/Design (scope); Developer (commands) |
| [user/](user/README.md) (install, generate, export, cli, structures, simulator) | How-to guides | users | Developer; Delivery/Release refreshes them per release (D28) |
| [flows/](flows/overview.md) | Workflow diagrams (generate, export, fly-through, consumer) | users | Delivery/Release |
| [architecture/README.md](architecture/README.md) | Pipeline, export paths, package and consumer, decision map | developers | Product/Design (architecture); Developer (code entries) |
| [dev/README.md](dev/README.md) | Repository map, local checks, workflow, adding a feature type, licence | developers | Developer |
| [PACKAGE_FORMAT.md](PACKAGE_FORMAT.md) | **Normative** `.mbmap` contract, format policy | consumers, developers | Developer (facts); Product/Design (format decisions) |
| [UNITY_CORE_HANDOFF.md](UNITY_CORE_HANDOFF.md) | Consumer integration guide and checklist | consumers | Developer |
| [VALIDATION.md](VALIDATION.md) | What is tested, how to run, recorded results, what is not validated | developers, QA | QA (results); Developer (commands) |
| [DEMO.md](DEMO.md), `demo/<ver>/` | Real-data demo recipe and recorded results | release, users | Delivery/Release |
| [releases/](releases/README.md), [../CHANGELOG.md](../CHANGELOG.md) | Version-specific notes | users | Delivery/Release |
| [PLATFORM_SUBMISSION.md](PLATFORM_SUBMISSION.md) | Blender Extensions submission checklist | user, release | Delivery/Release |
| [../design/](../design/roadmap.md) | Goals, decisions (ADR equivalent), task specs, reviews, charter | team | Product/Design; Team Leader (charter) |

## Coverage matrix (four goals)

Audited on 2026-11-24 against main `873aa36`.

**States:**

* `covered`: the authoritative page answers the goal for the current main.
* `gap`: there is no answer.
* `stale`: an answer exists, but describes an older main.
* `conflict`: two pages disagree.
* `unknown`: not yet checked.
* `n/a`: not applicable, with the reason given.

**How to read it:** this is a **structural** audit only. "Covered" means a current page exists and addresses the
goal. It is **not** owner-verified factual truth or QA-executed procedure; that verification is still pending for
every row. No completion percentage is implied.

**Goals:**

* **Design:** boundaries and data flow.
* **Implementation:** code entries and how to extend.
* **Trade-offs:** decisions and alternatives.
* **Usage:** run, configure and troubleshoot.

| Component / scope | Design | Implementation | Trade-offs | Usage | Authoritative page(s) | Gap rows |
|---|---|---|---|---|---|---|
| Acquisition and DSM (DEM, OSM, cache, DSM correction) | covered | covered (pending owner check) | covered | covered | [architecture §From sources to package](architecture/README.md#from-sources-to-package); `design/roadmap.md` D15; user/generate §DSM | DOC-ARCH |
| Terrain, roads, vegetation, buildings | covered | covered (pending owner check) | covered | covered | [architecture §From sources to package](architecture/README.md#from-sources-to-package); user/generate | DOC-ARCH |
| Roofs (skeleton, gabled/hipped, vertical-cut ends, named fallbacks) | covered (pending owner check) | covered (pending owner check) | covered (D54–D107) | covered | [architecture §From sources to package](architecture/README.md#from-sources-to-package); user/generate §roofs; roadmap S3/S4 | DOC-ARCH |
| Bridges, tunnels, passages, probes | covered | covered | covered (D18–D25) | **stale**: title says v0.3.0, body cites v0.5.0 | user/structures; [architecture §From sources to package](architecture/README.md#from-sources-to-package) | DOC-USER-STRUCT |
| Water: surfaces, carved bed, bank colour, shore ramps, cascades | covered (pending owner check) | covered (pending owner check) | covered (pending owner check) | covered | design, implementation, trade-offs: [architecture §Water and shores](architecture/README.md#water-and-shores); decisions: [roadmap](../design/roadmap.md#decision-record); usage: [user/generate §Water](user/generate.md#water-rivers-and-lakes); contract: [PACKAGE_FORMAT](PACKAGE_FORMAT.md), [UNITY_CORE_HANDOFF](UNITY_CORE_HANDOFF.md); open findings: [S5-F3](../design/tasks/S5-F3.md) | DOC-ARCH, DOC-WATER-DESIGN (review) |
| Textures and UVs | covered (pending owner check) | covered (pending owner check) | covered (D57–D65, D86, D99, D124) | covered (user/generate §textures) | user/generate; PACKAGE_FORMAT §textures | DOC-ARCH |
| Blender add-on (panel, scene build, bake, export) | covered | covered (pending owner check) | covered | covered | [architecture §Two export paths](architecture/README.md#two-export-paths); usage: [user/](user/README.md) guides | DOC-ARCH |
| CLI | covered | covered | n/a (shares the core, D1) | covered | user/cli; README §CLI | — |
| Package format and consumer contract | covered | covered | covered (D101, D110 format policy) | covered | PACKAGE_FORMAT (normative); UNITY_CORE_HANDOFF | — |
| C# reference reader | covered | covered | covered | covered | examples/README; PACKAGE_FORMAT | — |
| Validation and tests | covered | **stale**: dev guide CI description omits the mypy step (Python 3.12 leg) and the format-policy step (C# job) | covered | covered; VALIDATION.md line 117 has a stray control character (`\b` from a backtick) in the S4-COL-DEGEN row | VALIDATION; dev/README §checks | DOC-DEV |
| Contribution workflow and DoD | covered | n/a | covered | covered: [team charter §4](../design/team-charter.md#4-definition-of-done) is the only DoD; the Backlog and dev guide link to it (deduplicated in this change) | team charter §4 | — |
| Developer tools: `floating_audit`, `water_replay`, `water_check`, `design/bench` | gap | **gap**: no developer-facing usage page; only VALIDATION rows and task specs | covered in specs and decisions | **gap** | VALIDATION rows; task specs | DOC-TOOLS |
| Performance method (D91, D106, D147, D153) | covered (roadmap) | gap (S5-PERF-GATE tool not built yet) | covered | stale: dev/README has no performance section | roadmap; S5-PERF-GATE spec | DOC-PERF (after S5-PERF-GATE) |
| Release and extension packaging | covered | covered | covered (D100) | covered | releases/README; PLATFORM_SUBMISSION; SPRINT_CLOSE | — |
| Stylized look (S5, planned) | covered (spec) | n/a (not built) | covered (D136–D157) | n/a (not built) | design/tasks/S5-STYLE.md | user docs are added by each S5 task |
| Team process and authority | covered | n/a | covered | covered | design/team-charter.md | — |

**Deduplication decisions:**

* **Definition of Done:** the [team charter §4](../design/team-charter.md#4-definition-of-done) is the only DoD. The
  Backlog section and dev/README §Workflow now only link to it.
* **Decision record:** the roadmap's decision table is the only authority. [architecture §Decision pointers](architecture/README.md#decision-pointers) stays a
  short pointer list (DOC-ARCH removes its stale status claims).
* **Water design:** the authoritative explanation goes into the architecture page, not a new standalone document.
  User and consumer pages keep their usage and contract sections and link to it.

Gaps are tracked as Backlog rows in [design/tasks/README.md](../design/tasks/README.md#knowledge-gaps). This page is
re-audited at each milestone (next: M-S5) and before any handoff.
