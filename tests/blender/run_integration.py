"""Runner of the headless Blender integration test (Blender 4.2 LTS).

    blender --background --factory-startup --python tests/blender/run_integration.py -- <out_dir>

Runs ``checks_core.run(out_dir)`` (the core checks, see its docstring) and then every other
``checks_*.py`` module next to this file that defines ``run(out_dir)``, in name order, so a feature adds its
own file. All modules report through ``checks_core.check``. Exit code 0 = pass; non-zero with a FAIL list
otherwise.

The file names deliberately do not match unittest's ``test*.py`` pattern (and tests/blender has no
__init__.py), so ``python -m unittest discover -s tests`` never imports bpy.
"""

import glob
import importlib
import os
import sys
import tempfile
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import checks_core  # noqa: E402


def feature_modules():
    names = sorted(os.path.splitext(os.path.basename(p))[0] for p in glob.glob(os.path.join(HERE, "checks_*.py")))
    return [n for n in names if n != "checks_core"]


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = os.path.abspath(argv[0]) if argv else tempfile.mkdtemp(prefix="mb_it_")
    os.makedirs(out, exist_ok=True)
    try:
        checks_core.run(out)
        for name in feature_modules():
            importlib.import_module(name).run(out)
    except Exception:
        traceback.print_exc()
        checks_core.FAILURES.append("exception")
    print(f"\n{'FAILED' if checks_core.FAILURES else 'OK'}: {len(checks_core.FAILURES)} failure(s); output in {out}")
    for f in checks_core.FAILURES:
        print("  FAIL", f)
    sys.stdout.flush()
    sys.exit(1 if checks_core.FAILURES else 0)
