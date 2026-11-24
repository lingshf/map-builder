# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf

from __future__ import annotations

import os
import sys
import unittest

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


if __name__ == "__main__":
    unittest.main()
