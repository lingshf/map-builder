"""DSM terrain correction (pure Python, no bpy).

Copernicus GLO-30 is a digital *surface* model: buildings, tree canopy and bridge decks are part of
the elevation. This module pushes the terrain under those features back toward the surrounding ground:

1. :class:`MaskRaster` marks the grid points inside building footprints (buffered), tree crowns,
   forest/wood landcover and bridge deck ribbons (buffered).
2. :func:`fill_masked` fills the masked points from the unmasked ones with an ordered breadth-first
   fill (each newly reached point = mean of its already-known 8-neighbours), then runs smoothing passes
   over the masked points only (Jacobi mean of the 8-neighbours).
3. :func:`correct_grid` keeps ``min(original, filled)`` at masked points: terrain is never raised and
   unmasked points are returned bit-for-bit unchanged.

The result is an approximation of the ground, not a bare-earth DTM. It is a derived step: the raw
elevation provenance (provider, tiles, file hashes) is left unchanged and the correction is reported
separately (``report.json`` ``terrain_correction``).

Work is linear in the grid size and in the total length of the mask geometry (rasterised per row),
with no all-pairs loops; grids are bounded by :data:`dem.MAX_GRID_POINTS`.
"""

import math
from collections import deque

from .dem import ElevationGrid
from .errors import NoDataError

BUILDING_BUFFER_M = 15.0      # about half a GLO-30 pixel around each footprint
TREE_RADIUS_M = 6.0           # OSM natural=tree crown radius
BRIDGE_BUFFER_M = 15.0        # added to half the deck width
SMOOTHING_PASSES = 20
MIN_UNMASKED_FRACTION = 0.05
SURFACE_MODEL_PROVIDERS = ("copernicus-glo30-aws",)   # elevation providers that are surface models (DSM)

_EPS = 1e-9   # grid units; points exactly on a mask boundary are masked


def is_surface_model(provenance):
    """True if the elevation provenance names a surface-model (DSM) provider."""
    return (provenance or {}).get("provider") in SURFACE_MODEL_PROVIDERS


def resolve(requested, provenance):
    """(enabled, reason) for the ``dsm_correction`` setting ``requested`` (None = auto, True, False).

    Auto means ON for surface-model sources (Copernicus) and OFF otherwise (a local file is opt-in)."""
    if requested is not None and not isinstance(requested, bool):
        raise ValueError("dsm_correction must be None (auto), True or False")
    dsm = is_surface_model(provenance)
    local = (provenance or {}).get("provider") == "local-file"
    if requested is False:
        return False, "disabled"
    if requested is None and not dsm:
        return False, "local file (opt-in off)" if local else "not a surface-model source (opt-in off)"
    if dsm:
        return True, "dsm source"
    return True, "local file (opt-in on)" if local else "opt-in on"


class MaskRaster:
    """A byte mask over the points of an :class:`ElevationGrid` (index ``j * nx + i``)."""

    def __init__(self, grid):
        self.x0, self.y0, self.s = grid.x0, grid.y0, grid.spacing
        self.nx, self.ny = grid.nx, grid.ny
        self.mask = bytearray(self.nx * self.ny)

    def count(self):
        return sum(self.mask)

    def _row_range(self, ylo, yhi):
        j0 = max(0, math.ceil((ylo - self.y0) / self.s - _EPS))
        j1 = min(self.ny - 1, math.floor((yhi - self.y0) / self.s + _EPS))
        return range(j0, j1 + 1)

    def _mark_row(self, j, xl, xr):
        i0 = max(0, math.ceil((xl - self.x0) / self.s - _EPS))
        i1 = min(self.nx - 1, math.floor((xr - self.x0) / self.s + _EPS))
        if i0 <= i1:
            k = j * self.nx
            self.mask[k + i0:k + i1 + 1] = b"\x01" * (i1 - i0 + 1)

    def add_capsule(self, a, b, r):
        """Mark the points within distance ``r`` of segment a-b (a disc when a == b)."""
        ax, ay = a[0], a[1]
        bx, by = b[0], b[1]
        dx, dy = bx - ax, by - ay
        L = math.hypot(dx, dy)
        ux, uy = (dx / L, dy / L) if L > 0 else (0.0, 0.0)
        for j in self._row_range(min(ay, by) - r, max(ay, by) + r):
            y = self.y0 + j * self.s
            lo, hi = math.inf, -math.inf
            for cx, cy in ((ax, ay), (bx, by)):
                d = y - cy
                if abs(d) <= r:
                    h = math.sqrt(max(0.0, r * r - d * d))
                    lo, hi = min(lo, cx - h), max(hi, cx + h)
            if L > 0:
                # along t = (p - a).u in [0, L] and across n = (p - a) x u in [-r, r], both linear in x
                xl, xr = -math.inf, math.inf
                for coef, const, blo, bhi in ((ux, (y - ay) * uy - ax * ux, 0.0, L),
                                              (-uy, ax * uy + (y - ay) * ux, -r, r)):
                    if abs(coef) < 1e-12:
                        if not (blo <= const <= bhi):
                            xl, xr = math.inf, -math.inf
                            break
                        continue
                    p, q = (blo - const) / coef, (bhi - const) / coef
                    if p > q:
                        p, q = q, p
                    xl, xr = max(xl, p), min(xr, q)
                if xl <= xr:
                    lo, hi = min(lo, xl), max(hi, xr)
            if lo <= hi:
                self._mark_row(j, lo, hi)

    def add_polyline(self, pts, r):
        if len(pts) == 1:
            self.add_capsule(pts[0], pts[0], r)
        for a, b in zip(pts, pts[1:]):
            self.add_capsule(a, b, r)

    def add_polygon(self, rings, buffer=0.0):
        """Mark the points inside ``rings`` (outer ring plus holes, even-odd rule) and, if ``buffer`` > 0,
        every point within ``buffer`` of any ring edge."""
        rows = {}
        for ring in rings:
            n = len(ring)
            for k in range(n):
                a, b = ring[k], ring[(k + 1) % n]
                if a[1] == b[1]:
                    continue
                for j in self._row_range(min(a[1], b[1]), max(a[1], b[1])):
                    y = self.y0 + j * self.s
                    if (a[1] > y) != (b[1] > y):   # half-open rule: each crossing counted once
                        rows.setdefault(j, []).append(a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1]))
        for j, xs in rows.items():
            xs.sort()
            for q in range(0, len(xs) - 1, 2):
                self._mark_row(j, xs[q], xs[q + 1])
        if buffer > 0:
            for ring in rings:
                n = len(ring)
                for k in range(n):
                    self.add_capsule(ring[k], ring[(k + 1) % n], buffer)


