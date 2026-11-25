# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""S5-F3 step 2 evidence: the AC2 audit of every after-build and the sample, and the before -> after member diffs.

``--work`` holds ``builds/{before,after}_<preset>_<path>.mbmap`` (from ``build_all.ps1``); the results go to
``<work>/step2``. ``--sample-blender`` is the sample fixtures built through Blender (the headless run's ``it.mbmap``).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

PRESETS = ("bellevue-factoria", "munich", "pittsburgh")
PATHS = ("cli", "blender")
SHORE_STEP_BOUND_M = 1.501
GATED_KINDS = ("water_above_bank", "water_buried")
DIFF_KEYS = ("archive_identical", "members_changed", "collision_objects", "glb_nodes", "heightfield",
             "pinned_unchanged", "report_water_bodies")


def audit(root: Path, out_dir: Path, name: str, pkg: Path) -> dict:
    out = out_dir / f"{name}.audit.json"
    code = subprocess.run([sys.executable, "tools/floating_audit.py", str(pkg), "--json", str(out)], cwd=root,
                          capture_output=True).returncode
    summary = json.loads(out.read_text())["findings_summary"]
    step = max((v["max_offset_m"] for k, v in summary.items() if k.startswith("water_shore_step")), default=0.0)
    gated = {k: v["regions"] for k, v in summary.items() if k.split(":")[0] in GATED_KINDS}
    return {"exit": code, "water_above_bank+water_buried": gated, "shore_step_max_m": step,
            "shore_step_ok": step <= SHORE_STEP_BOUND_M, "kinds": {k: v["regions"] for k, v in summary.items()}}


def member_diff(root: Path, builds: Path, out_dir: Path, name: str) -> dict:
    out = out_dir / f"{name}.diff.json"
    subprocess.run([sys.executable, "design/evidence/S5-F3/scripts/member_diff.py",
                    str(builds / f"before_{name}.mbmap"), str(builds / f"after_{name}.mbmap"),
                    "--json", str(out)], cwd=root, capture_output=True, check=True)
    return json.loads(out.read_text())


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, required=True, help="the map-builder head checkout")
    ap.add_argument("--work", type=Path, required=True)
    ap.add_argument("--sample-blender", type=Path, required=True)
    args = ap.parse_args()
    builds, out_dir = args.work / "builds", args.work / "step2"
    out_dir.mkdir(exist_ok=True)
    audits, diffs = {}, {}
    for preset in PRESETS:
        for path in PATHS:
            name = f"{preset}_{path}"
            audits[name] = audit(args.root, out_dir, name, builds / f"after_{name}.mbmap")
            d = member_diff(args.root, builds, out_dir, name)
            diffs[name] = {k: d[k] for k in DIFF_KEYS}
    samples = {"sample_cli": args.root / "examples" / "synthetic_sample.mbmap", "sample_blender": args.sample_blender}
    for name, pkg in samples.items():
        audits[name] = audit(args.root, out_dir, name, pkg)
    (out_dir / "ac2.json").write_text(json.dumps(audits, indent=2) + "\n")
    (out_dir / "diffs.json").write_text(json.dumps(diffs, indent=2) + "\n")
    print(json.dumps(audits, indent=1))
    print(json.dumps(diffs, indent=1))


if __name__ == "__main__":
    main()
