# Simulator use: integration preview

**v0.5.0 does not add a playable map loader to
lingshf/drone-flight-simulator.** This release delivers a package contract, a
sample and a reference reader. No simulator files are changed by installing the
Blender extension.

For a quick consumer-side check, install the .NET 8 SDK and run from this
repository's root:

```powershell
dotnet run -c Release --project examples\csharp\MbmapReader -- examples\synthetic_sample.mbmap
```

Expected result: `OK` and exit code 0. You can substitute your own validated
`.mbmap`. This verifies the reference reader, **not an integrated flight test**.

Integration developers should follow [Unity / Core handoff](../UNITY_CORE_HANDOFF.md):
verify container bounds and member hashes before accepting the package identity,
load authoritative collision into the physics Core, load GLB into presentation,
and verify the orientation probes. Record `package_id` for replay compatibility.
Ship and display source attribution from `NOTICES.txt`.

The map uses ENU metres; glTF and Unity have different axis conventions.
Do not guess axes or derive gameplay collision from imported visual meshes.
A heightfield cannot represent underpasses. Schema 2.0 supports bridge/tunnel
classes and passage probes. Road tunnels are generated as flyable tubes with a bore passage probe and a
matching heightfield hole (NaN cells). Highway bridges are generated (a bridge's `under` probe exists only where
its clearance is at least 4 m). Elevated building parts and `tunnel=building_passage`
ways through buildings are generated as flyable passages, each with a passage probe
(a probe that collision blocks is left out and listed in the report). Older schema 1.x packages must be regenerated for the current reader.
Packages from v0.4.0 are schema 2.1.0. The only addition is optional
textures: UVs and embedded CC0 images in the GLB, and an `asset_notices` list
in the manifest. A 2.0 reader (such as the v0.3.0 C# reader) accepts them and
ignores both. The collision and heightfield do not depend on textures, so
`--no-textures` changes only the visuals. A Unity glTF importer that reads
embedded PNGs shows the textures; ship the textures' CC0 notice from
`NOTICES.txt` along with the map data notices.
Since v0.5.0, rivers inside the map are flat water surfaces exported as
collision class 5 (water) over a carved bed; treat class 5 as a surface your
simulator decides how to handle (land, splash or crash). The heightfield
.mbhf stays terrain-only and therefore shows the bed below the water, so
use the triangle collision over rivers. The schema is still 2.1.0.
Check every probe before flight: see [bridges, tunnels and passages](structures.md).
