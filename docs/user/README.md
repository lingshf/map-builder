# User guide

Map Builder runs inside Blender 4.2 LTS. It creates editable maps and exports
visuals plus engine-neutral collision; it is not a flight simulator.

1. [Install the extension](install.md).
2. [Generate an offline sample or a real map](generate.md).
3. [Edit, export and inspect GLB / .mbmap](export.md).
4. [Fly under bridges, through tunnels and passages: probes and limits](structures.md).
5. [Understand the simulator handoff](simulator.md).
6. [Build and validate with the CLI; use demo presets](cli.md).

For development see the [developer guide](../dev/README.md); for the current
pipeline and package design see the [architecture overview](../architecture/README.md).

See the [v0.4.0 demo](../demo/v0.4.0/README.md) (non-rectangular roofs and
textures on Munich and Pittsburgh; [reproduce it](../DEMO.md)), the
[v0.3.0 real-data demo](../demo/v0.3.0/README.md), the [v0.2.0 Pittsburgh bridge/tunnel demo](../demo/v0.2.0/README.md),
the [v0.1.0 editing demo](../demo/v0.1.0/README.md) and the
[real Blender sidebar](../demo/v0.4.0/panel.png), plus the
[workflow overview](../flows/overview.md) and [fly-through check](../flows/flythrough.md).
The [package contract](../PACKAGE_FORMAT.md)
is normative when implementing a reader.
