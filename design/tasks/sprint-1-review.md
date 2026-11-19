# sprint-1-review: v0.2.0 "fly under bridges and through tunnels"

Sprint S1 · depends on S1-RELEASE-WF, S1-DEMOKIT, S1-SEAMS, S1-BRIDGE, S1-PIERS, S1-TUNNEL
merged, demo area D26 · follows [SPRINT_REVIEW.md](SPRINT_REVIEW.md)

## Examples (2–3)

1. Demo area (D26) main bridge: before (v0.1.0 code: bridge omitted) / after (deck + piers),
   `overview` and `bridge-under` cameras.
2. Demo area tunnel: before (hill, no opening) / after (portal, headwall), `tunnel-portal`
   camera; leak-test result in the notes.
3. Synthetic sample via the CLI one-liner: validator output with bridge and tunnel probes PASS.

The "before" package is built from the `v0.1.0` tag with the same preset (v0.1.0 has no sample
package attached).

## Review focus

Shared sweep and probe helper used by both bridges and tunnels (no duplication), hooks-only
changes in `generate.py`, D21–D23 honoured, `run_integration.py` split kept small.

## Conflict domain

As SPRINT_REVIEW.md with N = 2.
