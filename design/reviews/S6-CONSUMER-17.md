# S6-CONSUMER-TRIAGE: simulator consumer requests (#17)

Task: [S6-CONSUMER-TRIAGE](../tasks/S6.md#s6-consumer-triage-simulator-consumer-requests-17). Issue:
[#17](https://github.com/lingshf/map-builder/issues/17) (lingshf/drone-flight-simulator's `.mbmap` 2.x importer,
design lingshf/drone-flight-simulator#60). Triage only: nothing here is implemented. Facts are taken on main at
**8e96cd9** (2026-11-27) and from the GitHub releases.

## Facts on main

| Fact | Value | Evidence |
|---|---|---|
| Tags and releases | `v0.1.0` … `v0.6.0`, all GitHub pre-releases; no `format-*` tag | `git tag -l`; `gh release list` |
| Writer format | `schema: map-builder.package`, `schema_version` **2.1.0** (default since #49) | sample `manifest.json`; `docs/PACKAGE_FORMAT.md:4–11` |
| Committed sample | `examples/synthetic_sample.mbmap`, last rebuilt at b04b769 (v0.6.0), 694,613 bytes, SHA-256 `5011f1d3b421e390f26ef8c0db28a2e951b37b38fd65b8656ec24c303f4d1213`, `package_id` `sha256:c68ed08db5f0fa110c3e40d1c3b1c046c6cb0bf2ef132aa658e19484b6c88bf9`, `VALID` (1 warning: 2 degenerate collision triangles) | `py -3.12 tools\mbmap_cli.py validate examples\synthetic_sample.mbmap` |
| Sample identity over time | The sample is rebuilt at every release, and `package_id` covers `generator.version`, so it changes every release even when the geometry does not. The consumer's pin (`0958f47`, `sha256:3bcc75e2…`) is an older build. | `docs/releases/v0.6.0.md:163–166` |
| Sample content | Objects: `bridge` 1, `tunnel` 1, `building` 11, `road` 3, `water` 1, `terrain` 2, `vegetation` 63. `.mbcol` classes `bridge` = 7 (solid), `tunnel` = 8 (tube). 4 `passage_probes`: `osm:way/1069:deck` (bridge), `osm:way/1072:bore` (tunnel), `osm:way/1048:under` and `osm:way/1098:passage` (elevated) | sample `manifest.json` (`objects`, `collision.class_kinds`, `passage_probes`) |
| Release checksums | Since v0.4.0 the release notes list each **real-data** asset with bytes, SHA-256 and `package_id`; the committed synthetic sample is not listed, and it is not attached as a release asset | `docs/releases/v0.4.0.md:108–117`, `v0.5.0.md:183–192`, `v0.6.0.md` asset table; `gh release view v0.6.0` assets |
| Licence | Decided (D13, option B, user 2026-11-20): `LICENSE` (Apache-2.0) covers `map_builder/core/`, `tools/`, `docs/` (incl. the format spec) and `examples/` (the C# reader); the Blender add-on is GPL-3.0-or-later (`LICENSE-GPL-3.0.txt`); generated data is not covered by the code licences (ODbL / Copernicus / CC0 apply) | `README.md:270–286`; roadmap D13 |
| Format policy | Draft D101/D110: a minor adds optional content that the frozen previous-minor Python and C# readers load unchanged, no new package members, and ships with a positive frozen-reader fixture; a major (3.0) is any breaking change; readers reject another major. Final only when the user confirms it at v1.0 | `docs/PACKAGE_FORMAT.md:510–531`; roadmap D101, D110 |

## Dispositions

| # | Request | State on main | Disposition |
|---|---|---|---|
| 1 | Stable version marker: a tag or release (at least a format tag such as `format-2.0.0`) that includes the sample | Partly met. Every `v0.N.0` tag is a named, immutable version whose tree contains `examples/synthetic_sample.mbmap`; the format version is in the manifest (`schema_version` 2.1.0). There is no separate format tag. | **Done** for the named release tags (pin `v0.6.0`). **Needs the user** for a separate format tag: tagging is a user decision (D202). Proposal: a lightweight tag `format-2.1.0` on the v0.6.0 commit b04b769, created at the next release by the release manager if the user agrees. |
| 2 | Code licence and a LICENSE file | Met. `LICENSE` exists; the split licence is final (D13). The C# reader under `examples/` and the format spec are Apache-2.0. | **Done.** The reply points out that the simulator may reuse `examples/csharp/MbmapReader` under Apache-2.0 with its notice. |
| 3 | Each release states the sample's `package_id` and file SHA-256 | Partly met: real-data assets have both since v0.4.0; the synthetic sample has neither in the notes. | **New task S7-REL-SAMPLE** (Sprint 7 candidate): the release notes asset table gains a row for `examples/synthetic_sample.mbmap` (bytes, SHA-256, `package_id`, `schema_version`), and the SPRINT_CLOSE release AC checks it. Applies to the next release. |
| 4 | Optional `spawn_points[]` in a 2.x minor (map frame, metres, with heading) | Not present. | **New task S7-SPAWN** (Sprint 7 candidate), a proposed minor **2.2.0** under D101/D110: an optional manifest array (map frame, metres, heading), no new package member. Reader impact: the frozen 2.1 Python and C# readers ignore unknown JSON fields and must load a 2.2.0 package unchanged, proved by the D101 positive frozen-reader fixture in CI; the current readers parse and validate the field. Open scope for the Team Leader: where spawn points come from (Blender empties, a CLI option or an automatic pick) and the validation rules (inside the area, above collision). |
| 5 | A synthetic sample with `bridge`, `tunnel` and non-empty `passage_probes` | Met. The committed sample has one bridge and one tunnel object, `.mbcol` classes 7 and 8, and 4 passage probes (bridge deck, tunnel bore, two elevated). | **Done.** No new sample is needed. |
| 6 | Advance notice before 3.0, and a 2.x sample kept in the repository | No 3.0 is planned. The draft policy defines what a major is, but not a notice period or a kept sample. | **Needs the user**, as part of the D101 confirmation (roadmap "Decisions that need the user", item 3). Proposal to add to D101: a 3.0 is announced on the consumer issue at least one release before it ships, and a 2.x sample stays in `examples/` for at least one release after 3.0. |

New tasks join the Sprint 7 candidates (roadmap); none joins M-S6 unless the Team Leader adds it with a D-number.

## Reply on #17

Posted after this record merges. Draft (no internal process labels, D195):

> Thanks for the list. Where each request stands today:
>
> 1. **Version marker.** Every release is a named tag (`v0.1.0` … `v0.6.0`), and each tag contains
>    `examples/synthetic_sample.mbmap`; the package format version is in the manifest (`schema_version` 2.1.0).
>    Please pin a release tag (currently `v0.6.0`). A separate format tag (`format-2.1.0`) is proposed and waits
>    for the owner's decision.
> 2. **Licence.** Decided. `LICENSE` is Apache-2.0 for the core, the tools, the format spec and `examples/`,
>    including the C# reader, so you may reuse `examples/csharp/MbmapReader` with its notice. The Blender add-on
>    is GPL-3.0-or-later. Generated maps carry their data licences (OSM ODbL, Copernicus).
> 3. **Checksums.** Release notes already list bytes, SHA-256 and `package_id` for the real-data packages. We
>    will add the committed synthetic sample to that table from the next release. Note that the sample is rebuilt
>    at each release and its `package_id` includes the generator version, so it changes every release; in
>    `v0.6.0` it is `sha256:c68ed08db5f0fa110c3e40d1c3b1c046c6cb0bf2ef132aa658e19484b6c88bf9` (file SHA-256
>    `5011f1d3b421e390f26ef8c0db28a2e951b37b38fd65b8656ec24c303f4d1213`).
> 4. **Spawn points.** Planned as a candidate for a 2.2.0 minor: an optional `spawn_points[]` in the manifest (map
>    frame, metres, heading). 2.1 readers ignore it, so your importer keeps working without changes.
> 5. **Bridge and tunnel sample.** Already there: the committed sample has a bridge and a tunnel (collision classes
>    `bridge` and `tunnel`) and four passage probes (bridge deck, tunnel bore, two elevated passages).
> 6. **3.0 notice.** No 3.0 is planned. We propose to announce any 3.0 here at least one release ahead and to keep a
>    2.x sample in `examples/` for at least one release after it; this becomes final with the format stability
>    policy.
