"""DSM terrain correction (pure Python, no bpy).

Copernicus GLO-30 is a digital *surface* model: buildings, tree canopy and bridge decks are part of
the elevation. This module pushes the terrain under those features back toward the surrounding ground:

1. :class:`MaskRaster` marks the grid points inside building footprints (buffered), tree crowns,
   forest/wood landcover and bridge deck ribbons (buffered).
2. :func:`fill_masked` replaces the masked points by a harmonic (Laplace) interpolation of the
   unmasked ones, solved coarse to fine (multigrid: nested-iteration initial guess, then V- or W-cycles;
   elongated grids are semi-coarsened along their long axis). The fill stays within the range of the
   surrounding ground (maximum principle), so relief inside large masked areas is interpolated, not
   flattened. A plane is reproduced where the masked area is enclosed by known ground; where the mask
   reaches the grid edge the natural (zero-slope) edge condition bends the fill there. A fill that has not
   converged within its bounded cycles is never applied (the correction is skipped with a warning).
3. :func:`correct_grid` keeps ``min(original, filled)`` at masked points: terrain is never raised and
   unmasked points are returned bit-for-bit unchanged.

The result is an approximation of the ground, not a bare-earth DTM. It is a derived step: the raw
elevation provenance (provider, tiles, file hashes) is left unchanged and the correction is reported
separately (``report.json`` ``terrain_correction``).

Work is linear in the grid size (the multigrid solve is bounded by :func:`vcycle_cap` cycles) and in the
total length of the mask geometry: polygons are rasterised by a scanline sweep holding one row's crossings
(memory O(edges + crossings of one row)), and the cumulative rasterisation work (edges plus row
crossings) is bounded by :data:`MASK_WORK_BUDGET`, checked before any terrain change. Work limits skip the
correction with a warning rather than failing the build (the uncorrected surface model is used); hard input
limits (``max_features``, :data:`dem.MAX_GRID_POINTS`) remain LimitError.
"""

import math

from .dem import ElevationGrid
from .errors import LimitError, NoDataError