def build_mask(grid, buildings=(), trees=(), forests=(), bridges=(), building_buffer=BUILDING_BUFFER_M,
               tree_radius=TREE_RADIUS_M, bridge_buffer=BRIDGE_BUFFER_M):
    """MaskRaster for the DSM obstacles, all in map-frame metres.

    ``buildings``/``forests``: polygons as ring lists ``[outer, hole, ...]``; ``trees``: (x, y);
    ``bridges``: (polyline points, deck width m), buffered by ``width / 2 + bridge_buffer``."""
    m = MaskRaster(grid)
    for rings in buildings:
        m.add_polygon(rings, building_buffer)
    for x, y in trees:
        m.add_capsule((x, y), (x, y), tree_radius)
    for rings in forests:
        m.add_polygon(rings, 0.0)
    for pts, width in bridges:
        m.add_polyline(pts, width / 2.0 + bridge_buffer)
    return m


def _neighbours(nx, ny):
    """k -> list of 8-neighbour indices (generator per index, bounded)."""
    def nbrs(k):
        j, i = divmod(k, nx)
        out = []
        for dj in (-1, 0, 1):
            jj = j + dj
            if 0 <= jj < ny:
                base = jj * nx
                for di in (-1, 0, 1):
                    ii = i + di
                    if (di or dj) and 0 <= ii < nx:
                        out.append(base + ii)
        return out
    return nbrs


def _hsum(row):
    n = len(row)
    if n == 1:
        return [row[0]]
    return [row[0] + row[1]] + [a + b + c for a, b, c in zip(row, row[1:], row[2:])] + [row[-2] + row[-1]]


def fill_masked(heights, mask, nx, ny, passes=SMOOTHING_PASSES):
    """Filled copy of ``heights`` (rows of floats): masked points get values from the unmasked ones.

    Ordered BFS from the unmasked points (row-major seeds): each newly reached masked point becomes the
    mean of its already-known 8-neighbours. Then ``passes`` Jacobi passes over the masked points only, each
    setting a point to the mean of its 8-neighbours. Unmasked values are never modified. Needs at least one
    unmasked point."""
    n = nx * ny
    flat = [h for row in heights for h in row]
    known = bytearray(b"\x01") * n
    masked_idx = [k for k in range(n) if mask[k]]
    for k in masked_idx:
        known[k] = 0
    if len(masked_idx) == n:
        raise ValueError("fill_masked needs at least one unmasked point")
    nbrs = _neighbours(nx, ny)
    queued = bytearray(n)
    queue = deque()
    for k in masked_idx:
        if any(known[q] for q in nbrs(k)):
            queue.append(k)
            queued[k] = 1
    while queue:
        k = queue.popleft()
        total = cnt = 0
        nb = nbrs(k)
        for q in nb:
            if known[q]:
                total += flat[q]
                cnt += 1
        flat[k] = total / cnt
        known[k] = 1
        for q in nb:
            if not known[q] and not queued[q]:
                queued[q] = 1
                queue.append(q)
    rows = [flat[j * nx:(j + 1) * nx] for j in range(ny)]
    by_row = {}
    for k in masked_idx:
        j, i = divmod(k, nx)
        by_row.setdefault(j, []).append(i)
    colcount = [min(i + 1, nx - 1) - max(i - 1, 0) + 1 for i in range(nx)]
    rowcount = [min(j + 1, ny - 1) - max(j - 1, 0) + 1 for j in range(ny)]
    for _ in range(passes):
        hs = {}

        def hrow(j):
            h = hs.get(j)
            if h is None:
                h = hs[j] = _hsum(rows[j])
            return h

        updates = []
        for j, cols in by_row.items():
            h0 = hrow(j)
            hm = hrow(j - 1) if j > 0 else None
            hp = hrow(j + 1) if j < ny - 1 else None
            row = rows[j]
            rc = rowcount[j]
            new = []
            for i in cols:
                t = h0[i] - row[i]
                if hm is not None:
                    t += hm[i]
                if hp is not None:
                    t += hp[i]
                new.append(t / (colcount[i] * rc - 1))
            updates.append((j, cols, new))
        for j, cols, new in updates:
            row = rows[j]
            for i, v in zip(cols, new):
                row[i] = v
    return rows


