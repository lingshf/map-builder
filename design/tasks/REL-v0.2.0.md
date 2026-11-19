# REL-v0.2.0: "fly under bridges and through tunnels"

Owner: release manager · depends on S1-DEMOKIT, S1-SEAMS, S1-BRIDGE, S1-PIERS, S1-TUNNEL
merged · follows [SPRINT_CLOSE.md](SPRINT_CLOSE.md) · demo area D26 (Pittsburgh)

## Scope

RC PR: version 0.2.0, CHANGELOG, `docs/user/` (bridges, tunnels, probes, limits incl. D25),
`docs/flows/` (fly-through check: export → validate → probe results), `docs/demo/v0.2.0/` via
`tools/demo/run_demo.py --preset pittsburgh --before <v0.1.0 demo> --after <new>` with
`--panel`, `docs/releases/v0.2.0.md`.

## Examples (2–3)

1. Fort Pitt Bridge: before (v0.1.0, omitted) / after (deck + piers), `overview` and
   `bridge-under` cameras.
2. Fort Pitt Tunnel: before (hill) / after (portal, headwall), `tunnel-portal` camera;
   leak-test result in the notes.
3. Synthetic sample via the CLI one-liner: validator output with bridge and tunnel probes PASS.

## Acceptance criteria

Common release criteria, plus ≥ 1 bridge and the tunnel generated in the Pittsburgh package
with their probes PASS in the validator and the C# reader; panel screenshot present (D27) or
its recorded limit.

## Performance considerations

Pittsburgh build time (excluding download) recorded in the notes; target ≤ 120 s.

## Conflict domain

Hard: version files, `CHANGELOG.md`, `docs/user/`, `docs/flows/`, `docs/demo/v0.2.0/`,
`docs/releases/v0.2.0.md`. Runs alone.
