"""DSM terrain correction (pure Python, no bpy).

Copernicus GLO-30 is a digital *surface* model: buildings, tree canopy and bridge decks are part of
the elevation. This module pushes the terrain under those features back toward the surrounding ground:

1. :class:`MaskRaster` marks the grid points inside building footprints (buffered), tree crowns,
   forest/wood landcover and bridge deck ribbons (buffered).
2. :func:`fill_masked` replaces the masked points by a harmonic (Laplace) interpolation of the
   unmasked ones, solved coarse to fine (multigrid: nested-iteration initial guess, then V-cycles).
   A plane is reproduced and the fill stays within the range of the surrounding ground (maximum
   principle), so relief inside large masked areas is interpolated, not flattened.
3. :func:`correct_grid` keeps ``min(original, filled)`` at masked points: terrain is never raised and
   unmasked points are returned bit-for-bit unchanged.

The result is an approximation of the ground, not a bare-earth DTM. It is a derived step: the raw
elevation provenance (provider, tiles, file hashes) is left unchanged and the correction is reported
separately (``report.json`` ``terrain_correction``).

Work is linear in the grid size (the multigrid solve is bounded by :data:`MAX_VCYCLES` V-cycles on large
grids and :data:`VCYCLE_WORK_BUDGET` on small ones) and in the total
length of the mask geometry (rasterised per row), with no all-pairs loops; grids are bounded by
:data:`dem.MAX_GRID_POINTS`.
"""

import math

from .dem import ElevationGrid
from .errors import NoDataError

BUILDING_BUFFER_M = 15.0      # about half a GLO-30 pixel around each footprint
TREE_RADIUS_M = 6.0           # OSM natural=tree crown radius
BRIDGE_BUFFER_M = 15.0        # added to half the deck width
FINE_PASSES = 2               # initial-guess Gauss-Seidel passes at the finest level; doubled per coarser level
MAX_LEVEL_PASSES = 256        # cap on the initial-guess passes of any level
COARSEST_PASSES = 200         # passes on a coarsest level of at most 64 cells
VCYCLE_SMOOTHING = 2          # Gauss-Seidel passes before and after each coarse-grid correction
MAX_VCYCLES = 10              # V-cycle cap on large grids
VCYCLE_WORK_BUDGET = 4_000_000  # small grids may run more V-cycles while cycles * points stays below this
VCYCLE_LIMIT = 200            # absolute V-cycle cap (thin or tiny grids converge slowly but cheaply)
VCYCLE_TOLERANCE_M = 0.005    # stop when the largest update / coarse-grid correction is below this
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


def _axis_weights(n, nc):
    """Per fine index: (coarse a, coarse b, weight a, weight b) of the cell-centred linear prolongation
    (fine point i lies at coarse coordinate (i - 0.5) / 2), clamped at the grid edges."""
    out = []
    for i in range(n):
        c = i // 2
        a, b, wa = (c - 1, c, 0.25) if i % 2 == 0 else (c, c + 1, 0.75)
        out.append((min(max(a, 0), nc - 1), min(max(b, 0), nc - 1), wa, 1.0 - wa))
    return out


def _zeros(nx, ny):
    return [[0.0] * (nx + 2) for _ in range(ny + 2)]


class _Level:
    """One level of the coarse-to-fine hierarchy.

    Arrays on a level are padded row lists ``U[j][i]`` (j in 1..ny, i in 1..nx) with a ghost border.
    ``known[j]`` (padded bytes, ghosts 1) marks the fixed points; ``spans`` lists (j, first, last)
    unknown column per row that has unknown points; ``edge`` is True if an unknown point lies on the grid
    edge (its ghost neighbours then mirror it: a natural boundary, i.e. the mean of the in-grid
    neighbours)."""

    __slots__ = ("nx", "ny", "known", "spans", "edge", "wy")

    def __init__(self, rows, nx, ny):
        self.nx, self.ny = nx, ny
        border = b"\x01" * (nx + 2)
        self.known = [border] + [b"\x01" + r + b"\x01" for r in rows] + [border]
        self.spans = []
        for j, r in enumerate(rows, 1):
            lo = r.find(0)
            if lo >= 0:
                self.spans.append((j, lo + 1, r.rfind(0) + 1))
        self.edge = any(j in (1, ny) or lo == 1 or hi == nx for j, lo, hi in self.spans)
        self.wy = None


