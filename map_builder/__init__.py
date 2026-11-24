# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 lingshf
"""map-builder: generate editable georeferenced maps in Blender and export validated map packages.

The pure-Python core (``map_builder.core``) never imports ``bpy`` so it can be
unit-tested and used headlessly; Blender modules are imported in register().
"""

from __future__ import annotations

from types import ModuleType

bl_info = {
    "name": "Map Builder",
    "author": "map-builder contributors",
    "version": (0, 5, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > Map Builder",
    "description": "Real terrain + OpenStreetMap layout with procedural details; exports GLB + collision map packages",
    "category": "Import-Export",
}

_modules: tuple[ModuleType, ...] | None = None


def register() -> None:
    global _modules
    from .blender import operators, props, ui
    _modules = (props, operators, ui)
    for m in _modules:
        m.register()


def unregister() -> None:
    global _modules
    for m in reversed(_modules or ()):
        m.unregister()
    _modules = None
