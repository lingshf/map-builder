# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""Pure-Python core of map-builder.

Nothing in this package imports ``bpy``; it is unit-testable with a plain
CPython 3.11+ interpreter and uses only the standard library.
"""

PACKAGE_SCHEMA = "map-builder.package"
PACKAGE_SCHEMA_VERSION = "2.1.0"
COLLISION_FORMAT_VERSION = 2
HEIGHTFIELD_FORMAT_VERSION = 1
GENERATOR_NAME = "map-builder"
GENERATOR_VERSION = "0.4.0"
