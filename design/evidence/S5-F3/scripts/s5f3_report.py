"""S5-F3 step-1 report (session files): classify the regions of ``evidence.json`` and write the PR evidence.

  py -3.12 s5f3_report.py --evidence <dir>/evidence.json --blocked <blocked_strips.json> --out <dir>

Writes ``summary.md`` (per-region table and the class-D detail), ``cells.csv`` (four Z values per cell, both
surfaces), ``rays.csv`` (Python and C# grid rays) and ``plan-i90.svg`` (plan view of the blocked strips).
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

SHORE_STEP_BOUND_M = 1.501
HF_KIND = "hf_below_ground:water"
SVG_SCALE = 6.0              # pixels per metre in the plan diagram
SVG_PAD_M = 8.0
SVG_LEGEND_W = 300.0         # pixels reserved right of the plan for the region legend
SVG_LINE_PX = 16             # legend line height
SVG_TAG_OFFSET_M = 3.0       # region tags sit this far west of the worst cell


# --- classification ---------------------------------------------------------------------------------------------

def classify(region: dict[str, Any]) -> tuple[str, str]:
    """(class, reason) for one region on its own surface, by the S5-F3 class rules."""
    category = region["category"]
    if category == HF_KIND:
        if region["nodes_hf_equals_collision_bed"] == region["nodes"]:
            return "E", "D117: every node of .mbhf equals the collision bed under the sheet"
        return "D?", "heightfield differs from the collision bed at some nodes"
    if category.startswith("water_above_bank"):
        return "D", "sheet edge above the outside terrain by more than the 1.5 m carve step; " + _ramp_reason(region)
    if region["over_shore_step_bound"]:
        return "D", f"shore step {region['max_offset_m']:.3f} m above the {SHORE_STEP_BOUND_M} m bound; " \
                    + _ramp_reason(region)
    return "E", f"designed shore step on the audit ring, max {region['max_offset_m']:.3f} m <= {SHORE_STEP_BOUND_M} m"


def _ramp_reason(region: dict[str, Any]) -> str:
    masks = _blocking_objects(region)
    if region["bank_ramp_cells"]:
        return f"{region['bank_ramp_cells']} cells on a bank: ramp; ramp missing at the rest ({masks or 'no blocked strip'})"
    if masks:
        return f"bank ramp skipped (shore_ramp_blocked_m): strip meets the line mask of {masks}"
    return "no bank ramp and no blocked strip recorded"


def _blocking_objects(region: dict[str, Any]) -> str:
    objects = sorted({o for strip in region.get("blocked_strips", []) for reason in strip["reasons"]
                      for o in reason.get("objects", [])})
    wet = any(reason["mask"] == "wet" for strip in region.get("blocked_strips", []) for reason in strip["reasons"])
    return ", ".join(objects + (["wet overlap"] if wet else []))


# --- markdown ---------------------------------------------------------------------------------------------------

def region_table(regions: list[dict[str, Any]]) -> list[str]:
    lines = ["| Region | Cells | bbox (m) | Centre | Max offset (m) | Bodies | Outside owners | Ring steps | "
             "Grid top objects | Py/C# disagree | Class | Reason |", "|" + "---|" * 12]
    for r in regions:
        cls, reason = r["class"]
        lines.append(f"| `{r['id']}` | {r['cell_count']} | {_fmt(r['bbox'])} | {_fmt(r['centre'])} | "
                     f"{r['max_offset_m']:.3f} | {', '.join(r['bodies'])} | {', '.join(r.get('outside_owners', ['-']))} | "
                     f"{_fmt(r.get('ring_steps', ['-']))} | {'; '.join(r['grid_top_objects'])} | "
                     f"{r['python_csharp_disagreements']} | **{cls}** | {reason} |")
    return lines


def d_detail(r: dict[str, Any]) -> list[str]:
    side = r["category"].rsplit(":", 1)[1]
    lines = [f"#### `{r['id']}` (class D)", "", f"Blocked strips within reach "
             f"(`shore_ramp_blocked_m` of the body: {r['shore_ramp_blocked_m']}):", ""]
    for s in r["blocked_strips"]:
        lines.append(f"* {s['kind']} strip {_fmt(s['a'])} -> {_fmt(s['b'])} ({s['length_m']} m): "
                     + "; ".join(f"{x['mask']} {x.get('half_width_m', '')} {', '.join(x.get('objects', []))}"
                                 for x in s["reasons"]))
    lines += ["", "| Cell XY | Collision top (z, mb_id, class) | Visual top (z, owner, category) | "
                  f"Sheet z ({side}) | Outside z ({side}) | Outside owner | Offset (m) |", "|" + "---|" * 7]
    for c in r["cells"]:
        top, vis, me = c["collision_top"], c["visual_top"], c[side]
        lines.append(f"| {_fmt(c['xy'])} | {top['z']}, {top['mb_id']}, {top['class']} | "
                     f"{vis['z']}, {vis['owner']}, {vis['category']} | {me['sheet_z']} | {me['outside_z']} | "
                     f"{me['outside_owner']} | {me['offset_m']} |")
    return lines + [""]


def _fmt(v: Any) -> str:
    return "(" + ", ".join(str(x) for x in v) + ")" if isinstance(v, list) else str(v)


def summary(evidence: dict[str, Any]) -> str:
    regions = evidence["regions"]
    counts: dict[str, int] = {}
    for r in regions:
        key = f"{r['category']} {r['class'][0]}"
        counts[key] = counts.get(key, 0) + 1
    disagreements = sum(r["python_csharp_disagreements"] for r in regions)
    rays = sum(len(r["grid_rays"]) + r["cell_count"] for r in regions)
    head = [f"# S5-F3 step 1: per-region evidence ({evidence['package']})", "",
            f"Python and C# readers: {rays} rays (every cell, plus the 121-ray centre grid per region), "
            f"**{disagreements} disagreements**.", "", "| Category and class | Regions |", "|---|---|"]
    head += [f"| {k} | {v} |" for k, v in sorted(counts.items())]
    detail = [line for r in regions if r["class"][0] == "D" for line in d_detail(r)]
    return "\n".join(head + ["", "## Every region", ""] + region_table(regions) + ["", "## Class D detail", ""]
                     + detail) + "\n"


# --- csv --------------------------------------------------------------------------------------------------------

def write_cells(regions: list[dict[str, Any]], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["region", "x", "y", "col_top_z", "col_top_mb_id", "col_top_class", "vis_top_z", "vis_top_owner",
                    "vis_top_category", "col_sheet_z", "col_sheet_owner", "col_outside_z", "col_outside_owner",
                    "col_offset_m", "vis_sheet_z", "vis_sheet_owner", "vis_outside_z", "vis_outside_owner",
                    "vis_offset_m", "hf_z", "hf_is_bed"])
        for r in regions:
            for c in r["cells"]:
                w.writerow([r["id"], *c["xy"], *_hit(c["collision_top"]), *_cell_surfaces(c)])


def _cell_surfaces(c: dict[str, Any]) -> list[Any]:
    if "hf_z" in c:
        return ["", "", "", "", "", c["col_water_z"], c["water_owner"], c["col_terrain_z"], "", c["offset_m"],
                c["vis_water_z"], "", c["vis_terrain_z"], "", "", c["hf_z"], c["hf_is_bed"]]
    vis = c["visual_top"]
    return [vis["z"], vis["owner"], vis["category"],
            *(c[side][k] for side in ("col", "vis")
              for k in ("sheet_z", "sheet_owner", "outside_z", "outside_owner", "offset_m")), "", ""]


def _hit(h: dict[str, Any] | None) -> list[Any]:
    return [h["z"], h["mb_id"], h["class"]] if h else ["", "miss", ""]


def write_rays(regions: list[dict[str, Any]], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["region", "x", "y", "py_z", "py_mb_id", "py_class", "cs_z", "cs_mb_id", "cs_class", "disagreement"])
        for r in regions:
            for h in r["grid_rays"]:
                w.writerow([r["id"], *h["xy"], *_hit(h["python"]), *_hit(h["csharp"]), h["disagreement"]])


# --- plan diagram -----------------------------------------------------------------------------------------------

def _d_cells(r: dict[str, Any]) -> list[dict[str, Any]]:
    """The cells that make a region class D: all of an above-bank region, the over-bound cells of a shore step."""
    if "above_bank" in r["category"]:
        return r["cells"]
    side = r["category"].rsplit(":", 1)[1]
    return [c for c in r["cells"] if (c[side]["offset_m"] or 0.0) > SHORE_STEP_BOUND_M]


def _free_tag_spot(spot: tuple[float, float], used: list[tuple[float, float]]) -> tuple[float, float]:
    """Move a tag down a line at a time until it clears every tag already placed."""
    x, y = spot
    while any(abs(x - ux) < SVG_LINE_PX and abs(y - uy) < SVG_LINE_PX for ux, uy in used):
        y += SVG_LINE_PX
    return x, y


def plan_svg(regions: list[dict[str, Any]], strips: list[dict[str, Any]]) -> str:
    """Plan view of the class-D cells with the bank strips skipped around them."""
    d_regions = [r for r in regions if r["class"][0] == "D" and r["category"].endswith(":col")]
    cells = [c["xy"] for r in d_regions for c in _d_cells(r)]
    x0, y0 = min(p[0] for p in cells) - SVG_PAD_M, min(p[1] for p in cells) - SVG_PAD_M
    x1, y1 = max(p[0] for p in cells) + SVG_PAD_M, max(p[1] for p in cells) + SVG_PAD_M

    def px(x: float, y: float) -> tuple[float, float]:
        return round((x - x0) * SVG_SCALE, 1), round((y1 - y) * SVG_SCALE, 1)

    w, h = px(x1, y0)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w + SVG_LEGEND_W}" height="{h + 40}" '
           f'font-family="sans-serif" font-size="11"><rect width="100%" height="100%" fill="white"/>']
    for s in strips:
        if x0 <= s["a"][0] <= x1 and y0 <= s["a"][1] <= y1:
            (ax, ay), (bx, by) = px(*s["a"][:2]), px(*s["b"][:2])
            out.append(f'<line x1="{ax}" y1="{ay}" x2="{bx}" y2="{by}" stroke="orange" stroke-width="4"/>')
    used_tags: list[tuple[float, float]] = []
    for tag, r in enumerate(d_regions, start=1):
        colour = "red" if "above_bank" in r["category"] else "purple"
        for c in _d_cells(r):
            cx, cy = px(c["xy"][0] - 0.5, c["xy"][1] + 0.5)
            out.append(f'<rect x="{cx}" y="{cy}" width="{SVG_SCALE}" height="{SVG_SCALE}" fill="{colour}"/>')
        xy = max(_d_cells(r), key=lambda c: c["col"]["offset_m"] or 0.0)["xy"]
        lx, ly = _free_tag_spot(px(xy[0] - SVG_TAG_OFFSET_M, xy[1]), used_tags)
        used_tags.append((lx, ly))
        out.append(f'<text x="{lx}" y="{ly}" font-weight="bold" fill="{colour}">{tag}</text>')
        out.append(f'<text x="{w + 8}" y="{SVG_LINE_PX * tag}" fill="{colour}">{tag}: {r["id"]} '
                   f'max {r["max_offset_m"]:.3f} m</text>')
    out.append(f'<text x="4" y="{h + 16}">red: water_above_bank cells; purple: shore-step cells over 1.501 m; '
               'orange: bank strips skipped by a mask (blocked_strips.json); north up, 1 m cells</text>')
    out.append(f'<text x="4" y="{h + 32}">x {x0:.0f}..{x1:.0f} m, y {y0:.0f}..{y1:.0f} m (map frame)</text></svg>')
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence", type=Path, required=True)
    ap.add_argument("--blocked", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    evidence = json.loads(a.evidence.read_text())
    for r in evidence["regions"]:
        r["class"] = classify(r)
    (a.out / "summary.md").write_text(summary(evidence), "utf-8")
    write_cells(evidence["regions"], a.out / "cells.csv")
    write_rays(evidence["regions"], a.out / "rays.csv")
    (a.out / "plan-i90.svg").write_text(plan_svg(evidence["regions"], json.loads(a.blocked.read_text())), "utf-8")
    (a.out / "classes.json").write_text(json.dumps({r["id"]: r["class"] for r in evidence["regions"]}, indent=1),
                                        "utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
