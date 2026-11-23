# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""The committed sample must have no floating or buried collision (tools/floating_audit.py)."""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLE = os.path.join(ROOT, "examples", "synthetic_sample.mbmap")
HAS_NUMPY = importlib.util.find_spec("numpy") is not None   # the audit tool needs it; the core does not


@unittest.skipUnless(HAS_NUMPY, "numpy is not installed (the audit tool is a developer tool)")
class SampleAuditTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        try:
            import floating_audit
        finally:
            sys.path.pop(0)
        cls.result = floating_audit.audit(SAMPLE)

    def test_no_collision_floats_above_or_is_buried_below_the_visible_surface(self):
        self.assertTrue(self.result["ok"], self.result["findings_summary"])

    def test_roads_do_not_hover_over_the_carved_terrain(self):
        self.assertNotIn("ground_above_terrain:road", self.result["findings_summary"])

    def test_findings_are_json_serialisable_without_infinities(self):
        json.dumps(self.result, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
