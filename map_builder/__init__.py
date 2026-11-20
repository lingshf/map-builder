"""map-builder: generate editable georeferenced maps in Blender and export validated map packages.

The pure-Python core (``map_builder.core``) never imports ``bpy`` so it can be
unit-tested and used headlessly; Blender modules are imported in register().
"""

bl_info = {
    "name": "Map Builder",
    "author": "map-builder contributors",
    "version": (0, 3, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > Map Builder",
    "description": "Real terrain + OpenStreetMap layout with procedural details; exports GLB + collision map packages",
    "category": "Import-Export",
}

_modules = None


def register():
    global _modules
    from .blender import operators, props, ui
    _modules = (props, operators, ui)
    for m in _modules:
        m.register()


def unregister():
    global _modules
    for m in reversed(_modules or ()):
        m.unregister()
    _modules = None
