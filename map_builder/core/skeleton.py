"""Straight skeleton of a simple polygon without holes (D55).

Pure geometry: no Blender, no OSM types. ``straight_skeleton(ring)`` returns one planar face per
footprint edge; every skeleton node carries its offset distance ``t`` (the roof height of a
45-degree-per-metre roof is simply ``z = t``).

Algorithm: an event-driven wavefront. Every wavefront edge moves inwards with unit speed; every
wavefront vertex moves along the bisector of its two edges. The earliest of two event kinds is
processed until the wavefront has vanished:

* edge event: two neighbouring vertices meet (their edge shrank to zero length);
* split event: a reflex vertex runs into a wavefront edge of its own cycle and splits it.

After each event a new vertex can have two antiparallel edges (a zero-width spike); such spikes
are resolved immediately into a ridge. Events whose times differ by less than ``EVENT_TOL`` are
processed in a fixed order, and nodes closer than ``POINT_TOL_M`` (at the same ``t``) are merged,
so simultaneous events (symmetric shapes) produce a single multi-way node. Both constants equal
``PLANAR_TOL_M`` of ``roofs.py`` (not imported, to keep this module free of cycles).

Bounds: at most ``MAX_SKELETON_VERTICES`` vertices after merging collinear runs, and at most
``MAX_SKELETON_EVENTS`` processed events (edge, split and every spike-resolution step; a simple polygon needs
fewer than 4 n of them). Finding the next event is O(n^2), so the whole run is O(n^3) with an O(n^2)
event cap and never depends on wall-clock time. Exceeding the cap raises :class:`LimitError`.

Output is canonical: the ring is made counter-clockwise and rotated to start at its lexicographically
smallest vertex, so the same polygon rotated or reversed gives identical output. Faces are listed
in ring-edge order (face ``i`` belongs to ``ring[i] -> ring[i + 1]``), counter-clockwise seen from
above, starting at ``ring[i]``. Nodes ``0 .. len(ring) - 1`` are the ring vertices (``t = 0``).

The result is verified before it is returned (planarity at ``z = t`` and total face area); an
inconsistent result raises :class:`SkeletonError` instead of being returned.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from .errors import LimitError, MapBuilderError
from .triangulate import TriangulationError, validate_rings

MAX_SKELETON_VERTICES = 64
MAX_SKELETON_EVENTS = MAX_SKELETON_VERTICES ** 2
Pt = tuple[float, float]
Node = tuple[float, float, float]  # (x, y, t)
Edge = tuple[float, float, float, float, float]  # (dx, dy, nx, ny, c)
Seg = tuple[int, int]  # directed node pair
_Event = tuple[float, int, int, int, "_V", "_V"]  # (time, kind 0 edge / 1 split, uid, uid, vertex, partner)

POINT_TOL_M = 1e-6
EVENT_TOL = 1e-9
_PARALLEL = 1e-9


class SkeletonError(MapBuilderError):
    """The polygon is unsupported by the straight skeleton (reason in the message)."""


@dataclass
class Skeleton:
    ring: list[Pt]  # canonical ring (CCW, collinear runs merged)
    nodes: list[Node]  # the first len(ring) nodes are the ring vertices
    faces: list[list[int]]  # one list of node ids per ring edge
    events: int  # processed events (the bounded work counter)

    def face_points(self, i: int) -> list[Node]:
        return [self.nodes[k] for k in self.faces[i]]


class _V:
    __slots__ = ("p0", "tv", "vel", "prev", "next", "ep", "en", "node", "alive", "uid")

    p0: Pt
    tv: float
    vel: Pt
    prev: _V
    next: _V
    ep: int
    en: int
    node: int
    alive: bool
    uid: int

    def __init__(self, p0: Pt, tv: float, vel: Pt, ep: int, en: int, node: int, uid: int) -> None:
        self.p0, self.tv, self.vel, self.ep, self.en, self.node, self.uid = p0, tv, vel, ep, en, node, uid
        self.prev = self.next = None  # type: ignore[assignment]  # linked by the caller right after construction
        self.alive = True

    def at(self, t: float) -> Pt:
        d = t - self.tv
        return (self.p0[0] + self.vel[0] * d, self.p0[1] + self.vel[1] * d)


def _signed_area(pts: Sequence[Sequence[float]]) -> float:
    return sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1]
               for i in range(len(pts))) / 2.0


def _canonical_ring(ring: Iterable[Sequence[float]]) -> list[Pt]:
    pts: list[Pt] =  [(float(p[0]), float(p[1])) for p in ring]
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts.pop()
    if any(not (math.isfinite(x) and math.isfinite(y)) for x, y in pts):
        raise SkeletonError("ring has non-finite coordinates")
    if len(pts) < 3:
        raise SkeletonError("ring has fewer than 3 vertices")
    n = len(pts)
    for k in range(n):
        if math.dist(pts[k], pts[(k + 1) % n]) < POINT_TOL_M:
            raise SkeletonError(f"zero-length edge at vertex {k} (shorter than {POINT_TOL_M} m)")
    changed = True
    while changed and len(pts) > 3:
        changed = False
        for k in range(len(pts)):
            a, b, c = pts[k - 1], pts[k], pts[(k + 1) % len(pts)]
            ac = math.dist(a, c)
            if ac < POINT_TOL_M:
                raise SkeletonError("ring folds back on itself (zero-width spike)")
            dev = abs((c[0] - a[0]) * (b[1] - a[1]) - (c[1] - a[1]) * (b[0] - a[0])) / ac
            if dev <= POINT_TOL_M:
                if (b[0] - a[0]) * (c[0] - b[0]) + (b[1] - a[1]) * (c[1] - b[1]) < 0:
                    raise SkeletonError("ring folds back on itself (zero-width spike)")
                del pts[k]
                changed = True
                break
    if len(pts) > MAX_SKELETON_VERTICES:
        raise SkeletonError(f"{len(pts)} vertices exceed the limit of {MAX_SKELETON_VERTICES}")
    try:
        validate_rings(pts, list(range(len(pts))) if _signed_area(pts) > 0 else list(range(len(pts)))[::-1])
    except TriangulationError as exc:
        raise SkeletonError(f"unsupported ring: {exc}") from exc
    if _signed_area(pts) < 0:
        pts.reverse()
    start = min(range(len(pts)), key=lambda k: pts[k])
    return pts[start:] + pts[:start]


class _Run:
    def __init__(self, ring: list[Pt]) -> None:
        self.ring = ring
        m = len(ring)
        self.nodes: list[Node] = [(x, y, 0.0) for x, y in ring]
        self.edges: list[Edge] = []
        for i in range(m):
            a, b = ring[i], ring[(i + 1) % m]
            ln = math.dist(a, b)
            dx, dy = (b[0] - a[0]) / ln, (b[1] - a[1]) / ln
            nx, ny = -dy, dx
            self.edges.append((dx, dy, nx, ny, nx * a[0] + ny * a[1]))
        self.segs: list[list[Seg]] = [[] for _ in range(m)]  # directed node pairs per face (excluding the ring edge)
        self.events = 0
        self.uid = 0
        self.verts: list[_V] = []
        self.now = 0.0

    # -- nodes and vertices -------------------------------------------------
    def node(self, p: Pt, t: float) -> int:
        for k in range(len(self.ring), len(self.nodes)):
            x, y, tt = self.nodes[k]
            if abs(tt - t) <= POINT_TOL_M and abs(x - p[0]) <= POINT_TOL_M and abs(y - p[1]) <= POINT_TOL_M:
                return k
        self.nodes.append((p[0], p[1], t))
        return len(self.nodes) - 1

    def velocity(self, ep: int, en: int) -> Pt:
        _, _, n1x, n1y, _ = self.edges[ep]
        _, _, n2x, n2y, _ = self.edges[en]
        det = n1x * n2y - n1y * n2x
        if abs(det) < _PARALLEL:
            if n1x * n2x + n1y * n2y > 0:
                return (n1x, n1y)
            raise SkeletonError("internal: antiparallel vertex")
        return ((n2y - n1y) / det, (n1x - n2x) / det)

    def antiparallel(self, ep: int, en: int) -> bool:
        e1, e2 = self.edges[ep], self.edges[en]
        return abs(e1[0] * e2[1] - e1[1] * e2[0]) < _PARALLEL and e1[0] * e2[0] + e1[1] * e2[1] < 0

    def new_vertex(self, p: Pt, t: float, ep: int, en: int, node: int) -> _V:
        vel = (0.0, 0.0) if self.antiparallel(ep, en) else self.velocity(ep, en)
        v = _V(p, t, vel, ep, en, node, self.uid)
        self.uid += 1
        self.verts.append(v)
        return v

    def end_arc(self, v: _V, node: int) -> None:
        v.alive = False
        if node != v.node:
            self.segs[v.ep].append((v.node, node))
            self.segs[v.en].append((node, v.node))

    def ridge(self, u: int, w: int, e1: int, e2: int) -> None:
        if u != w:
            self.segs[e1].append((u, w))
            self.segs[e2].append((w, u))

    @staticmethod
    def cycle(v: _V) -> list[_V]:
        out, w = [v], v.next
        while w is not v:
            out.append(w)
            w = w.next
        return out

    # -- event search ---------------------------------------------------------
    def reflex(self, v: _V) -> bool:
        d1, d2 = self.edges[v.ep], self.edges[v.en]
        return d1[0] * d2[1] - d1[1] * d2[0] < -_PARALLEL

    def find_event(self, alive: Iterable[_V]) -> _Event | None:
        t0 = self.now
        best: _Event | None = None
        for v in alive:
            w = v.next
            dx, dy = self.edges[v.en][0], self.edges[v.en][1]
            pv, pw = v.at(t0), w.at(t0)
            g = (pw[0] - pv[0]) * dx + (pw[1] - pv[1]) * dy
            gv = (w.vel[0] - v.vel[0]) * dx + (w.vel[1] - v.vel[1]) * dy
            t: float | None = None
            if g <= POINT_TOL_M and gv <= POINT_TOL_M:
                t = t0
            elif gv < -1e-12:
                t = t0 + g / -gv
            if t is not None:
                best = self._better(best, (t, 0, v.uid, w.uid, v, w))
            if not self.reflex(v):
                continue
            for a in self.cycle(v):
                b = a.next
                if a is v or b is v:
                    continue
                dxe, dye, nx, ny, c = self.edges[a.en]
                p = v.at(t0)
                dist = nx * p[0] + ny * p[1] - c - t0
                rate = nx * v.vel[0] + ny * v.vel[1] - 1.0
                if dist < -POINT_TOL_M or rate >= -1e-12:
                    continue
                t = t0 + max(dist, 0.0) / -rate
                p = v.at(t)
                pa, pb = a.at(t), b.at(t)
                s = (p[0] - pa[0]) * dxe + (p[1] - pa[1]) * dye
                ln = (pb[0] - pa[0]) * dxe + (pb[1] - pa[1]) * dye
                if s < -POINT_TOL_M or s > ln + POINT_TOL_M:
                    continue
                best = self._better(best, (t, 1, v.uid, a.uid, v, a))
        return best

    @staticmethod
    def _better(cur: _Event | None, cand: _Event) -> _Event:
        if cur is None:
            return cand
        if cand[0] < cur[0] - EVENT_TOL:
            return cand
        if cand[0] > cur[0] + EVENT_TOL:
            return cur
        return cand if cand[1:4] < cur[1:4] else cur

    # -- event handling -------------------------------------------------------
    def charge(self) -> None:
        self.events += 1
        if self.events > MAX_SKELETON_EVENTS:
            raise LimitError(f"straight skeleton exceeded {MAX_SKELETON_EVENTS} events")

    def settle(self, x: _V, t: float) -> None:
        """Terminate or repair the cycle containing the fresh vertex ``x`` (spikes, size 2)."""
        while True:
            cyc = self.cycle(x)
            if len(cyc) <= 2:
                nodes = [self.node(v.at(t), t) for v in cyc]
                for v, nd in zip(cyc, nodes):
                    self.end_arc(v, nd)
                if len(cyc) == 2:
                    self.ridge(nodes[0], nodes[1], cyc[0].ep, cyc[0].en)
                return
            if not self.antiparallel(x.ep, x.en):
                return
            self.charge()
            p, q = x.prev, x.next
            px = x.at(t)
            dp, dq = math.dist(p.at(t), px), math.dist(q.at(t), px)
            nx_ = self.node(px, t)
            self.end_arc(x, nx_)
            if abs(dp - dq) <= POINT_TOL_M:
                nd = self.node(p.at(t), t)
                self.end_arc(p, nd)
                self.end_arc(q, nd)
                self.ridge(nx_, nd, x.ep, x.en)
                if len(cyc) == 3:
                    return
                y = self.new_vertex(p.at(t), t, p.ep, q.en, nd)
                y.prev, y.next = p.prev, q.next
            elif dp < dq:
                nd = self.node(p.at(t), t)
                self.end_arc(p, nd)
                self.ridge(nx_, nd, x.ep, x.en)
                y = self.new_vertex(p.at(t), t, p.ep, x.en, nd)
                y.prev, y.next = p.prev, q
            else:
                nd = self.node(q.at(t), t)
                self.end_arc(q, nd)
                self.ridge(nx_, nd, x.ep, x.en)
                y = self.new_vertex(q.at(t), t, x.ep, q.en, nd)
                y.prev, y.next = p, q.next
            y.prev.next = y
            y.next.prev = y
            x = y

    def edge_event(self, t: float, v: _V, w: _V) -> None:
        pv, pw = v.at(t), w.at(t)
        nd = self.node(((pv[0] + pw[0]) / 2.0, (pv[1] + pw[1]) / 2.0), t)
        self.end_arc(v, nd)
        self.end_arc(w, nd)
        x = self.new_vertex(self.nodes[nd][:2], t, v.ep, w.en, nd)
        x.prev, x.next = v.prev, w.next
        x.prev.next = x
        x.next.prev = x
        self.settle(x, t)

    def split_event(self, t: float, v: _V, a: _V) -> None:
        b = a.next
        p = v.at(t)
        nd = self.node(p, t)
        u, w = v.prev, v.next
        self.end_arc(v, nd)
        x1 = self.new_vertex(self.nodes[nd][:2], t, a.en, v.en, nd)
        x2 = self.new_vertex(self.nodes[nd][:2], t, v.ep, a.en, nd)
        a.next, x1.prev = x1, a
        x1.next, w.prev = w, x1
        u.next, x2.prev = x2, u
        x2.next, b.prev = b, x2
        self.settle(x1, t)
        self.settle(x2, t)

    def run(self) -> list[list[int]]:
        m = len(self.ring)
        first: list[_V] = []
        for i in range(m):
            ep, en = (i - 1) % m, i
            if self.antiparallel(ep, en):
                raise SkeletonError("ring folds back on itself (zero-width spike)")
            first.append(self.new_vertex(self.ring[i], 0.0, ep, en, i))
        for i, v in enumerate(first):
            v.prev, v.next = first[i - 1], first[(i + 1) % m]
        while True:
            alive = [v for v in self.verts if v.alive]
            if not alive:
                break
            ev = self.find_event(alive)
            if ev is None:
                raise SkeletonError("no skeleton event found (degenerate or numerically unstable ring)")
            self.charge()
            t = max(ev[0], self.now)
            self.now = t
            if ev[1] == 0:
                self.edge_event(t, ev[4], ev[5])
            else:
                self.split_event(t, ev[4], ev[5])
        return self.build_faces()

    # -- result ---------------------------------------------------------------
    def build_faces(self) -> list[list[int]]:
        m = len(self.ring)
        faces: list[list[int]] = []
        for i in range(m):
            nxt = {i: (i + 1) % m}
            for u, w in self.segs[i]:
                if u in nxt:
                    raise SkeletonError("internal: face boundary is not a simple cycle")
                nxt[u] = w
            face, k = [i], nxt[i]
            while k != i:
                if len(face) > len(nxt):
                    raise SkeletonError("internal: face boundary is not closed")
                face.append(k)
                step = nxt.get(k)
                if step is None:
                    raise SkeletonError("internal: face boundary is not closed")
                k = step
            if len(face) != len(nxt):
                raise SkeletonError("internal: face boundary is not a single cycle")
            faces.append(face)
        self.verify(faces)
        return faces

    def verify(self, faces: list[list[int]]) -> None:
        scale = max(1.0, max(abs(c) for p in self.ring for c in p))
        total = 0.0
        for i, face in enumerate(faces):
            _, _, nx, ny, c = self.edges[i]
            for k in face:
                x, y, t = self.nodes[k]
                if abs(nx * x + ny * y - c - t) > POINT_TOL_M * max(1.0, scale / 1000.0):
                    raise SkeletonError("internal: skeleton node is off its face plane")
            area = _signed_area([self.nodes[k][:2] for k in face])
            if area <= 0:
                raise SkeletonError("internal: degenerate or flipped skeleton face")
            total += area
        expect = _signed_area(self.ring)
        if abs(total - expect) > 1e-7 * expect:
            raise SkeletonError("internal: skeleton faces do not cover the footprint")


def straight_skeleton(ring: Iterable[Sequence[float]]) -> Skeleton:
    """Straight skeleton of the simple polygon ``ring`` ([(x, y), ...], either orientation).

    Collinear runs are merged first. Raises :class:`SkeletonError` for a self-touching or
    self-intersecting ring, an edge shorter than ``POINT_TOL_M``, a zero-width spike or more than
    ``MAX_SKELETON_VERTICES`` vertices, and :class:`LimitError` past ``MAX_SKELETON_EVENTS``.
    """
    canon = _canonical_ring(ring)
    run = _Run(canon)
    faces = run.run()
    return Skeleton(canon, run.nodes, faces, run.events)
