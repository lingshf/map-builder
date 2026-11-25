# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""S5-F3 step 2 evidence: the ``--pre-carve`` base of tools/water_check.py, the same inputs built without
water. ``build_water`` gets no water areas, so the emitted terrain mesh is the uncarved (pre-carve) grid.

  py -3.12 precarve.py --root <tree> --cache <dir> --preset <p> --out <pkg>
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import build_factoria


def main(argv: list[str]) -> int:
    args = build_factoria.parse_args(["cli", *argv])
    sys.path.insert(0, str(args.root))
    from map_builder.core import water
    real = water.build_water

    def without_water(grid, z_offset, areas, riverbanks, waterways, *rest, **kw):  # type: ignore[no-untyped-def]
        return real(grid, z_offset, [], [], [], *rest, **kw)
    water.build_water = without_water  # type: ignore[assignment]
    build_factoria.deny_network()
    with tempfile.TemporaryDirectory() as scratch:
        cache = build_factoria.fresh_cache_copy(args.cache, args.preset, Path(scratch))
        ok = build_factoria.build_cli(args.preset, str(cache), args.out)
    print("valid:", ok)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