def _hierarchy(known_rows, nx, ny):
    """Levels from fine to coarse, halving the grid (2 x 2 blocks). A coarse cell is known if any of its
    children is known. Stops at 2 x 2 cells or before a level with no unknown cell."""
    levels = [_Level(known_rows, nx, ny)]
    while nx > 2 or ny > 2:
        cx, cy = (nx + 1) // 2, (ny + 1) // 2
        crows = []
        for jc in range(cy):
            r0 = known_rows[2 * jc]
            r1 = known_rows[2 * jc + 1] if 2 * jc + 1 < ny else r0
            row = (int.from_bytes(r0, "big") | int.from_bytes(r1, "big")).to_bytes(nx, "big")
            if nx % 2:
                row += b"\x00"
            crows.append(bytes(a | b for a, b in zip(row[0::2], row[1::2])))
        if all(0 not in r for r in crows):
            break
        levels[-1].wy = _axis_weights(ny, cy)
        known_rows, nx, ny = crows, cx, cy
        levels.append(_Level(known_rows, nx, ny))
    return levels


def _ghosts(U, lev):
    """Copy the edge values into the ghost border (natural boundary)."""
    nx, ny = lev.nx, lev.ny
    for j in range(1, ny + 1):
        r = U[j]
        r[0] = r[1]
        r[nx + 1] = r[nx]
    U[0][:] = U[1]
    U[ny + 1][:] = U[ny]


def _gauss_seidel(U, lev, passes, B=None):
    """``passes`` red-black Gauss-Seidel passes over the unknown points of the 5-point equation
    ``4 * u - sum(neighbours) = b``. For Laplace (``B`` None) each update is the mean of the neighbours."""
    K = lev.known
    for _ in range(passes):
        for colour in (0, 1):
            if lev.edge:
                _ghosts(U, lev)
            for j, lo, hi in lev.spans:
                row, up, dn, kn = U[j], U[j - 1], U[j + 1], K[j]
                s = lo + ((lo + j + colour) & 1)
                e = hi + 1
                if B is None:
                    row[s:e:2] = [v if f else (le + ri + a + d) * 0.25 for v, f, le, ri, a, d in
                                  zip(row[s:e:2], kn[s:e:2], row[s - 1:e - 1:2], row[s + 1:e + 1:2], up[s:e:2],
                                      dn[s:e:2])]
                else:
                    row[s:e:2] = [v if f else (le + ri + a + d + b) * 0.25 for v, f, le, ri, a, d, b in
                                  zip(row[s:e:2], kn[s:e:2], row[s - 1:e - 1:2], row[s + 1:e + 1:2], up[s:e:2],
                                      dn[s:e:2], B[j][s:e:2])]


def _restricted_residual(U, B, lev, clev):
    """(coarse right-hand side or None, largest absolute residual). The residual is ``b + sum(neighbours)
    - 4 * u`` at the unknown points; per coarse cell (``clev``), the right-hand side is the sum of its
    children's residuals (the operator is unscaled, so a cell of twice the spacing carries four times the
    source)."""
    nx = lev.nx
    cx = clev.nx if clev is not None else 0
    out = _zeros(cx, clev.ny) if clev is not None else None
    if lev.edge:
        _ghosts(U, lev)
    K = lev.known
    rmax = 0.0
    for j, _, _ in lev.spans:
        row, up, dn, kn = U[j], U[j - 1], U[j + 1], K[j]
        if B is None:
            r = [0.0 if f else le + ri + a + d - 4.0 * v for v, f, le, ri, a, d in
                 zip(row[1:nx + 1], kn[1:nx + 1], row[0:nx], row[2:nx + 2], up[1:nx + 1], dn[1:nx + 1])]
        else:
            r = [0.0 if f else le + ri + a + d - 4.0 * v + b for v, f, le, ri, a, d, b in
                 zip(row[1:nx + 1], kn[1:nx + 1], row[0:nx], row[2:nx + 2], up[1:nx + 1], dn[1:nx + 1],
                     B[j][1:nx + 1])]
        rmax = max(rmax, max(r), -min(r))
        if out is None:
            continue
        if nx % 2:
            r.append(0.0)
        dst = out[((j - 1) >> 1) + 1]
        dst[1:cx + 1] = [t + a + b for t, a, b in zip(dst[1:cx + 1], r[0::2], r[1::2])]
    return out, rmax