def correct_grid(grid, mask, passes=SMOOTHING_PASSES, min_unmasked_fraction=MIN_UNMASKED_FRACTION):
    """(corrected ElevationGrid or None, stats dict) for a :class:`MaskRaster` ``mask`` over ``grid``.

    Returns None (and ``stats['skipped']``) when no point is masked or fewer than ``min_unmasked_fraction``
    of the points are unmasked. Raises NoDataError for any non-finite height: NoData is never filled."""
    nx, ny = grid.nx, grid.ny
    total = nx * ny
    for row in grid.heights:
        for h in row:
            if not math.isfinite(h):
                raise NoDataError("elevation grid contains NoData; the DSM correction never fills NoData")
    m = mask.mask if isinstance(mask, MaskRaster) else mask
    masked = sum(m)
    stats = {"masked_points": masked, "total_points": total, "max_lowering_m": 0.0, "mean_lowering_m": 0.0}
    if masked == 0:
        stats["skipped"] = "nothing to mask"
        return None, stats
    if total - masked < min_unmasked_fraction * total:
        stats["skipped"] = "too few unmasked points"
        return None, stats
    filled = fill_masked(grid.heights, m, nx, ny, passes)
    out = [list(row) for row in grid.heights]
    lower_sum = lower_max = 0.0
    for j in range(ny):
        base = j * nx
        orow, frow, crow = grid.heights[j], filled[j], out[j]
        for i in range(nx):
            if m[base + i] and frow[i] < orow[i]:
                crow[i] = frow[i]
                d = orow[i] - frow[i]
                lower_sum += d
                if d > lower_max:
                    lower_max = d
    stats["max_lowering_m"] = round(lower_max, 3)
    stats["mean_lowering_m"] = round(lower_sum / masked, 3)
    return ElevationGrid(grid.x0, grid.y0, grid.spacing, nx, ny, out, grid.provenance), stats


def apply_correction(grid, requested, buildings=(), trees=(), forests=(), bridges=()):
    """(grid to use, report entry, warning or None). ``requested``: the ``dsm_correction`` setting.

    The report entry is ``{applied, enabled, setting, masked_points, total_points, max_lowering_m,
    mean_lowering_m, reason, ...}``; when the correction is not applied the input grid is returned."""
    enabled, reason = resolve(requested, grid.provenance)
    entry = {"applied": False, "enabled": enabled,
             "setting": {None: "auto", True: "on", False: "off"}[requested],
             "masked_points": 0, "total_points": grid.nx * grid.ny, "max_lowering_m": 0.0,
             "mean_lowering_m": 0.0, "reason": reason}
    if not enabled:
        return grid, entry, None
    mask = build_mask(grid, buildings, trees, forests, bridges)
    corrected, stats = correct_grid(grid, mask)
    entry.update({k: v for k, v in stats.items() if k != "skipped"})
    entry["mask"] = {"building_buffer_m": BUILDING_BUFFER_M, "tree_radius_m": TREE_RADIUS_M,
                     "bridge_buffer_m": f"deck width / 2 + {BRIDGE_BUFFER_M:g}", "forest": "inside landcover",
                     "features": {"buildings": len(buildings), "trees": len(trees), "forest_areas": len(forests),
                                  "bridges": len(bridges)}}
    entry["method"] = (f"ordered BFS fill (mean of known 8-neighbours), {SMOOTHING_PASSES} smoothing passes "
                       "over masked points, min(original, filled)")
    warning = None
    if corrected is None:
        entry["reason"] = stats["skipped"]
        if stats["skipped"] == "too few unmasked points":
            warning = (f"DSM terrain correction skipped: only {grid.nx * grid.ny - stats['masked_points']} of "
                       f"{grid.nx * grid.ny} terrain points are outside buildings/trees/forest/bridges (needs at "
                       f"least {MIN_UNMASKED_FRACTION:.0%}); the terrain is the uncorrected surface model")
        return grid, entry, warning
    entry["applied"] = True
    return corrected, entry, warning
