"""Pure (bpy-free) tests of the Blender layer's export baking and settings helpers
(map_builder/blender/bake.py and sources.py). The Blender side itself is covered by the headless
integration test tests/blender/run_integration.py, which needs Blender and is not run here."""

import hashlib
import json
import math
import os
import shutil
import tempfile
import unittest
import zipfile

from map_builder.blender.bake import (DEFAULT_MATERIAL, ExportError, bake_object, det3, export_baked, package_parts,
                                      transform_problem)
from map_builder.blender.sources import (ENV_OVERPASS_URL, SettingsInputError, endpoint_problem, format_report,
                                         needs_network, redact_diagnostics, settings_kwargs)
from map_builder.core.errors import PackageError
from map_builder.core.generate import MATERIALS, PlanOptions, build_plan
from map_builder.core.osm import DEFAULT_OVERPASS_URL
from map_builder.core.package import validate_package
from map_builder.core.pipeline import Settings

from .synthetic import chiral_mesh, synthetic_inputs

UTC = "2024-01-01T00:00:00Z"


def trs(loc=(0.0, 0.0, 0.0), rz=0.0, scale=(1.0, 1.0, 1.0), rx=0.0):
    """4x4 row-major world matrix T * Rz * Rx * S."""
    c, s = math.cos(rz), math.sin(rz)
    cx, sx = math.cos(rx), math.sin(rx)
    rzm = [[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]]
    rxm = [[1.0, 0.0, 0.0], [0.0, cx, -sx], [0.0, sx, cx]]
    r = [[sum(rzm[i][k] * rxm[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
    m = [[r[i][j] * scale[j] for j in range(3)] + [loc[i]] for i in range(3)]
    return m + [[0.0, 0.0, 0.0, 1.0]]


def signed_volume(verts, tris):
    v = 0.0
    for a, b, c in tris:
        (ax, ay, az), (bx, by, bz), (cx, cy, cz) = verts[a], verts[b], verts[c]
        v += ax * (by * cz - bz * cy) - ay * (bx * cz - bz * cx) + az * (bx * cy - by * cx)
    return v / 6.0


def baked_from_spec(spec, plan, matrix=None, name=None, mb_id=None):
    md = spec.mesh if spec.mesh is not None else plan.shared_meshes[spec.mesh_key]
    tris = list(md.triangles())
    mats, cols = [], []
    for fi, f in enumerate(md.faces):
        for _ in range(len(f) - 2):
            mats.append(md.materials[md.face_materials[fi]])
            cols.append(md.face_colors[fi])
    s = spec.scale if isinstance(spec.scale, (tuple, list)) else (spec.scale,) * 3
    m = matrix or trs(spec.location, spec.rotation_z, s)
    return bake_object(name or spec.name, md.vertices, tris, m, mats, cols, mb_id=mb_id or spec.mb_id,
                       mb_class=spec.mb_class, provenance=spec.provenance)


class BakeTransformTest(unittest.TestCase):
    def test_zero_scale_singular_and_non_finite_are_rejected(self):
        self.assertIsNone(transform_problem(trs(scale=(2.0, 0.5, 3.0))))
        self.assertIn("zero scale", transform_problem(trs(scale=(1.0, 1.0, 0.0))))
        shear = [[1.0, 1.0, 0.0, 0.0], [1.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]
        self.assertIn("singular", transform_problem(shear))
        bad = trs()
        bad[0][3] = float("nan")
        self.assertIn("non-finite", transform_problem(bad))
        proj = trs()
        proj[3][0] = 0.5
        self.assertIn("affine", transform_problem(proj))
        md = chiral_mesh()
        tris = list(md.triangles())
        with self.assertRaises(ExportError) as cm:
            bake_object("flat", md.vertices, tris, trs(scale=(0.0, 1.0, 1.0)))
        self.assertIn("flat: zero scale", cm.exception.errors[0])
        verts = list(md.vertices)
        verts[0] = (float("inf"), 0.0, 0.0)
        with self.assertRaises(ExportError):
            bake_object("inf", verts, tris, trs())
        with self.assertRaises(ExportError):
            bake_object("far", md.vertices, tris, trs(loc=(2e6, 0.0, 0.0)))
        with self.assertRaises(ExportError):
            bake_object("idx", md.vertices, [(0, 1, 99)], trs())

    def test_mirrored_matrix_keeps_outward_winding(self):
        md = chiral_mesh()
        tris = list(md.triangles())
        vol0 = signed_volume(md.vertices, tris)
        self.assertGreater(vol0, 0)
        for scale in ((-1.0, 1.0, 1.0), (1.0, -2.0, 0.5), (-1.0, -1.0, -1.0), (1.5, 0.7, 2.0)):
            m = trs((3.0, -4.0, 1.0), 0.7, scale, rx=0.2)
            b = bake_object("c", md.vertices, tris, m)
            self.assertEqual(b.mirrored, det3(m) < 0)
            vol = signed_volume(b.vertices, b.triangles)
            expected = vol0 * abs(scale[0] * scale[1] * scale[2])
            self.assertAlmostEqual(vol, expected, places=6, msg=str(scale))

    def test_loose_vertices_are_dropped_and_reindexed(self):
        verts = [(0, 0, 0), (9, 9, 9), (1, 0, 0), (0, 1, 0)]
        b = bake_object("t", verts, [(0, 2, 3)], trs(loc=(1.0, 2.0, 3.0)))
        self.assertEqual(b.unused_vertices, 1)
        self.assertEqual(b.vertices, [(1.0, 2.0, 3.0), (2.0, 2.0, 3.0), (1.0, 3.0, 3.0)])
        self.assertEqual(b.triangles, [(0, 1, 2)])
        self.assertEqual(b.tri_materials, [DEFAULT_MATERIAL])


class BakeExportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        area, grid, classified, cls.ids, cls.sources = synthetic_inputs(cls.tmp)
        cls.area = area
        cls.plan = build_plan(area, grid, classified, PlanOptions(seed=1))
        cls.generated = [o.mb_id for o in cls.plan.objects]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def edited_scene(self):
        """Baked objects after typical edits: transform/mirror a building, delete one, duplicate one,
        add a user object."""
        buildings = [o for o in self.plan.objects if o.mb_class == "building"]
        moved, deleted, duped, mirrored = buildings[:4]
        baked = []
        for spec in self.plan.objects:
            if spec is deleted:
                continue
            if spec is moved:
                m = trs((spec.location[0] + 7.0, spec.location[1] - 3.0, spec.location[2]), spec.rotation_z + 0.4,
                        (1.3, 0.8, 1.5), rx=0.05)
                baked.append(baked_from_spec(spec, self.plan, m))
            elif spec is mirrored:
                m = trs(spec.location, spec.rotation_z, (-1.0, 1.0, 1.0))
                baked.append(baked_from_spec(spec, self.plan, m))
            else:
                baked.append(baked_from_spec(spec, self.plan))
        baked.append(baked_from_spec(duped, self.plan, trs((duped.location[0], duped.location[1] + 20.0,
                                                            duped.location[2])), name=duped.name + ".001"))
        md = chiral_mesh("user_thing")
        baked.append(bake_object("user_thing", md.vertices, list(md.triangles()), trs((10.0, 10.0, 5.0)),
                                 provenance={"ignored": True}))
        return baked, moved, deleted, duped, mirrored

    def test_edited_scene_exports_valid_package_with_identities(self):
        baked, moved, deleted, duped, mirrored = self.edited_scene()
        path = f"{self.tmp}/edited.mbmap"
        report = {"warnings": [], "unsupported_features": [], "invalid_features": [],
                  "z_offset_m": self.area.frame.z_offset}
        manifest, result, edits = export_baked(path, "edited", self.area, self.sources, baked, self.generated,
                                               MATERIALS, report, blender_version="4.2.23 LTS",
                                               heightfield_spacing=5.0, created_utc=UTC)
        self.assertTrue(result.ok, result.summary())
        r = validate_package(path)
        self.assertTrue(r.ok, r.summary())
        self.assertEqual(edits["removed"], [deleted.mb_id])
        self.assertEqual(edits["duplicated"], [{"object": duped.name + ".001", "source_id": duped.mb_id}])
        self.assertEqual(edits["user_added"], ["user_thing"])
        ents = {e["name"]: e for e in r.collision.objects}
        self.assertEqual(ents[duped.name + ".001"]["mb_id"], f"{duped.mb_id}~{duped.name}.001")
        self.assertEqual(ents[duped.name]["mb_id"], duped.mb_id)
        self.assertEqual((ents["user_thing"]["mb_id"], ents["user_thing"]["class"]), ("user:user_thing", "user"))
        self.assertEqual(ents[moved.name]["mb_id"], moved.mb_id)
        objs = {o["name"]: o for o in manifest["objects"]}
        self.assertEqual(objs["user_thing"]["provenance"]["source"], "user-added in Blender (no generated identity)")
        self.assertIn("duplicate of", objs[duped.name + ".001"]["provenance"]["edit"])
        # collision == baked world triangles (float32 storage)
        b = next(x for x in baked if x.name == moved.name)
        got = r.collision.object_triangles(ents[moved.name])
        want = [tuple(b.vertices[i] for i in t) for t in b.triangles]
        self.assertEqual(len(got), len(want))
        err = max(abs(p - q) for tg, tw in zip(got, want) for pg, pw in zip(tg, tw) for p, q in zip(pg, pw))
        self.assertLess(err, 1e-4)
        self.assertTrue(next(x for x in baked if x.name == mirrored.name).mirrored)

    def test_probe_of_deleted_feature_is_dropped_and_reported(self):
        baked, moved, deleted, *_ = self.edited_scene()
        path = f"{self.tmp}/probes.mbmap"
        hi = 400.0                                    # far above the synthetic scene: never blocked
        keep = {"id": "p-keep", "kind": "bridge", "feature": moved.mb_id, "path_map": [[0, 0, hi], [10, 0, hi]],
                "radius_m": 1.0}
        gone = dict(keep, id="p-gone", feature=deleted.mb_id)
        manifest, result, _ = export_baked(path, "probes", self.area, self.sources, baked, self.generated, MATERIALS,
                                           {}, created_utc=UTC, passage_probes=[keep, gone])
        self.assertTrue(result.ok, result.summary())
        self.assertEqual(manifest["passage_probes"], [keep])
        with zipfile.ZipFile(path) as z:
            self.assertEqual(json.loads(z.read("report.json"))["passage_probes_dropped"], ["p-gone"])
        stray = dict(keep, id="p-stray", feature="osm:way/999999")      # never part of the plan: refused
        with self.assertRaises(PackageError):
            export_baked(f"{self.tmp}/stray.mbmap", "probes", self.area, self.sources, baked, self.generated,
                         MATERIALS, {}, created_utc=UTC, passage_probes=[keep, stray])
        self.assertFalse(os.path.exists(f"{self.tmp}/stray.mbmap"))

    def test_malformed_probe_metadata_fails_export_cleanly(self):
        """Review round 2: a JSON null is malformed (not "no probes"), and oversized integers give a
        PackageError instead of an OverflowError, through export_baked and the Blender export_map path."""
        baked, moved, *_ = self.edited_scene()
        keep = {"id": "p", "kind": "bridge", "feature": moved.mb_id, "path_map": [[0, 0, 400], [10, 0, 400]],
                "radius_m": 1.0}
        cases = {"null": None, "huge radius": [dict(keep, radius_m=10 ** 400)],
                 "huge coordinate": [dict(keep, path_map=[[10 ** 400, 0, 400], [10, 0, 400]])]}
        for what, probes in cases.items():
            with self.subTest(what):
                out = f"{self.tmp}/bad-{what.replace(' ', '-')}.mbmap"
                with self.assertRaises(PackageError) as cm:
                    export_baked(out, "bad", self.area, self.sources, baked, self.generated, MATERIALS, {},
                                 created_utc=UTC, passage_probes=probes)
                self.assertIn("passage_probes", str(cm.exception))
                self.assertFalse(os.path.exists(out))
                with self.assertRaises(PackageError):
                    self.export_map_with_meta(baked, out, {"passage_probes": probes})
                self.assertFalse(os.path.exists(out))
        # a missing key still means "no probes"
        manifest, result, report, _ = self.export_map_with_meta(baked, f"{self.tmp}/nokey.mbmap", {})
        self.assertTrue(result.ok, result.summary())
        self.assertEqual((manifest["passage_probes"], report["passage_probes_dropped"]), ([], []))

    def export_map_with_meta(self, baked, out, extra):
        """Run blender/export.py export_map with a stub ``bpy`` and the scene collection replaced by ``baked``."""
        import sys
        from unittest import mock
        f = self.area.frame
        meta = dict({"area": {"lat": f.lat0, "lon": f.lon0, "width_m": self.area.width, "height_m": self.area.height},
                     "z_offset_m": f.z_offset, "generated_ids": self.generated, "sources": self.sources}, **extra)

        class Root(dict):
            name = "Map"

        root = Root(mb_map=json.dumps(meta))
        before = set(sys.modules)
        bpy = mock.MagicMock()
        bpy.path.abspath = lambda p: p
        bpy.app.version_string = "4.2.23 LTS"
        try:
            with mock.patch.dict(sys.modules, {"bpy": bpy}):
                from map_builder.blender import export as ex
                with mock.patch.object(ex, "collect", return_value=(baked, MATERIALS, {"warnings": []})):
                    return ex.export_map(mock.MagicMock(), out, "m", root=root)
        finally:
            for k in set(sys.modules) - before:        # never leave bpy-bound modules behind for other tests
                del sys.modules[k]

    def test_failed_export_keeps_previous_package(self):
        baked, *_ = self.edited_scene()
        path = f"{self.tmp}/keep.mbmap"
        export_baked(path, "keep", self.area, self.sources, baked, self.generated, MATERIALS, {}, created_utc=UTC)
        with open(path, "rb") as f:
            before = hashlib.sha256(f.read()).hexdigest()
        holed = next(x for x in baked if x.mb_class == "building")
        holed.triangles = holed.triangles[1:]          # open shell: strict validation must refuse
        holed.tri_materials, holed.tri_colors = holed.tri_materials[1:], holed.tri_colors[1:]
        with self.assertRaises(PackageError):
            export_baked(path, "keep", self.area, self.sources, baked, self.generated, MATERIALS, {},
                         created_utc=UTC)
        with open(path, "rb") as f:
            self.assertEqual(hashlib.sha256(f.read()).hexdigest(), before)
        with self.assertRaises(ExportError):
            package_parts([], self.generated, MATERIALS)


class ExportPolicyTest(unittest.TestCase):
    def test_linked_and_local_objects_sharing_a_name_block_export(self):
        from map_builder.blender.bake import export_name_clashes
        self.assertEqual(export_name_clashes([("a", "a"), ("b", "b [lib.blend]")]), [])
        errs = export_name_clashes([("Box", "Box"), ("Box", "Box [lib.blend]"), ("c", "c")])
        self.assertEqual(len(errs), 1)
        self.assertIn("'Box'", errs[0])
        self.assertIn("'Box [lib.blend]'", errs[0])
        self.assertIn("unique", errs[0])

    def test_principled_omissions_name_each_unsupported_effect(self):
        from map_builder.blender.bake import principled_omissions
        default = {"Base Color": (False, (0.8, 0.8, 0.8, 1.0)), "Roughness": (False, 0.5),
                   "Metallic": (False, 0.0), "Alpha": (False, 1.0), "Normal": (False, (0.0, 0.0, 0.0)),
                   "Emission Color": (False, (1.0, 1.0, 1.0, 1.0)), "Emission Strength": (False, 0.0),
                   "Subsurface Weight": (False, 0.0), "Transmission Weight": (False, 0.0),
                   "Coat Weight": (False, 0.0), "Sheen Weight": (False, 0.0), "Anisotropic": (False, 0.0),
                   "Thin Film Thickness": (False, 0.0), "Specular IOR Level": (False, 0.5), "IOR": (False, 1.5)}
        self.assertEqual(principled_omissions(default), [])
        # supported inputs (linked Base Color, Roughness, Metallic, Alpha) are handled elsewhere
        self.assertEqual(principled_omissions(dict(default, **{"Base Color": (True, (1, 1, 1, 1)),
                                                               "Roughness": (True, 0.5)})), [])
        # black emission colour or zero strength: no visible emission
        self.assertEqual(principled_omissions(dict(default, **{"Emission Color": (False, (0.0, 0.0, 0.0, 1.0)),
                                                               "Emission Strength": (False, 5.0)})), [])
        rich = dict(default, **{"Emission Strength": (False, 2.0), "Normal": (True, (0.0, 0.0, 0.0)),
                                "Transmission Weight": (False, 0.3), "Coat Weight": (False, 0.5),
                                "Sheen Weight": (True, 0.0), "Subsurface Weight": (False, 0.1),
                                "Anisotropic": (False, 0.2), "Specular IOR Level": (True, 0.5)})
        self.assertEqual(principled_omissions(rich),
                         ["emission", "subsurface scattering", "transmission", "coat", "sheen",
                          "anisotropic specular", "normal/bump map (Normal input)",
                          "Specular IOR Level driven by nodes"])
        self.assertEqual(principled_omissions(dict(default, **{"Emission Color": (True, (0, 0, 0, 1))})),
                         ["emission"])


class SourcesTest(unittest.TestCase):
    def test_redact_diagnostics_withholds_credential_like_names(self):
        out = redact_diagnostics(["'curve token=FAKE_REVIEW_ONLY': CURVE objects cannot be exported",
                                  "'bld_1': zero scale", "collection 'token=FAKE_REVIEW_ONLY' is disabled",
                                  "excluded (token=FAKE_REVIEW_ONLY)", 'in "token=FAKE_REVIEW_ONLY"'])
        for redacted in (out[0], *out[2:]):
            self.assertNotIn("FAKE_REVIEW_ONLY", redacted)
            self.assertIn("withheld", redacted)
        self.assertEqual(out[1], "'bld_1': zero scale")

    BASE = {"elevation_source": "file", "elevation_file": "/x/dem.asc", "elevation_crs": "EPSG:4326",
            "elevation_vertical_datum": "", "elevation_license": "CC-BY 4.0", "terrain_spacing": 10.0,
            "osm_source": "file", "osm_file": "/x/a.osm", "overpass_endpoint": "default", "cache_dir": ""}
    DUMMY = "DUMMY-TOKEN-0000"
    LEAKS = (f"see https://user:{DUMMY}@licence.invalid/terms", f"https://licence.invalid/terms?token={DUMMY}",
             f"Authorization: Bearer {DUMMY}xyz")

    def test_credentials_in_user_fields_are_rejected_without_echo(self):
        fields = ("elevation_license", "elevation_file", "elevation_crs", "elevation_vertical_datum", "osm_file",
                  "cache_dir", "package_name")
        for key in fields:
            for leak in self.LEAKS:
                with self.subTest(field=key, leak=leak):
                    with self.assertRaises(SettingsInputError) as cm:
                        settings_kwargs(dict(self.BASE, **{key: leak}), {})
                    msg = str(cm.exception)
                    self.assertNotIn(self.DUMMY, msg)
                    self.assertNotIn("licence.invalid", msg)
                    self.assertIn("credential-like", msg)
        with self.assertRaises(SettingsInputError) as cm:
            settings_kwargs(dict(self.BASE, elevation_license=self.LEAKS[0]), {})
        self.assertIn("Licence", str(cm.exception))
        settings_kwargs(dict(self.BASE, elevation_license="CC-BY 4.0, https://licence.invalid/terms"), {})

    def test_persisted_scene_data_is_checked_before_writing(self):
        from map_builder.blender.sources import check_persistable, reject_credentials
        clean = {"collection_metadata": {"sources": [{"license": {"name": "CC-BY"}, "attribution": "A"}]}}
        check_persistable(clean)
        leaky = {"collection_metadata": {"sources": [{"license": {"name": "CC-BY"},
                                                       "attribution": f"x?api_key={self.DUMMY}"}]}}
        with self.assertRaises(SettingsInputError) as cm:
            check_persistable(leaky)
        msg = str(cm.exception)
        self.assertIn("collection_metadata.sources[0].attribution", msg)
        self.assertNotIn(self.DUMMY, msg)
        with self.assertRaises(SettingsInputError) as cm:
            reject_credentials({"export_path": f"/x/a.mbmap?sig={self.DUMMY}"}, "Nothing was exported")
        self.assertIn("Package", str(cm.exception))
        self.assertNotIn(self.DUMMY, str(cm.exception))

    def test_local_files(self):
        kw = settings_kwargs(dict(self.BASE), {})
        Settings(**kw)
        self.assertEqual(kw["elevation_vertical_datum"], "user-declared (unknown)")
        self.assertFalse(needs_network(self.BASE))
        for key, msg in (("elevation_license", "licence"), ("elevation_file", "elevation file"),
                         ("osm_file", "OpenStreetMap")):
            with self.assertRaises(SettingsInputError) as cm:
                settings_kwargs(dict(self.BASE, **{key: ""}), {})
            self.assertIn(msg, str(cm.exception))

    def test_overpass_endpoint_never_from_saved_settings(self):
        v = dict(self.BASE, osm_source="overpass", elevation_source="copernicus")
        self.assertTrue(needs_network(v))
        self.assertEqual(settings_kwargs(v, {ENV_OVERPASS_URL: "https://x.invalid/i"})["overpass_url"],
                         DEFAULT_OVERPASS_URL)
        env = dict(v, overpass_endpoint="env")
        with self.assertRaises(SettingsInputError):
            settings_kwargs(env, {})
        secret_url = "https://u:secret@mirror.invalid/api/secret/interpreter"
        kw = settings_kwargs(env, {ENV_OVERPASS_URL: secret_url})
        self.assertEqual(kw["overpass_url"], secret_url)
        Settings(**kw)
        with self.assertRaises(SettingsInputError) as cm:
            settings_kwargs(env, {ENV_OVERPASS_URL: "ftp://secret@host/x"})
        self.assertNotIn("secret", str(cm.exception))
        self.assertIsNone(endpoint_problem("http://localhost:8080/api/interpreter"))
        self.assertIsNotNone(endpoint_problem("http://host:99999999/"))

    def test_report_sections(self):
        text = format_report("T", [{"kind": "elevation", "product": "P", "license": {"name": "L"},
                                    "attribution": "A", "resampled_spacing_m": 10.0}],
                             {"unsupported_features": [{"id": "osm:way/1"}], "invalid_features": [],
                              "warnings": ["w1"], "edits": {"removed": ["osm:way/2"], "duplicated": [],
                                                            "user_added": ["u"]}})
        for needle in ("SOURCES, LICENCES AND ATTRIBUTION", "licence: L", "attribution: A", "resampled_spacing_m",
                       "UNSUPPORTED FEATURES (1)", "INVALID FEATURES (0)", "WARNINGS (1)", "removed: osm:way/2",
                       "user-added: u"):
            self.assertIn(needle, text)


if __name__ == "__main__":
    unittest.main()
