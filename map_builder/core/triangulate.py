"""Polygon triangulation with holes (ear clipping + hole bridging).

Works on indices into a shared 2-D point list so callers keep vertex identity.
Outer ring must be CCW, holes CW (see :class:`osm.Polygon`). Output triangles
are CCW (normal +Z in the right-handed map frame).
"""

from .errors import MapBuilderError


class TriangulationError(MapBuilderError):
    pass


def _cross(o, a, b):
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _in_tri(p, a, b, c):
    eps = 1e-12
    return (_cross(a, b, p) >= -eps and _cross(b, c, p) >= -eps and _cross(c, a, p) >= -eps)


def _seg_intersect(p1, p2, p3, p4):
    d1, d2 = _cross(p3, p4, p1), _cross(p3, p4, p2)
    d3, d4 = _cross(p1, p2, p3), _cross(p1, p2, p4)
    return d1 * d2 < 0 and d3 * d4 < 0


def _bridge_hole(poly, hole, pts):
    """Splice hole (list of indices) into poly with a mutually visible bridge."""
    m_i = max(range(len(hole)), key=lambda k: (pts[hole[k]][0], -pts[hole[k]][1]))
    m = pts[hole[m_i]]
    edges = [(poly[k], poly[(k + 1) % len(poly)]) for k in range(len(poly))]
    # candidates sorted by distance; take the closest polygon vertex whose
    # connecting segment does not cross any polygon/hole edge.
    hole_edges = [(hole[k], hole[(k + 1) % len(hole)]) for k in range(len(hole))]
    order = sorted(range(len(poly)), key=lambda k: ((pts[poly[k]][0] - m[0]) ** 2 + (pts[poly[k]][1] - m[1]) ** 2))
    chosen = None
    for k in order:
        p = pts[poly[k]]
        ok = True
        for a, b in edges + hole_edges:
            if poly[k] in (a, b) or hole[m_i] in (a, b):
                continue
            if _seg_intersect(m, p, pts[a], pts[b]):
                ok = False
                break
        if ok:
            # bridge must leave poly vertex into the interior: check against the vertex wedge
            prev = pts[poly[k - 1]]
            nxt = pts[poly[(k + 1) % len(poly)]]
            if _cross(prev, p, nxt) >= 0:  # convex vertex: m must lie inside the wedge
                if not (_cross(prev, p, m) >= -1e-12 and _cross(p, nxt, m) >= -1e-12):
                    continue
            else:  # reflex vertex: m must not lie in the exterior wedge
                if _cross(prev, p, m) < 0 and _cross(p, nxt, m) < 0:
                    continue
            chosen = k
            break
    if chosen is None:
        raise TriangulationError("could not bridge hole to outer ring")
    rot = hole[m_i:] + hole[:m_i]
    return poly[:chosen + 1] + rot + [rot[0], poly[chosen]] + poly[chosen + 1:]


def triangulate(pts, outer, holes=()):
    """pts: list of (x, y); outer/holes: lists of indices. Returns [(i, j, k)]."""
    if len(outer) < 3:
        raise TriangulationError("ring has fewer than 3 vertices")
    poly = list(outer)
    for hole in sorted(holes, key=lambda h: -max(pts[i][0] for i in h)):
        if len(hole) >= 3:
            poly = _bridge_hole(poly, list(hole), pts)
    tris = []
    n_guard = 0
    while len(poly) > 3:
        n = len(poly)
        n_guard += 1
        if n_guard > 4 * len(pts) * len(pts) + 100:
            raise TriangulationError("ear clipping did not converge")
        ear = None
        for k in range(n):
            ia, ib, ic = poly[k - 1], poly[k], poly[(k + 1) % n]
            a, b, c = pts[ia], pts[ib], pts[ic]
            if _cross(a, b, c) <= 1e-12:
                continue
            blocked = False
            for q in poly:
                if q in (ia, ib, ic):
                    continue
                pq = pts[q]
                if pq == a or pq == b or pq == c:
                    continue
                if _in_tri(pq, a, b, c):
                    blocked = True
                    break
            if not blocked:
                ear = k
                break
        if ear is None:
            # Degenerate leftovers (collinear runs): drop a zero-area vertex if any.
            for k in range(n):
                if abs(_cross(pts[poly[k - 1]], pts[poly[k]], pts[poly[(k + 1) % n]])) <= 1e-12:
                    poly.pop(k)
                    break
            else:
                raise TriangulationError("no ear found (self-intersecting or degenerate polygon)")
            continue
        tris.append((poly[ear - 1], poly[ear], poly[(ear + 1) % n]))
        poly.pop(ear)
    a, b, c = (pts[i] for i in poly)
    if _cross(a, b, c) > 1e-12:
        tris.append(tuple(poly))
    return tris