BUILDING_BUFFER_M = 15.0      # about half a GLO-30 pixel around each footprint
TREE_RADIUS_M = 6.0           # OSM natural=tree crown radius
BRIDGE_BUFFER_M = 15.0        # added to half the deck width
MAX_BRIDGE_HALF_WIDTH_M = 30.0  # generate.road_width never exceeds 60 m
# Mask candidates are selected beyond the scene area (core/osm.py classify), against the terrain grid
# extent expanded by these reaches; bridge polylines are clipped to the extent expanded by the largest one.
BRIDGE_CANDIDATE_MARGIN_M = MAX_BRIDGE_HALF_WIDTH_M + BRIDGE_BUFFER_M
MASK_WORK_BUDGET = 20_000_000  # cumulative rasterisation work units (edges plus row crossings / capsule rows)
FINE_PASSES = 2               # initial-guess Gauss-Seidel passes at the finest level; doubled per coarser level
MAX_LEVEL_PASSES = 256        # cap on the initial-guess passes of any level
COARSEST_PASSES = 200         # passes on a coarsest level of at most 64 cells
VCYCLE_SMOOTHING = 2          # Gauss-Seidel passes before and after each coarse-grid correction
MAX_VCYCLES = 10              # V-cycle cap on large grids
VCYCLE_WORK_BUDGET = 4_000_000  # small grids may run more V-cycles while cycles * points stays below this
VCYCLE_LIMIT = 200            # absolute V-cycle cap (thin or tiny grids converge slowly but cheaply)
VCYCLE_TOLERANCE_M = 0.005    # stop when the largest update / coarse-grid correction is below this
W_CYCLE_MAX_COST = 3.0        # W-cycles are used when one costs at most this many times the fine grid's points
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
        self.work = 0

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
        every point within ``buffer`` of any ring edge.

        Scanline sweep with an active-edge table: edges are sorted by their first grid row and only the
        crossings of the current row are held, so memory is O(edges + crossings of one row) and work is
        O(edges log edges + crossings). Rows outside the grid are never visited."""
        edges = []
        for ring in rings:
            n = len(ring)
            for k in range(n):
                a, b = ring[k], ring[(k + 1) % n]
                if a[1] == b[1]:
                    continue
                rr = self._row_range(min(a[1], b[1]), max(a[1], b[1]))
                if rr.start < rr.stop:
                    edges.append((rr.start, rr.stop, a[0], a[1], b[0], b[1]))
        if edges:
            edges.sort(key=lambda e: e[0])
            active, k, ne = [], 0, len(edges)
            j = edges[0][0]
            while k < ne or active:
                if not active and edges[k][0] > j:
                    j = edges[k][0]
                while k < ne and edges[k][0] <= j:
                    active.append(edges[k])
                    k += 1
                y = self.y0 + j * self.s
                # half-open rule: each crossing counted once
                xs = sorted(ax + (y - ay) * (bx - ax) / (by - ay) for _, _, ax, ay, bx, by in active
                            if (ay > y) != (by > y))
                for q in range(0, len(xs) - 1, 2):
                    self._mark_row(j, xs[q], xs[q + 1])
                j += 1
                active = [e for e in active if e[1] > j]
        if buffer > 0:
            for ring in rings:
                n = len(ring)
                for k in range(n):
                    self.add_capsule(ring[k], ring[(k + 1) % n], buffer)

    def _rows(self, ylo, yhi):
        r = self._row_range(ylo, yhi)
        return max(0, r.stop - r.start)

    def capsule_work(self, a, b, r):
        """Rasterisation work units of :meth:`add_capsule`: 1 + the grid rows it visits."""
        return 1 + self._rows(min(a[1], b[1]) - r, max(a[1], b[1]) + r)

    def polygon_work(self, rings, buffer=0.0):
        """Rasterisation work units of :meth:`add_polygon` (an upper bound): per edge 1 + the grid rows it
        may cross, plus the buffer capsules."""
        w = 0
        for ring in rings:
            n = len(ring)
            for k in range(n):
                a, b = ring[k], ring[(k + 1) % n]
                w += 1 + (self._rows(min(a[1], b[1]), max(a[1], b[1])) if a[1] != b[1] else 0)
                if buffer > 0:
                    w += self.capsule_work(a, b, buffer)
        return w


def build_mask(grid, buildings=(), trees=(), forests=(), bridges=(), building_buffer=BUILDING_BUFFER_M,
               tree_radius=TREE_RADIUS_M, bridge_buffer=BRIDGE_BUFFER_M, work_budget=MASK_WORK_BUDGET):
    """MaskRaster for the DSM obstacles, all in map-frame metres.

    ``buildings``/``forests``: polygons as ring lists ``[outer, hole, ...]``; ``trees``: (x, y);
    ``bridges``: (polyline points, deck width m), buffered by ``width / 2 + bridge_buffer``. Features may
    extend beyond the grid: rasterisation is clipped to it.

    The cumulative rasterisation work (edges plus the grid rows each edge or capsule may cross, see
    :meth:`MaskRaster.polygon_work`) is counted from the geometry first, in O(edges), and LimitError is
    raised before anything is rasterised if it exceeds ``work_budget``."""
    m = MaskRaster(grid)
    work = 0
    for rings in buildings:
        work += m.polygon_work(rings, building_buffer)
    for x, y in trees:
        work += m.capsule_work((x, y), (x, y), tree_radius)
    for rings in forests:
        work += m.polygon_work(rings, 0.0)
    for pts, width in bridges:
        r = width / 2.0 + bridge_buffer
        work += (m.capsule_work(pts[0], pts[0], r) if len(pts) == 1 else
                 sum(m.capsule_work(a, b, r) for a, b in zip(pts, pts[1:])))
    if work > work_budget:
        raise LimitError(f"DSM mask rasterisation needs {work} work units (edges plus row crossings); the "
                         f"budget is {work_budget}")
    for rings in buildings:
        m.add_polygon(rings, building_buffer)
    for x, y in trees:
        m.add_capsule((x, y), (x, y), tree_radius)
    for rings in forests:
        m.add_polygon(rings, 0.0)
    for pts, width in bridges:
        m.add_polyline(pts, width / 2.0 + bridge_buffer)
    m.work = work
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


def _identity_weights(n):
    return [(i, i, 1.0, 0.0) for i in range(n)]


class _Level:
    """One level of the coarse-to-fine hierarchy.

    Arrays on a level are padded row lists ``U[j][i]`` (j in 1..ny, i in 1..nx) with a ghost border.
    ``known[j]`` (padded bytes, ghosts 1) marks the fixed points; ``spans`` lists (j, first, last)
    unknown column per row that has unknown points; ``edge`` is True if an unknown point lies on the grid
    edge (its ghost neighbours then mirror it: a natural boundary, i.e. the mean of the in-grid
    neighbours).

    The level's cells measure ``sx`` x ``sy`` fine spacings; its 5-point operator is
    ``c * u - wx * (left + right) - wy * (up + down)`` with ``wx = 1 / sx**2``, ``wy = 1 / sy**2`` and
    ``c = 2 * (wx + wy)`` (on the finest level ``4 * u - sum(neighbours)``). ``fx``/``fy`` (1 or 2) are the
    coarsening factors to the next level and ``px``/``py`` the per-axis prolongation weights."""

    __slots__ = ("nx", "ny", "known", "spans", "edge", "wx", "wy", "c", "ax", "ay", "ab", "fx", "fy", "px", "py")

    def __init__(self, rows, nx, ny, sx=1, sy=1):
        self.nx, self.ny = nx, ny
        border = b"\x01" * (nx + 2)
        self.known = [border] + [b"\x01" + r + b"\x01" for r in rows] + [border]
        self.spans = []
        for j, r in enumerate(rows, 1):
            lo = r.find(0)
            if lo >= 0:
                self.spans.append((j, lo + 1, r.rfind(0) + 1))
        self.edge = any(j in (1, ny) or lo == 1 or hi == nx for j, lo, hi in self.spans)
        # a single row (column) has mirrored ghosts on both sides: its y (x) terms cancel exactly, so they
        # are dropped instead of being iterated (which would damp every update by half)
        self.wx = 1.0 / (sx * sx) if nx > 1 else 0.0
        self.wy = 1.0 / (sy * sy) if ny > 1 else 0.0
        self.c = 2.0 * (self.wx + self.wy) or 1.0
        self.ax, self.ay, self.ab = self.wx / self.c, self.wy / self.c, 1.0 / self.c
        self.fx = self.fy = 1
        self.px = self.py = None


def _hierarchy(known_rows, nx, ny):
    """Levels from fine to coarse. Each level halves every axis that still has more than 2 cells (2 x 2
    blocks while both can be halved; semi-coarsening of the long axis of an elongated grid once the short
    one is down to 1 or 2 cells, so that a 5001 x 51 grid still coarsens to a few cells). A coarse cell is
    known if any of its children is known. Stops at 2 x 2 cells or before a level with no unknown cell."""
    levels = [_Level(known_rows, nx, ny)]
    sx = sy = 1
    while nx > 1 or ny > 1:
        fx, fy = (2 if nx > 1 else 1), (2 if ny > 1 else 1)
        cx = (nx + 1) // 2 if fx == 2 else nx
        cy = (ny + 1) // 2 if fy == 2 else ny
        crows = []
        for jc in range(cy):
            if fy == 2:
                r0 = known_rows[2 * jc]
                r1 = known_rows[2 * jc + 1] if 2 * jc + 1 < ny else r0
                row = (int.from_bytes(r0, "big") | int.from_bytes(r1, "big")).to_bytes(nx, "big")
            else:
                row = known_rows[jc]
            if fx == 2:
                if nx % 2:
                    row += b"\x00"
                row = bytes(a | b for a, b in zip(row[0::2], row[1::2]))
            crows.append(row)
        if all(0 not in r for r in crows):
            break
        lev = levels[-1]
        lev.fx, lev.fy = fx, fy
        lev.px = _axis_weights(nx, cx) if fx == 2 else None
        lev.py = _axis_weights(ny, cy) if fy == 2 else _identity_weights(ny)
        sx, sy = sx * fx, sy * fy
        known_rows, nx, ny = crows, cx, cy
        levels.append(_Level(known_rows, nx, ny, sx, sy))
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
    """``passes`` red-black Gauss-Seidel passes over the unknown points of the level's 5-point equation
    ``c * u - wx * (left + right) - wy * (up + down) = b``. For Laplace (``B`` None) on an isotropic level
    each update is the mean of the neighbours."""
    K = lev.known
    ax, ay, ab = lev.ax, lev.ay, lev.ab
    iso = ax == ay
    for _ in range(passes):
        for colour in (0, 1):
            if lev.edge:
                _ghosts(U, lev)
            for j, lo, hi in lev.spans:
                row, up, dn, kn = U[j], U[j - 1], U[j + 1], K[j]
                s = lo + ((lo + j + colour) & 1)
                e = hi + 1
                if B is None and iso:
                    row[s:e:2] = [v if f else (le + ri + a + d) * ax for v, f, le, ri, a, d in
                                  zip(row[s:e:2], kn[s:e:2], row[s - 1:e - 1:2], row[s + 1:e + 1:2], up[s:e:2],
                                      dn[s:e:2])]
                elif B is None:
                    row[s:e:2] = [v if f else (le + ri) * ax + (a + d) * ay for v, f, le, ri, a, d in
                                  zip(row[s:e:2], kn[s:e:2], row[s - 1:e - 1:2], row[s + 1:e + 1:2], up[s:e:2],
                                      dn[s:e:2])]
                else:
                    row[s:e:2] = [v if f else (le + ri) * ax + (a + d) * ay + b * ab for v, f, le, ri, a, d, b in
                                  zip(row[s:e:2], kn[s:e:2], row[s - 1:e - 1:2], row[s + 1:e + 1:2], up[s:e:2],
                                      dn[s:e:2], B[j][s:e:2])]


def _restricted_residual(U, B, lev, clev):
    """(coarse right-hand side or None, largest Gauss-Seidel update ``|residual| / c``).

    The residual is ``b + wx * (left + right) + wy * (up + down) - c * u`` at the unknown points. Each
    level's operator is scaled by its own cell size, so the coarse right-hand side (``clev``) is the mean
    of the residuals of a coarse cell's children inside the grid."""
    nx = lev.nx
    wx, wy, c = lev.wx, lev.wy, lev.c
    cx = clev.nx if clev is not None else 0
    out = _zeros(cx, clev.ny) if clev is not None else None
    if lev.edge:
        _ghosts(U, lev)
    K = lev.known
    rmax = 0.0
    for j, _, _ in lev.spans:
        row, up, dn, kn = U[j], U[j - 1], U[j + 1], K[j]
        if B is None:
            r = [0.0 if f else (le + ri) * wx + (a + d) * wy - c * v for v, f, le, ri, a, d in
                 zip(row[1:nx + 1], kn[1:nx + 1], row[0:nx], row[2:nx + 2], up[1:nx + 1], dn[1:nx + 1])]
        else:
            r = [0.0 if f else (le + ri) * wx + (a + d) * wy - c * v + b for v, f, le, ri, a, d, b in
                 zip(row[1:nx + 1], kn[1:nx + 1], row[0:nx], row[2:nx + 2], up[1:nx + 1], dn[1:nx + 1],
                     B[j][1:nx + 1])]
        rmax = max(rmax, max(r), -min(r))
        if out is None:
            continue
        if lev.fx == 2:
            if nx % 2:
                r.append(0.0)
            r = [a + b for a, b in zip(r[0::2], r[1::2])]
        dst = out[((j - 1) >> 1) + 1 if lev.fy == 2 else j]
        dst[1:cx + 1] = [t + a for t, a in zip(dst[1:cx + 1], r)]
    if out is not None:
        scale = 1.0 / (lev.fx * lev.fy)
        for jc in range(1, clev.ny + 1):
            out[jc][1:cx + 1] = [t * scale for t in out[jc][1:cx + 1]]
    return out, rmax / c


