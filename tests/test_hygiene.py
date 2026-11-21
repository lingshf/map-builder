# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""The test-run guard in tests/__init__.py: a leaked handle must fail the run."""

import os
import subprocess
import sys
import tempfile
import textwrap
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SCRATCH = textwrap.dedent('''
    import unittest

    class Leak(unittest.TestCase):
        def test_leaks_a_handle(self):
            f = open(__file__)
            del f

    if __name__ == "__main__":
        unittest.main()
''')


class UnraisableGuardTest(unittest.TestCase):
    def run_scratch(self, body):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "tests"))
            for name, text in (("__init__.py", None), ("test_scratch.py", body)):
                with open(os.path.join(d, "tests", name), "w", encoding="utf-8") as f:
                    if text is None:
                        with open(os.path.join(ROOT, "tests", "__init__.py"), encoding="utf-8") as src:
                            f.write(src.read())
                    else:
                        f.write(text)
            return subprocess.run([sys.executable, "-m", "unittest", "tests.test_scratch"], cwd=d,
                                  capture_output=True, text=True)

    def test_a_leaked_handle_fails_the_run(self):
        run = self.run_scratch(SCRATCH)
        self.assertNotEqual(run.returncode, 0, run.stderr)
        self.assertIn("ResourceWarning", run.stderr)

    def test_a_handle_held_by_a_module_global_fails_the_run(self):
        run = self.run_scratch(SCRATCH.replace("f = open(__file__)\n        del f", "global KEPT\n        KEPT = open(__file__)"))
        self.assertNotEqual(run.returncode, 0, run.stderr)
        self.assertIn("ResourceWarning", run.stderr)

    def test_a_clean_run_passes(self):
        run = self.run_scratch(SCRATCH.replace("f = open(__file__)", "with open(__file__) as f:\n            pass"))
        self.assertEqual(run.returncode, 0, run.stderr)


if __name__ == "__main__":
    unittest.main()
