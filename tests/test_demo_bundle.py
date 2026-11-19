"""Pure-Python parts of the demo kit (tools/demo). No Blender, no network, no renders."""

import json
import os
import shutil
import sys
import tempfile
import unittest
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools", "demo"))

import demo_bundle as db  # noqa: E402
import run_demo  # noqa: E402

SAMPLE = os.path.join(REPO, "examples", "synthetic_sample.mbmap")


class StalePanelTests(unittest.TestCase):
    def test_failed_panel_step_leaves_no_old_image(self):
        for extra in ([], ["--panel", "--mesa-blender", os.path.join(REPO, "no-such", "blender.exe")]):
            with tempfile.TemporaryDirectory() as out:
                png = os.path.join(out, "panel.png")
                with open(png, "wb") as f:
                    f.write(b"old")
                run_demo.main(["--preset", "synthetic", "--after", SAMPLE, "--out", out, "--bundle-only"] + extra)
                self.assertFalse(os.path.exists(png))
                with open(os.path.join(out, "summary.md"), encoding="utf-8") as f:
                    self.assertIn("not produced", f.read())


def good_preset():
    return {"name": "x", "area": {"lat": 1, "lon": 2, "width_m": 100, "height_m": 100},
            "cameras": [{"name": "overview", "eye": [0, -50, 30], "target": [0, 0, 0]}]}


class PresetTests(unittest.TestCase):
    def test_committed_presets_load(self):
        for n in ("synthetic", "sf-fidi", "pittsburgh"):
            p = db.load_preset(n)
            self.assertEqual(p["name"], n)
            self.assertIn("overview", [c["name"] for c in p["cameras"]])

    def test_pittsburgh_preset_matches_the_v0_1_0_cameras(self):
        saved = json.load(open(os.path.join(REPO, "docs", "demo", "v0.1.0", "pittsburgh-cameras.json")))
        self.assertEqual(db.load_preset("pittsburgh"), saved)

    def test_rejects_bad_presets(self):
        bad = []
        p = good_preset(); p["cameras"][0]["eye"] = [0, 0]; bad.append(p)
        p = good_preset(); p["cameras"][0]["eye"] = [0, 0, float("nan")]; bad.append(p)
        p = good_preset(); p["cameras"] = p["cameras"] * 2; bad.append(p)
        p = good_preset(); p["cameras"] = [dict(p["cameras"][0], name="c%d" % i) for i in range(7)]; bad.append(p)
        p = good_preset(); p["name"] = "../x"; bad.append(p)
        p = good_preset(); p["area"]["lat"] = 99; bad.append(p)
        for p in bad:
            with self.assertRaises(db.DemoError):
                db.validate_preset(p)

    def test_render_names_are_deterministic(self):
        p = good_preset()
        self.assertEqual(db.render_names(p, False), ["render-overview-after.png"])
        self.assertEqual(db.render_names(p, True), ["render-overview-after.png", "render-overview-before.png"])


class BundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pkg = db.read_package(SAMPLE, verify=False)  # verification is covered by the tamper test and real runs

    def test_viewer_bundle(self):
        out = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, out, True)
        z = db.write_viewer(out, self.pkg, db.probe_results(self.pkg))
        for f in db.VIEWER_FILES:
            self.assertTrue(os.path.isfile(os.path.join(out, "viewer", f)), f)
        names = db.zip_listing(z)
        self.assertEqual(names, sorted(names))
        for f in db.VIEWER_FILES:
            self.assertIn("viewer/" + f, names)
        self.assertIn("viewer/vendor/LICENSE-three.txt", names)
        with open(os.path.join(out, "viewer", "NOTICES.txt"), encoding="utf-8") as f:
            self.assertIn("notices", f.read().lower())
        with open(os.path.join(out, "viewer", "probes.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f)["package_id"], self.pkg["package_id"])

    def test_probe_results_and_summary(self):
        pkg = dict(self.pkg)
        m = json.loads(json.dumps(pkg["manifest"]))
        feat = m["objects"][0]["mb_id"]
        # a capsule far above everything passes; one through the terrain is blocked
        m["passage_probes"] = [
            {"id": "high", "kind": "bridge", "feature": feat, "path_map": [[0, 0, 500], [1, 0, 500]], "radius_m": 1},
            {"id": "ground", "kind": "tunnel", "feature": feat, "path_map": [[-100, -100, 8], [-90, -100, 8]],
             "radius_m": 50}]
        pkg["manifest"] = m
        res = {p["id"]: p for p in db.probe_results(pkg)}
        self.assertEqual(res["high"]["result"], "PASS")
        self.assertEqual(res["ground"]["result"], "BLOCKED")
        self.assertEqual(res["high"]["path_gltf"][0], [0, 500, 0])
        md = db.summary_md(db.load_preset("synthetic"), pkg, list(res.values()), ["render-overview-after.png"], "note")
        self.assertIn("| high | bridge |", md)
        self.assertIn("BLOCKED", md)
        self.assertIn("render-overview-after.png", md)

    def test_tampered_member_is_rejected(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        bad = os.path.join(d, "bad.mbmap")
        with zipfile.ZipFile(SAMPLE) as zin, zipfile.ZipFile(bad, "w", zipfile.ZIP_DEFLATED) as zout:
            for zi in zin.infolist():
                data = zin.read(zi.filename)
                if zi.filename == "visual/map.glb":
                    data = data[:-1] + bytes([data[-1] ^ 1])
                zout.writestr(zi.filename, data)
        with self.assertRaises(db.DemoError):
            db.read_package(bad)

    def test_probe_budget_is_shared(self):
        pkg = dict(self.pkg)
        m = json.loads(json.dumps(pkg["manifest"]))
        feat = m["objects"][0]["mb_id"]
        m["passage_probes"] = [{"id": "p%d" % i, "kind": "bridge", "feature": feat,
                                "path_map": [[0, 0, 500], [1, 0, 500]], "radius_m": 1} for i in range(3)]
        pkg["manifest"] = m
        saved = db.PASSAGE_QUERY_BUDGET
        db.PASSAGE_QUERY_BUDGET = 100
        self.addCleanup(setattr, db, "PASSAGE_QUERY_BUDGET", saved)
        res = [p["result"] for p in db.probe_results(pkg)]
        self.assertEqual(res[0], "PASS")
        self.assertIn("UNCHECKED", res)
        self.assertNotIn("BLOCKED", res)

    def test_vendor_files_present(self):
        for rel in ("three.module.min.js", "jsm/loaders/GLTFLoader.js", "jsm/controls/OrbitControls.js"):
            self.assertTrue(os.path.isfile(os.path.join(db.VIEWER_SRC, "vendor", *rel.split("/"))), rel)
        self.assertTrue(zipfile.is_zipfile(SAMPLE))


if __name__ == "__main__":
    unittest.main()
