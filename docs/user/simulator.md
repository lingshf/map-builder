# Simulator use: integration preview

**v0.1.0 does not add a playable map loader to
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
classes and passage probes, but generated flyable passages are not in this
baseline. Older schema 1.x packages must be regenerated for the current reader.