def _prolongate(U, lev, Uc, clev, add):
    """Linear prolongation (per coarsened axis) of the coarser level ``Uc`` onto the unknown points of ``U``
    (in place). It replaces them (initial guess) or, with ``add``, is added to them (coarse-grid
    correction)."""
    cx, K = clev.nx, lev.known
    for j, lo, hi in lev.spans:
        ja, jb, va, vb = lev.py[j - 1]
        crow = [va * a + vb * b for a, b in zip(Uc[ja + 1][1:cx + 1], Uc[jb + 1][1:cx + 1])]
        if lev.fx == 2:
            ext = [crow[0]] + crow + [crow[-1]]
            f = [0.0] * (2 * cx)
            f[0::2] = [0.25 * a + 0.75 * b for a, b in zip(ext, ext[1:cx + 1])]
            f[1::2] = [0.75 * a + 0.25 * b for a, b in zip(ext[1:cx + 1], ext[2:])]
        else:
            f = crow
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
        for j in ((2 * jc + 1, 2 * jc + 2) if lev.fy == 2 else (jc + 1,)):
            if j > ny:
                break
            kn = lev.known[j][1:nx + 1]
            t = [v if f else 0.0 for v, f in zip(U[j][1:nx + 1], kn)]
            if lev.fx == 2:
                kn += b"\x00"
                t.append(0.0)
                tot = [s + a + b for s, a, b in zip(tot, t[0::2], t[1::2])]
                cnt = [s + a + b for s, a, b in zip(cnt, kn[0::2], kn[1::2])]
            else:
                tot = [s + a for s, a in zip(tot, t)]
                cnt = [s + a for s, a in zip(cnt, kn)]
        Uc[jc + 1][1:cx + 1] = [t / c if c else 0.0 for t, c in zip(tot, cnt)]
    return Uc


