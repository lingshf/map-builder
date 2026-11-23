# Bridges, tunnels and passages (v0.3.0)

Map Builder generates places you can fly **under or through**. Each one is an
ordinary editable Blender object. It is exported as collision with its own
class, plus a **passage probe**: a capsule path that must stay clear of all
collision. Use the probes to check a map before you hand it to a simulator.
See the [fly-through check flow](../flows/flythrough.md) and the
[v0.3.0 real-data demo](../demo/v0.3.0/README.md) (Pittsburgh bridges and
tunnel; Munich elevated part, building passage and roofs).

## What is generated

| Feature (OSM) | Generated object | Passage probe |
|---|---|---|
| `highway=*` + `bridge=*` (not `no`) | Deck solid (class `bridge`): road width + 2 x 0.5 m wide, 1 m thick. Parapets 1 m high are added where the deck is wide enough. **Piers** are added where the deck stands more than 6 m above the ground (about every 40 m, moved off roads beneath). | `<id>:deck` 1.5 m above the deck. `<id>:under` beside the span, only where clearance is at least 4 m. Radius 1 m. |
| `highway=*` + `tunnel=*` | Tube with an arched roof (class `tunnel`), 4.5 m walls by default. The terrain is cut **only** inside the bore. A 1 m headwall (class `structure`) closes the cutting at each portal. The heightfield cells over the bore are NaN. | `<id>:bore` through the tube and 3 m past each portal. Radius up to 1.5 m. |
| Building with `min_height` / `building:part` raised off the ground | Elevated part as a closed solid with empty space beneath. | `<id>:under` when at least 2.6 m of free height remains. |
| `tunnel=building_passage` or `covered=yes` highway crossing a building | The building is split into lower parts and an upper part above the passage. The passage road stays at grade (default height 4.5 m, 2.5–10 m from `maxheight`). | `<id>:passage` (kind `elevated`). |

Deck heights follow the OSM `layer`: each layer needs 5 m of clearance over
the ground. The deck profile stays linear between its at-grade ends and rises
within an **8 % ramp** where it needs more height. `report.json` counts the
results under `counts.bridges`, `counts.tunnels` and `counts.tunnel_headwalls`.

## Blocked probes are reported, not exported

After the whole scene is built, the generator re-checks every probe against
the finished collision (D21). A probe that collision blocks at generation is
**not exported** (a generator omission, not a validation result). It is listed in
`report.json` under `passage_probes_blocked`, together with the blocking
`mb_id`. On real data this is common and expected:

- Stacked decks (for example Fort Pitt Bridge's double deck): the upper deck
  blocks the lower deck's clearance probe.
- Short interchange ramps that meet the ground or another road.
- Clearance or grade warnings, where the OSM `layer` asks for more height than
  an 8 % ramp can reach.

Read these entries instead of assuming that every bridge has every probe. The
v0.5.0 Pittsburgh demo exports 11 probes and reports 31 blocked ones (v0.4.0:
13 and 29). The change comes from the rivers: one bridge's clearance probe now
starts over the water and runs into a pier of the next bridge, and one
low deck's probe capsule reaches below the new water surface. A probe never
passes through water.

## Real-data example: Munich Altstadt

The `munich-altstadt` demo preset (48.1395 N, 11.5764 E, 400 x 400 m) has
all three building and road structures on real OSM data:

| Probe | Kind | What it is |
|---|---|---|
| `osm:way/879138845:under` | elevated | Space beneath a raised building part (`min_level`) |
| `osm:way/1163022325:passage` | elevated | Rid Passage, a way through a building (building passage) |
| `osm:way/405100898:bore` | tunnel | Road tunnel, radius 1.5 m |

All three PASS in the Python validator and in the C# reader. `report.json`
counts 2 building passages and 26 tunnel ways. The tunnel ways form a joined
underground road network, so neighbouring tubes block 25 of the 26 bore probes,
and another object blocks the second passage's probe. All 26 are listed in
`passage_probes_blocked`.

## Check a package

These are **unverified templates**: replace `my_map.mbmap` with your own package.
The same validators were run on the committed synthetic sample; see the
[CLI guide](cli.md).

```powershell
py -3.12 tools\mbmap_cli.py validate my_map.mbmap
dotnet run -c Release --project examples\csharp\MbmapReader -- my_map.mbmap
```

The Python validator tests every exported probe. A blocked or unchecked probe
is a **warning, not an error**, so the package can still be `VALID`:

- `passage probe N is blocked by collision object #M`: probe N is obstructed.
- `passage_probes: query budget ... exhausted; probes A..B were not checked`:
  those probes were **not tested**, which is different from PASS.

The C# reference reader prints one `passage N ... PASS` line per probe and
reports the same two cases. Both checkers count query work the same way (the
v0.5.0 Pittsburgh demo: 11 of 11 checked and PASS in each).

**Before flying, stop on any blocked or unchecked probe, even if the package
is `VALID`.** `VALID` alone does not mean that every probe was checked and clear.

## If you edit structures

Edited decks, tubes and piers export like any other mesh. **Probes are kept
from generation, not recalculated from your edits.** If you lower a deck or move
a pier into a probe path, the export **still succeeds and replaces the previous
package**. Validation reports `passage probe N is blocked ...` as a warning, not
an error. Read the export's validation warnings. If a probe is blocked, undo
the edit or regenerate the map, and do not fly that passage. If you delete a structure, its probes are not exported and their IDs are listed
in the exported `report.json` `passage_probes_dropped`. The list also keeps the generation-time entries (missing passage road, probe cap) as `{id, reason}`; a deleted structure's probes are added with `reason: "feature_deleted"`.

## Limits (D25)

- Only **highway** bridges and tunnels are generated. Railway bridges and
  tunnels (including funiculars), culverts, `man_made=bridge` outlines and
  `man_made=tunnel` are reported as unsupported in `report.json`.
- Decks are simple swept rectangles: there are no trusses, arches, cables or
  railings beyond the parapet. Piers are simple boxes; their positions are
  generated, not taken from the real bridge.
- Ways are clipped to the area: only the part inside the map is generated.
  For example, the Pittsburgh demo shows the north Fort Pitt Tunnel portals
  but not the southern ends.
- Probes are sanity checks for a 1–1.5 m capsule, not a guarantee that a given
  aircraft fits. Your simulator must still use the exported triangle collision.
- Water surfaces are collision (class 5). A bridge deck is never lowered to
  meet a river; where a deck would sit too close to the water it is raised and
  listed in eport.json water_decks_raised. Piers reach the carved bed.
- A heightfield alone cannot represent underpasses. Use the triangle collision
  (bridge, tunnel and structure classes) for flight.
