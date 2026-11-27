# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""Genuine exported package with a visual-only ``MB Decor`` primitive (S5-DECOR step 1a).

``python -m tests.make_decor_fixture OUT.mbmap`` writes the synthetic package through the real headless
exporter (:func:`pipeline.plan_to_package`) with decoration triangles added to the terrain mesh. The decoration
has no collision, so ``.mbcol`` and ``.mbhf`` equal those of the same package without it.
"""

import os
import sys
import tempfile

from map_builder.core import pipeline
from map_builder.core.generate import PlanOptions, build_plan
from map_builder.core.mesh import DECOR_MATERIAL

from .synthetic import synthetic_inputs

UTC = "2024-01-01T00:00:00Z"
DECOR_HEIGHT_M = 0.1
DECOR_COLOUR = (0.2, 0.5, 0.2)


def terrain_mesh(plan):
    node = next(o for o in plan.objects if o.mb_class == "terrain")
    return node.mesh_data(plan.shared_meshes)


def add_decor_face(mesh, material=DECOR_MATERIAL):
    """Append one triangle of ``material`` hovering ``DECOR_HEIGHT_M`` above the first terrain triangle."""
    face = next(mesh.triangles())
    base = len(mesh.vertices)
    mesh.vertices.extend((x, y, z + DECOR_HEIGHT_M) for x, y, z in (mesh.vertices[i] for i in face))
    mesh.faces.append((base, base + 1, base + 2))
    mesh.face_materials.append(mesh.material_index(material))
    mesh.face_colors.append(DECOR_COLOUR)


def build_package(path, material=None, heightfield_spacing=5):
    """Write the synthetic package; with ``material`` it carries one extra terrain triangle of that material."""
    with tempfile.TemporaryDirectory() as tmp:
        area, grid, cl, _ids, sources = synthetic_inputs(os.path.join(tmp, "src"))
        plan = build_plan(area, grid, cl, PlanOptions(seed=1))
        if material is not None:
            add_decor_face(terrain_mesh(plan), material)
        return pipeline.plan_to_package(plan, path, "synthetic_decor", sources,
                                        heightfield_spacing=heightfield_spacing, created_utc=UTC)


if __name__ == "__main__":
    build_package(sys.argv[1], DECOR_MATERIAL)