def _coarsest_passes(lev, passes):
    return COARSEST_PASSES if lev.nx * lev.ny <= 64 else passes


def _w_cycle_ok(levels):
    """True if a W-cycle (coarse levels below the first visited twice) costs at most
    :data:`W_CYCLE_MAX_COST` times the finest level's points. That holds when both axes are halved (about
    1.5 times) and on moderately elongated grids, but not on extreme strips, where repeated semi-coarsened
    levels would make each cycle O(n log n); those use V-cycles."""
    visits, cost = 1, 0
    for k, lev in enumerate(levels):
        cost += visits * lev.nx * lev.ny
        if 1 <= k and k + 2 < len(levels):
            visits *= 2
    return cost <= W_CYCLE_MAX_COST * levels[0].nx * levels[0].ny


def _vcycle(levels, level, U, B, w=False):
    """One correction-scheme cycle at ``level`` (a V-cycle, or with ``w`` a W-cycle: every level below the
    first, except the coarsest, solves its coarse-grid problem twice). Returns the convergence measure: the
    larger of the largest Gauss-Seidel update implied by the residual before the cycle (``|r| / c``) and the
    largest coarse-grid correction."""
    lev = levels[level]
    if level == len(levels) - 1:
        _gauss_seidel(U, lev, _coarsest_passes(lev, 2 * VCYCLE_SMOOTHING), B)
        return _restricted_residual(U, B, lev, None)[1] if level == 0 else 0.0
    _gauss_seidel(U, lev, VCYCLE_SMOOTHING, B)
    clev = levels[level + 1]
    rhs, update = _restricted_residual(U, B, lev, clev)
    E = _zeros(clev.nx, clev.ny)
    _vcycle(levels, level + 1, E, rhs, w)
    if w and level >= 1 and level + 2 < len(levels):
        _vcycle(levels, level + 1, E, rhs, w)
    _prolongate(U, lev, E, clev, True)
    _gauss_seidel(U, lev, VCYCLE_SMOOTHING, B)
    return max(update, max(max(max(r), -min(r)) for r in E))