def _prolongate(U, lev, Uc, clev, add):
    """Bilinear prolongation of the coarser level ``Uc`` onto the unknown points of ``U`` (in place). It
    replaces them (initial guess) or, with ``add``, is added to them (coarse-grid correction)."""
    cx, K = clev.nx, lev.known
    for j, lo, hi in lev.spans:
        ja, jb, va, vb = lev.wy[j - 1]
        crow = [va * a + vb * b for a, b in zip(Uc[ja + 1][1:cx + 1], Uc[jb + 1][1:cx + 1])]
        ext = [crow[0]] + crow + [crow[-1]]
        f = [0.0] * (2 * cx)
        f[0::2] = [0.25 * a + 0.75 * b for a, b in zip(ext, ext[1:cx + 1])]
        f[1::2] = [0.75 * a + 0.25 * b for a, b in zip(ext[1:cx + 1], ext[2:])]
        row, kn = U[j], K[j]
        if add:
            row[lo:hi + 1] = [v if k else v + w for v, k, w in zip(row[lo:hi + 1], kn[lo:hi + 1], f[lo - 1:hi])]
        else:
            row[lo:hi + 1] = [v if k else w for v, k, w in zip(row[lo:hi + 1], kn[lo:hi + 1], f[lo - 1:hi])]


def _coarse_values(U, lev, clev):
    """Coarse values for the initial guess: each known coarse cell holds the mean of its known children."""
    nx, ny, cx = lev.nx, lev.ny, clev.nx
    Uc = _zeros(cx, clev.ny)
    for jc in range(clev.ny):
        tot = [0.0] * cx
        cnt = [0] * cx
        for j in (2 * jc + 1, 2 * jc + 2):
            if j > ny:
                break
            kn = lev.known[j][1:nx + 1] + b"\x00"
            t = [v if f else 0.0 for v, f in zip(U[j][1:nx + 1], kn)] + [0.0]
            tot = [s + a + b for s, a, b in zip(tot, t[0::2], t[1::2])]
            cnt = [s + a + b for s, a, b in zip(cnt, kn[0::2], kn[1::2])]
        Uc[jc + 1][1:cx + 1] = [t / c if c else 0.0 for t, c in zip(tot, cnt)]
    return Uc


def _coarsest_passes(lev, passes):
    return COARSEST_PASSES if lev.nx * lev.ny <= 64 else passes


def _vcycle(levels, level, U, B):
    """One correction-scheme V-cycle at ``level``. Returns the convergence measure: the larger of the
    largest Gauss-Seidel update implied by the residual before the cycle (``|r| / 4``) and the largest
    coarse-grid correction."""
    lev = levels[level]
    if level == len(levels) - 1:
        _gauss_seidel(U, lev, _coarsest_passes(lev, 2 * VCYCLE_SMOOTHING), B)
        return _restricted_residual(U, B, lev, None)[1] * 0.25 if level == 0 else 0.0
    _gauss_seidel(U, lev, VCYCLE_SMOOTHING, B)
    clev = levels[level + 1]
    rhs, rmax = _restricted_residual(U, B, lev, clev)
    E = _zeros(clev.nx, clev.ny)
    _vcycle(levels, level + 1, E, rhs)
    _prolongate(U, lev, E, clev, True)
    _gauss_seidel(U, lev, VCYCLE_SMOOTHING, B)
    return max(rmax * 0.25, max(max(max(r), -min(r)) for r in E))


