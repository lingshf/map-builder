# Install from disk

Use Blender **4.2 LTS** (release tooling uses 4.2.23). Later versions have not been
qualified by this release.

1. Download `map_builder-0.3.0.zip` from the [v0.3.0 release](https://github.com/lingshf/map-builder/releases/tag/v0.3.0),
   or build an extension from the source checkout as described below.
2. In Blender, open **Edit > Preferences > Get Extensions**, open the dropdown menu,
   choose **Install from Disk...**, and select the zip **without unpacking it**.
3. Enable Map Builder if it is not already enabled. In a 3D Viewport press **N**,
   then select the **Map Builder** sidebar tab.
4. Start with the [offline sample](generate.md). It requires no network permission.

Build from the repository root in PowerShell, replacing the executable path.
This is a **template, unverified with the placeholder path**; validation and
build were verified with Blender 4.2.23 in the documentation audit.

```powershell
$blender = "C:\path\to\blender.exe"
New-Item -ItemType Directory -Force dist | Out-Null
& $blender --command extension validate map_builder
& $blender --command extension build --source-dir map_builder --output-dir dist
```

Use the extension zip, not GitHub's automatic **Source code (zip)** archive.
For online sources, explicitly enable
**Preferences > System > Network > Allow Online Access**. A disabled network
permission produces an error, never a substitute flat map.

If the sidebar is missing, verify that the extension is enabled and that the
active editor is a 3D Viewport. This is a Blender extension, not a standalone app.
The code licence is provisionally GPL-3.0-or-later pending owner confirmation.