def vcycle_cap(nx, ny):
    """Largest number of V-cycles :func:`fill_masked` runs on an ``nx`` x ``ny`` grid."""
    return min(VCYCLE_LIMIT, max(MAX_VCYCLES, VCYCLE_WORK_BUDGET // (nx * ny)))


def fill_masked(heights, mask, nx, ny, passes=FINE_PASSES, info=None):
    """Filled copy of ``heights`` (rows of floats): masked points get a harmonic (Laplace) interpolation of
    the unmasked ones, which stay fixed.

    The discrete problem is the 5-point Laplace equation at the masked points, with the unmasked points
    fixed and a natural boundary (mean of the in-grid neighbours) at the grid edge. It is solved coarse to
    fine (multigrid) on a hierarchy of coarsened grids (:func:`_hierarchy`: 2 x 2 blocks, then the long
    axis alone on elongated grids; each level's operator is scaled by its cell size), where a coarse cell
    is known if any of its children is known, with red-black Gauss-Seidel passes:

    1. Initial guess (nested iteration): known coarse cells hold the mean of their known children. The
       coarsest level (at most 2 x 2 cells, or the last level with unknown cells) is smoothed; each finer
       level starts its unknown points from the linear prolongation of the coarser solution and runs
       ``passes * 2**level`` passes (at most :data:`MAX_LEVEL_PASSES`).
    2. The coarse means are biased near the mask edge and on curved ground, so correction-scheme cycles
       (:data:`VCYCLE_SMOOTHING` passes before and after each coarse-grid correction; W-cycles when
       :func:`_w_cycle_ok`, else V-cycles) follow on the finest
       level until the largest Gauss-Seidel update (``|residual| / 4``) and the largest coarse correction
       are below :data:`VCYCLE_TOLERANCE_M`, at most :func:`vcycle_cap` times (:data:`MAX_VCYCLES` on large
       grids; small or thin grids may use up to :data:`VCYCLE_LIMIT` cycles within
       :data:`VCYCLE_WORK_BUDGET`).

    If ``info`` is a dict it receives ``cycles`` (V-cycles run), ``residual_m`` (the largest Gauss-Seidel
    update ``|residual| / 4`` of the returned fill, metres) and ``converged`` (the convergence measure fell
    below the tolerance within the cap). A fill that did not converge is still returned; callers decide.

    Work is bounded and linear in the grid size. The result obeys the maximum principle (it is also
    clamped to the range of the unmasked values against round-off) and is deterministic. Needs at least
    one unmasked point."""
    if passes < 0:
        raise ValueError("passes must be >= 0")
    known_flat = bytes(0 if m else 1 for m in mask[:nx * ny])
    if 1 not in known_flat:
        raise ValueError("fill_masked needs at least one unmasked point")
    rows = [[float(h) for h in row] for row in heights]
    if info is not None:
        info.update(cycles=0, residual_m=0.0, converged=True)
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
    cycles, converged, w = 0, False, _w_cycle_ok(levels)
    for _ in range(vcycle_cap(nx, ny)):
        cycles += 1
        if _vcycle(levels, 0, U, None, w) < VCYCLE_TOLERANCE_M:
            converged = True
            break
    if info is not None:
        info.update(cycles=cycles, residual_m=_restricted_residual(U, None, levels[0], None)[1],
                    converged=converged)
    K = levels[0].known
    for j, lo, hi in levels[0].spans:
        U[j][lo:hi + 1] = [v if f else min(max(v, lo_v), hi_v) for v, f in zip(U[j][lo:hi + 1], K[j][lo:hi + 1])]
    return [U[j][1:nx + 1] for j in range(1, ny + 1)]


def correct_grid(grid, mask, passes=FINE_PASSES, min_unmasked_fraction=MIN_UNMASKED_FRACTION):
    """(corrected ElevationGrid or None, stats dict) for a :class:`MaskRaster` ``mask`` over ``grid``.

    Returns None (and ``stats['skipped']``) when no point is masked, fewer than ``min_unmasked_fraction``
    of the points are unmasked, or the fill did not converge within its bounded work (a fill that has not
    converged is never applied). ``stats`` has ``masked_points``, ``lowered_points`` (masked points whose
    corrected height is below the original), ``max_lowering_m``, ``mean_lowering_m`` (over the masked
    points) and, once the fill ran, ``fill_cycles``, ``fill_residual_m`` and ``fill_converged``.
    Raises NoDataError for any non-finite height: NoData is never filled."""
    nx, ny = grid.nx, grid.ny
    total = nx * ny
    for row in grid.heights:
        for h in row:
            if not math.isfinite(h):
                raise NoDataError("elevation grid contains NoData; the DSM correction never fills NoData")
    m = mask.mask if isinstance(mask, MaskRaster) else mask
    masked = sum(m)
    stats = {"masked_points": masked, "lowered_points": 0, "total_points": total, "max_lowering_m": 0.0,
             "mean_lowering_m": 0.0}
    if masked == 0:
        stats["skipped"] = "nothing to mask"
        return None, stats
    if total - masked < min_unmasked_fraction * total:
        stats["skipped"] = "too few unmasked points"
        return None, stats
    info = {}
    filled = fill_masked(grid.heights, m, nx, ny, passes, info=info)
    stats.update(fill_cycles=info["cycles"], fill_residual_m=round(info["residual_m"], 4),
                 fill_converged=info["converged"])
    if not info["converged"]:
        stats["skipped"] = "fill did not converge"
        return None, stats
    out = [list(row) for row in grid.heights]
    lower_sum = lower_max = 0.0
    lowered = 0
    for j in range(ny):
        base = j * nx
        orow, frow, crow = grid.heights[j], filled[j], out[j]
        for i in range(nx):
            if m[base + i] and frow[i] < orow[i]:
                crow[i] = frow[i]
                lowered += 1
                d = orow[i] - frow[i]
                lower_sum += d
                if d > lower_max:
                    lower_max = d
    stats["lowered_points"] = lowered
    stats["max_lowering_m"] = round(lower_max, 3)
    stats["mean_lowering_m"] = round(lower_sum / masked, 3)
    return ElevationGrid(grid.x0, grid.y0, grid.spacing, nx, ny, out, grid.provenance), stats


def apply_correction(grid, requested, buildings=(), trees=(), forests=(), bridges=(), excluded_invalid=None,
                     work_budget=MASK_WORK_BUDGET):
    """(grid to use, report entry, warning or None). ``requested``: the ``dsm_correction`` setting.

    The report entry is ``{applied, enabled, setting, masked_points, lowered_points, total_points,
    max_lowering_m, mean_lowering_m, reason, ...}`` plus ``fill_cycles``, ``fill_residual_m`` and
    ``fill_converged`` once the fill ran; when the correction is not applied the input grid is returned.
    ``excluded_invalid`` (optional dict) counts mask features dropped for invalid geometry.

    Work limits never fail the build: when the mask rasterisation would exceed ``work_budget`` or the fill
    does not converge within its bounded cycles, the correction is skipped with a warning and the
    uncorrected surface model is used (like the "too few unmasked points" skip)."""
    enabled, reason = resolve(requested, grid.provenance)
    entry = {"applied": False, "enabled": enabled,
             "setting": {None: "auto", True: "on", False: "off"}[requested],
             "masked_points": 0, "lowered_points": 0, "total_points": grid.nx * grid.ny, "max_lowering_m": 0.0,
             "mean_lowering_m": 0.0, "reason": reason}
    if not enabled:
        return grid, entry, None
    entry["mask"] = {"building_buffer_m": BUILDING_BUFFER_M, "tree_radius_m": TREE_RADIUS_M,
                     "bridge_buffer_m": f"deck width / 2 + {BRIDGE_BUFFER_M:g}", "forest": "inside landcover",
                     "features": {"buildings": len(buildings), "trees": len(trees), "forest_areas": len(forests),
                                  "bridges": len(bridges)}}
    if excluded_invalid:
        entry["mask"]["excluded_invalid"] = dict(excluded_invalid)
    entry["method"] = ("harmonic (Laplace, 5-point) interpolation of the masked points from the unmasked ones, "
                       "solved coarse to fine (multigrid: nested-iteration initial guess from coarsened levels "
                       "- 2 x 2 blocks, semi-coarsening along the long axis of elongated grids - then a bounded "
                       "number of V- or W-cycles of red-black Gauss-Seidel until the largest update is below "
                       f"{VCYCLE_TOLERANCE_M:g} m; skipped if not converged), min(original, filled)")
    try:
        mask = build_mask(grid, buildings, trees, forests, bridges, work_budget=work_budget)
    except LimitError as exc:
        entry["reason"] = "mask rasterisation work budget exceeded"
        return grid, entry, (f"DSM terrain correction skipped: {exc}; the terrain is the uncorrected "
                             "surface model")
    entry["mask"]["rasterisation_work"] = mask.work
    corrected, stats = correct_grid(grid, mask)
    entry.update({k: v for k, v in stats.items() if k != "skipped"})
    warning = None
    if corrected is None:
        entry["reason"] = stats["skipped"]
        if stats["skipped"] == "too few unmasked points":
            warning = (f"DSM terrain correction skipped: only {grid.nx * grid.ny - stats['masked_points']} of "
                       f"{grid.nx * grid.ny} terrain points are outside buildings/trees/forest/bridges (needs at "
                       f"least {MIN_UNMASKED_FRACTION:.0%}); the terrain is the uncorrected surface model")
        elif stats["skipped"] == "fill did not converge":
            warning = (f"DSM terrain correction skipped: the ground fill did not converge within "
                       f"{stats['fill_cycles']} cycles (largest update {stats['fill_residual_m']:g} m, tolerance "
                       f"{VCYCLE_TOLERANCE_M:g} m); the terrain is the uncorrected surface model")
        return grid, entry, warning
    entry["applied"] = True
    return corrected, entry, warning