def fill_masked(heights, mask, nx, ny, passes=FINE_PASSES):
    """Filled copy of ``heights`` (rows of floats): masked points get a harmonic (Laplace) interpolation of
    the unmasked ones, which stay fixed.

    The discrete problem is the 5-point Laplace equation at the masked points, with the unmasked points
    fixed and a natural boundary (mean of the in-grid neighbours) at the grid edge. It is solved coarse to
    fine (multigrid) on a hierarchy of halved grids, where a coarse cell is known if any of its four
    children is known, with red-black Gauss-Seidel passes:

    1. Initial guess (nested iteration): known coarse cells hold the mean of their known children. The
       coarsest level (at most 2 x 2 cells, or the last level with unknown cells) is smoothed; each finer
       level starts its unknown points from the bilinear prolongation of the coarser solution and runs
       ``passes * 2**level`` passes (at most :data:`MAX_LEVEL_PASSES`).
    2. The coarse means are biased near the mask edge and on curved ground, so correction-scheme V-cycles
       (:data:`VCYCLE_SMOOTHING` passes before and after each coarse-grid correction) follow on the finest
       level until the largest Gauss-Seidel update (``|residual| / 4``) and the largest coarse correction
       are below :data:`VCYCLE_TOLERANCE_M`, at most :data:`MAX_VCYCLES` times on large grids (small or
       thin grids, which converge more slowly per cycle, may use up to :data:`VCYCLE_LIMIT` cycles within
       :data:`VCYCLE_WORK_BUDGET`).

    Work is bounded and linear in the grid size. The result obeys the maximum principle (it is also
    clamped to the range of the unmasked values against round-off) and is deterministic. Needs at least
    one unmasked point."""
    if passes < 0:
        raise ValueError("passes must be >= 0")
    known_flat = bytes(0 if m else 1 for m in mask[:nx * ny])
    if 1 not in known_flat:
        raise ValueError("fill_masked needs at least one unmasked point")
    rows = [[float(h) for h in row] for row in heights]
    if 0 not in known_flat:
        return rows
    known_rows = [known_flat[j * nx:(j + 1) * nx] for j in range(ny)]
    fixed = [v for row, kn in zip(rows, known_rows) for v, f in zip(row, kn) if f]
    lo_v, hi_v = min(fixed), max(fixed)
    U = [[r[0]] + r + [r[-1]] for r in rows]
    U = [U[0][:]] + U + [U[-1][:]]
    levels = _hierarchy(known_rows, nx, ny)
    vals = [U]
    for lev, clev in zip(levels, levels[1:]):
        vals.append(_coarse_values(vals[-1], lev, clev))
    top, T = levels[-1], vals[-1]
    tk = [v for j in range(1, top.ny + 1) for v, f in zip(T[j][1:top.nx + 1], top.known[j][1:top.nx + 1]) if f]
    start = sum(tk) / len(tk)
    for j, lo, hi in top.spans:
        T[j][lo:hi + 1] = [v if f else start for v, f in zip(T[j][lo:hi + 1], top.known[j][lo:hi + 1])]
    _gauss_seidel(T, top, _coarsest_passes(top, min(passes << (len(levels) - 1), MAX_LEVEL_PASSES)))
    for level in range(len(levels) - 2, -1, -1):
        _prolongate(vals[level], levels[level], vals[level + 1], levels[level + 1], False)
        _gauss_seidel(vals[level], levels[level], min(passes << level, MAX_LEVEL_PASSES))
    for _ in range(min(VCYCLE_LIMIT, max(MAX_VCYCLES, VCYCLE_WORK_BUDGET // (nx * ny)))):
        if _vcycle(levels, 0, U, None) < VCYCLE_TOLERANCE_M:
            break
    K = levels[0].known
    for j, lo, hi in levels[0].spans:
        U[j][lo:hi + 1] = [v if f else min(max(v, lo_v), hi_v) for v, f in zip(U[j][lo:hi + 1], K[j][lo:hi + 1])]
    return [U[j][1:nx + 1] for j in range(1, ny + 1)]


def correct_grid(grid, mask, passes=FINE_PASSES, min_unmasked_fraction=MIN_UNMASKED_FRACTION):
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
    entry["method"] = ("harmonic (Laplace, 5-point) interpolation of the masked points from the unmasked ones, "
                       "solved coarse to fine (multigrid: nested-iteration initial guess from 2 x 2 coarsened "
                       "levels, then a bounded number of V-cycles of red-black Gauss-Seidel until the largest "
                       f"update is below {VCYCLE_TOLERANCE_M:g} m), min(original, filled)")
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
