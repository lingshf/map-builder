# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""S5-F3 D153 gate: ``tools.perf.work_count compare`` for every gating preset and series.

``--perf`` holds the work vectors in ``{base,head}{1,2}/<preset>.<series>.json`` and the alternating CPU rounds as
``CPU {json}`` lines in ``cpu_cli.txt`` (``design/bench/cpu_cli.py``) and ``cpu_bl.txt`` (``cpu_bl.py``). Writes
``cpu-<preset>.<series>.json``, ``compare-<preset>.<series>.json`` and ``gate.json`` there.

    py -3.12 perf_gate.py --root ROOT --perf PERF
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

PRESETS = ("munich", "pittsburgh")
CPU_SOURCES = {  # series -> (rounds file, CPU-seconds field)
    "cli_generate": ("cpu_cli.txt", "cpu_total"),
    "blender_generate": ("cpu_bl.txt", "cpu_gen"),
    "blender_generate_export": ("cpu_bl.txt", "cpu_ge"),
}
CPU_LINE_PREFIX = "CPU "
UTF16_BOM = b"\xff\xfe"


def _lines(path: Path) -> list[str]:
    raw = path.read_bytes()
    return raw.decode("utf-16" if raw.startswith(UTF16_BOM) else "utf-8-sig").splitlines()


def cpu_rounds(perf: Path, preset: str, series: str) -> dict[str, list[float]]:
    """The base and head CPU seconds of ``series`` on ``preset``, in round order."""
    file_name, field = CPU_SOURCES[series]
    rounds: dict[str, list[float]] = {"base": [], "head": []}
    for line in _lines(perf / file_name):
        if line.startswith(CPU_LINE_PREFIX):
            record = json.loads(line[len(CPU_LINE_PREFIX):])
            if record["key"] == preset:
                rounds[record["tag"]].append(record[field])
    return rounds


def gate(root: Path, perf: Path, preset: str, series: str) -> dict[str, object]:
    name = f"{preset}.{series}"
    rounds = cpu_rounds(perf, preset, series)
    cpu_file = perf / f"cpu-{name}.json"
    cpu_file.write_text(json.dumps(rounds), encoding="utf-8")
    vector = {f"{tag}{peer}": str(perf / f"{tag}{peer}" / f"{name}.json") for tag in ("base", "head") for peer in (1, 2)}
    run = subprocess.run([sys.executable, "-m", "tools.perf.work_count", "compare",
                          "--base", vector["base1"], "--head", vector["head1"],
                          "--base-peer", vector["base2"], "--head-peer", vector["head2"],
                          "--cpu-rounds", str(cpu_file)], cwd=root, capture_output=True, text=True)
    events = json.loads(run.stdout)["events"]
    (perf / f"compare-{name}.json").write_text(json.dumps({"events": events}, indent=2) + "\n", encoding="utf-8")
    return {"exit": run.returncode, "cpu": rounds, "events": events}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, required=True, help="the map-builder head checkout")
    ap.add_argument("--perf", type=Path, required=True)
    args = ap.parse_args()
    results = {f"{preset}.{series}": gate(args.root, args.perf, preset, series)
               for preset in PRESETS for series in CPU_SOURCES}
    (args.perf / "gate.json").write_text(json.dumps(results, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(results, indent=1))


if __name__ == "__main__":
    main()
