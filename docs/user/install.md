# Install from disk

Use Blender **4.2 LTS** (release tooling uses 4.2.23). Later versions have not been
qualified by this release.

1. When the authorized v0.1.0 pre-release is published, download
   `map_builder-0.1.0.zip` from its GitHub Release assets. Until then, build it from
   the release-candidate checkout with the commands below.
2. In Blender, open **Edit > Preferences > Get Extensions**, open the dropdown menu,
   choose **Install from Disk...**, and select the zip **without unpacking it**.
3. Enable Map Builder if it is not already enabled. In a 3D Viewport press **N**,
   then select the **Map Builder** sidebar tab.
4. Start with the [offline sample](generate.md). It requires no network permission.

Build from the repository root in PowerShell, replacing the executable path:

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
