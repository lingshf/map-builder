# Bridges, tunnels and passages (v0.2.0)

v0.2.0 generates places you can fly **under or through**. Each one is an
ordinary editable Blender object. It is exported as collision with its own
class, plus a **passage probe**: a capsule path that must stay clear of all
collision. Use the probes to check a map before you hand it to a simulator.
See the [fly-through check flow](../flows/flythrough.md) and the
[Pittsburgh demo](../demo/v0.2.0/README.md).

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
the finished collision (D21). A probe that collision blocks is **not
exported**: an exported probe would fail validation. It is listed in
`report.json` under `passage_probes_blocked`, together with the blocking
`mb_id`. On real data this is common and expected:

- Stacked decks (for example Fort Pitt Bridge's double deck): the upper deck
  blocks the lower deck's clearance probe.
- Short interchange ramps that meet the ground or another road.
- Clearance or grade warnings, where the OSM `layer` asks for more height than
  an 8 % ramp can reach.

Read these entries instead of assuming that every bridge has every probe. The
Pittsburgh demo exports 13 probes and reports 29 blocked ones.

## Check a package

```powershell
py -3.12 tools\mbmap_cli.py validate my_map.mbmap
dotnet run -c Release --project examples\csharp\MbmapReader -- my_map.mbmap
```

The Python validator tests every exported probe and fails the package if one
is blocked. The C# reference reader prints one `passage N ... PASS` line per
probe. A `query budget ... exhausted; probes A..B were not checked` warning
means those probes were **not tested**, which is different from PASS.

> **v0.2.0 RC note (D46):** on large real maps the C# reader currently uses
> up its query budget before the last Pittsburgh probes, including both Fort
> Pitt Tunnel bores. It also warns `unrecognised mb_id form` for tunnel headwall
> ids such as `osm:way/N:headwall0`. Both issues are being fixed (FIX-CS-PROBE-PARITY)
> before v0.2.0 is final, and this note will be updated then.

## If you edit structures

Edited decks, tubes and piers export like any other mesh. **Probes are kept
from generation, not recalculated from your edits.** If you lower a deck or move
a pier into a probe path, validation fails and the previous package is kept.
Regenerate the map, or undo the edit. If you delete a structure, its probes are
not exported and are listed in `report.json` `passage_probes_dropped`.

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
- A heightfield alone cannot represent underpasses. Use the triangle collision
  (bridge, tunnel and structure classes) for flight.
