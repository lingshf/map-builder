# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf

from __future__ import annotations

import os
import sys
import unittest
import urllib.parse

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools", "demo"))

import style_frame_time_proxy as proxy  # noqa: E402


class StyleFrameTimeProxyTests(unittest.TestCase):
    def test_enu_to_gltf_conversion(self) -> None:
        self.assertEqual(proxy._enu_to_gltf([1.0, 2.0, 3.0]), [1.0, 3.0, -2.0])

    def test_result_match_requires_run_and_glb_identity(self) -> None:
        data = {
            "run_id": "r1",
            "glb_sha256": "abc",
            "warmup_frames": 60,
            "measured_frames": 300,
            "median_ms": 12.5,
            "median_render_ms": 11.0,
            "passes": 1,
            "renderer": "SwiftShader",
        }
        self.assertTrue(proxy._matches_expected_result(data, "r1", "abc", 60, 300, 1))
        self.assertFalse(proxy._matches_expected_result(data, "r2", "abc", 60, 300, 1))
        self.assertFalse(proxy._matches_expected_result(data, "r1", "def", 60, 300, 1))
        self.assertFalse(proxy._matches_expected_result(data, "r1", "abc", 59, 300, 1))
        self.assertFalse(proxy._matches_expected_result(data, "r1", "abc", 60, 301, 1))
        self.assertFalse(proxy._matches_expected_result(data, "r1", "abc", 60, 300, 2))
        self.assertFalse(proxy._matches_expected_result({**data, "median_render_ms": None}, "r1", "abc", 60, 300, 1))

    def test_make_url_carries_passes_and_does_not_echo_glb_sha256(self) -> None:
        camera = {"name": "overview", "eye": [1.0, 2.0, 3.0], "target": [4.0, 5.0, 6.0], "lens_mm": 30}
        url = proxy._make_url("127.0.0.1", 8781, camera, "run-1", 60, 300, 2)
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        self.assertNotIn("glb_sha256", qs)
        self.assertEqual(qs.get("run_id"), ["run-1"])
        self.assertEqual(qs.get("passes"), ["2"])
        default = urllib.parse.parse_qs(urllib.parse.urlparse(proxy._make_url("h", 1, camera, "r", 60, 300)).query)
        self.assertEqual(default.get("passes"), ["1"])

    def test_render_ratio_is_head_median_over_base_median(self) -> None:
        self.assertAlmostEqual(proxy.render_ratio([10.0, 12.0, 11.0], [22.0, 21.0, 23.0]), 2.0)

    def test_controls_and_d139_verdicts_from_canned_runs(self) -> None:
        canned = {
            "C1 pass": (1.02, 1, True, "C1", True),
            "C1 fail": (1.05, 1, True, "C1", False),
            "C2 pass": (1.90, 2, True, "C2", True),
            "C2 fail: slowdown not seen": (1.05, 2, True, "C2", False),
            "D139 pass": (1.04, 1, False, "D139", True),
            "D139 fail": (1.12, 1, False, "D139", False),
        }
        for name, (ratio, passes, same, rule, passed) in canned.items():
            with self.subTest(name):
                verdict = proxy.control_verdict(ratio, passes, same)
                self.assertEqual((verdict["rule"], verdict["passed"]), (rule, passed))

    def test_head_passes_above_one_needs_the_same_package(self) -> None:
        with self.assertRaises(SystemExit):
            proxy.control_verdict(1.0, 2, False)

    def test_renderer_validation(self) -> None:
        proxy._ensure_swiftshader_renderer("ANGLE (SwiftShader driver)", "r-ok")
        with self.assertRaises(SystemExit):
            proxy._ensure_swiftshader_renderer("ANGLE (NVIDIA)", "r-bad")


if __name__ == "__main__":
    unittest.main()
