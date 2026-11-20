# Edit, export and inspect

1. Generate a map and keep its map collection selected in the panel's
   **Export > Map collection** field.
2. Edit a building: move it, scale it, mirror it, or add a mesh modifier.
   You can also delete or duplicate generated objects and add your own meshes
   to the map collection. Preserve generated `mb_id` metadata.
3. Set **Package** to a new `.mbmap` path in your own output directory.
   **Heightfield spacing (m)** is 2 by default; 0 disables the optional grid.
4. Click **Export Map Package**, then **Validate Package**. Read the status
   message and **MapBuilder Report** text. Resolve errors and assess warnings.

The exported visuals and collision use the same evaluated, world-transformed
triangles. Modifiers are baked into the output, not applied destructively to the
scene. Selection and the active object are preserved. Failed exports retain the
previous package; they do not prove that the new edits were saved.

Curves, text, instances, particles, zero/non-finite transforms and invalid solid
buildings can block export. Convert intentional new geometry to ordinary meshes
and fix the named problem. Unsupported materials are reported; textures and
custom normals are not carried into the flat-shaded GLB.

## Open the visuals

A `.mbmap` is a ZIP **package**, not a Blender import file. First validate it:

The following command is an **unverified template**: replace the example path
with your own package.

```powershell
py -3.12 tools\mbmap_cli.py validate C:\your-output\sample.mbmap
```

To inspect your own validated output, copy it to a new `.zip` path and extract
into a new directory. These commands are **unverified templates**; replace
both paths and use a destination that does not already exist:

```powershell
Copy-Item C:\your-output\sample.mbmap C:\your-output\sample.zip
Expand-Archive C:\your-output\sample.zip C:\your-output\unpacked
```

In a new Blender scene use **File > Import > glTF 2.0 (.glb/.gltf)** and select
`unpacked\visual\map.glb`. Importing the GLB displays visuals only: it does not
reconstruct the add-on's export metadata or load authoritative collision.
Keep the original editable `.blend` separately.

Keep the complete `.mbmap` and its `NOTICES.txt` for consumer use.
`collision\map.mbcol` is authoritative collision; `collision\terrain.mbhf` is
an optional terrain-only convenience grid, not a replacement for all geometry.
Do not edit members inside an existing package: hashes would no longer match.
See [simulator integration status](simulator.md).
