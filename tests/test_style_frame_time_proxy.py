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
            "renderer": "SwiftShader",
        }
        self.assertTrue(proxy._matches_expected_result(data, "r1", "abc", 60, 300))
        self.assertFalse(proxy._matches_expected_result(data, "r2", "abc", 60, 300))
        self.assertFalse(proxy._matches_expected_result(data, "r1", "def", 60, 300))
        self.assertFalse(proxy._matches_expected_result(data, "r1", "abc", 59, 300))
        self.assertFalse(proxy._matches_expected_result(data, "r1", "abc", 60, 301))

    def test_make_url_does_not_echo_glb_sha256(self) -> None:
        camera = {"name": "overview", "eye": [1.0, 2.0, 3.0], "target": [4.0, 5.0, 6.0], "lens_mm": 30}
        url = proxy._make_url("127.0.0.1", 8781, camera, "run-1", 60, 300)
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        self.assertNotIn("glb_sha256", qs)
        self.assertEqual(qs.get("run_id"), ["run-1"])

    def test_renderer_validation(self) -> None:
        proxy._ensure_swiftshader_renderer("ANGLE (SwiftShader driver)", "r-ok")
        with self.assertRaises(SystemExit):
            proxy._ensure_swiftshader_renderer("ANGLE (NVIDIA)", "r-bad")


if __name__ == "__main__":
    unittest.main()
