"""Roof shapes of extruded building footprints.

``generate.build_building`` computes the eave and total heights (OSM semantics) and the wall
volume; this module decides which roof shape can be built on the footprint
(:func:`resolve_shape`, with ``fallback:`` provenance) and adds the roof faces
(:func:`build_roof`). It depends on nothing in ``generate``.
"""

import math

SUPPORTED_SHAPES = {"flat", "skillion", "pyramidal", "gabled", "hipped"}

PLANAR_TOL_M = 1e-6


def rect_check(ring):
    """Return True if ring is a near-rectangle (4 vertices, ~90 deg corners)."""
    if len(ring) != 4:
        return False
    for k in range(4):
        a, b, c = ring[k - 1], ring[k], ring[(k + 1) % 4]
        v1 = (a[0] - b[0], a[1] - b[1])
        v2 = (c[0] - b[0], c[1] - b[1])
        n1, n2 = math.hypot(*v1), math.hypot(*v2)
        if n1 < 0.5 or n2 < 0.5:
            return False
        if abs((v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)) > math.sin(math.radians(15)):
            return False
    return True


def is_convex(ring):
    n = len(ring)
    for k in range(n):
        a, b, c = ring[k - 1], ring[k], ring[(k + 1) % n]
        if (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]) < -1e-9:
            return False
    return True


def add_planar_face(mesh, idx, mat, col, tol=PLANAR_TOL_M):
    """Add face ``idx``; a polygon with > 3 vertices that is not planar within ``tol`` metres
    is added as explicit triangles instead (a quad along its shorter diagonal, otherwise a
    fan), keeping the winding. Returns True if the face was split."""
    if len(idx) > 3:
        V = [mesh.vertices[i] for i in idx]
        n = len(V)
        nx_ = sum((V[k][1] - V[(k + 1) % n][1]) * (V[k][2] + V[(k + 1) % n][2]) for k in range(n))
        ny_ = sum((V[k][2] - V[(k + 1) % n][2]) * (V[k][0] + V[(k + 1) % n][0]) for k in range(n))
        nz_ = sum((V[k][0] - V[(k + 1) % n][0]) * (V[k][1] + V[(k + 1) % n][1]) for k in range(n))
        ln = math.sqrt(nx_ * nx_ + ny_ * ny_ + nz_ * nz_)
        c = [sum(v[d] for v in V) / n for d in range(3)]
        if ln <= 1e-12 or max(abs((v[0] - c[0]) * nx_ + (v[1] - c[1]) * ny_ + (v[2] - c[2]) * nz_) / ln
                              for v in V) > tol:
            if n == 4 and math.dist(V[1], V[3]) < math.dist(V[0], V[2]):
                tris = [(idx[1], idx[2], idx[3]), (idx[1], idx[3], idx[0])]
            else:
                tris = [(idx[0], idx[k], idx[k + 1]) for k in range(1, n - 1)]
            for t in tris:
                mesh.add_face(t, mat, col)
            return True
    mesh.add_face(idx, mat, col)
    return False


def resolve_shape(shape_tag, outer, holes, prov):
    """The roof shape that can be built for ``roof:shape`` on this footprint; sets
    ``prov["roof_shape"]`` (``measured:``/``inferred:``/``fallback:``)."""
    shape = shape_tag or "flat"
    prov["roof_shape"] = "measured:osm roof:shape" if shape_tag else "inferred:flat"
    if shape not in SUPPORTED_SHAPES:
        prov["roof_shape"] = f"fallback:flat (roof:shape={shape} not modelled in v1)"
        shape = "flat"
    if holes and shape not in ("flat", "skillion"):
        prov["roof_shape"] = f"fallback:flat (roof:shape={shape} with courtyard)"
        shape = "flat"
    if shape in ("gabled", "hipped") and not rect_check(outer):
        if is_convex(outer):
            prov["roof_shape"] = f"fallback:pyramidal (roof:shape={shape} on non-rectangular footprint)"
            shape = "pyramidal"
        else:
            prov["roof_shape"] = f"fallback:flat (roof:shape={shape} on non-rectangular footprint)"
            shape = "flat"
    if shape == "pyramidal" and not is_convex(outer):
        prov["roof_shape"] = "fallback:flat (pyramidal roof on concave footprint)"
        shape = "flat"
    return shape


def resolve_orientation(shape, tags, prov):
    """True if the ridge runs across (parallel to the shorter side); sets
    ``prov["roof_orientation"]``."""
    across = False
    orient_tag = tags.get("roof:orientation")
    if shape in ("gabled", "hipped"):
        if orient_tag in ("along", "across"):
            prov["roof_orientation"] = f"measured:osm roof:orientation={orient_tag}"
            across = orient_tag == "across"
        elif orient_tag is None:
            prov["roof_orientation"] = "inferred:along (ridge parallel to the longer side)"
        else:
            prov["roof_orientation"] = f"fallback:along (roof:orientation={orient_tag} not recognised)"
    elif orient_tag is not None:
        prov["roof_orientation"] = f"ignored:roof:orientation={orient_tag} (roof built {shape})"
    return across


def skillion_surface(shape, rings, direction, top, roof_h, prov):
    """For a skillion roof, a function (x, y) -> roof underside z; else None. ``direction`` is the parsed\n    ``roof:direction`` in degrees (None if absent)."""
    if shape != "skillion":
        return None
    if direction is None:
        prov["roof_direction"] = "inferred:0 (north-facing slope)"
        direction = 0.0
    direction %= 360.0
    d = (math.sin(math.radians(direction)), math.cos(math.radians(direction)))
    proj = [p[0] * d[0] + p[1] * d[1] for r in rings for p in r]
    smin, smax = min(proj), max(proj)
    span = max(smax - smin, 1e-6)

    def skillion_z(p):
        s = p[0] * d[0] + p[1] * d[1]
        return top - roof_h * (s - smin) / span
    return skillion_z


def build_roof(mesh, ring, holes, eave_z, roof_h, shape, tags, prov, *, top_idx, tris, add_face,
               roof_col, facade, across=False):
    """Add the roof faces of ``shape`` on the wall-top vertices ``top_idx`` (one index list
    per ring, outer first, in the mesh's local frame). ``ring``/``holes`` are the local
    footprint rings, the wall tops are at ``eave_z`` (sloped for a skillion), the highest
    point is ``eave_z + roof_h``. ``tris`` triangulates the footprint over the flattened
    ``top_idx``; ``add_face(idx, material, colour)`` adds (and counts split) faces."""
    top = eave_z + roof_h
    flat_top = [i for rt in top_idx for i in rt]
    if shape in ("flat", "skillion"):
        for (a, b, c) in tris:
            add_face((flat_top[a], flat_top[b], flat_top[c]), "MB Roof", roof_col)
    elif shape == "pyramidal":
        apex = mesh.add_vertex(0.0, 0.0, top)
        rt = top_idx[0]
        for k in range(len(rt)):
            add_face((rt[k], rt[(k + 1) % len(rt)], apex), "MB Roof", roof_col)
    else:  # gabled / hipped on rectangle a,b,c,d (CCW); ridge runs parallel to a-b
        rt = top_idx[0]
        V = mesh.vertices
        a, b, c, d = rt
        # along: a-b is a long side (ridge along the long axis); across: a-b is a short side.
        if (math.dist(V[a][:2], V[b][:2]) < math.dist(V[b][:2], V[c][:2])) != across:
            a, b, c, d = b, c, d, a
        m1 = tuple((V[b][i] + V[c][i]) / 2 for i in range(2))
        m2 = tuple((V[d][i] + V[a][i]) / 2 for i in range(2))
        if shape == "hipped":
            end = math.dist(V[b][:2], V[c][:2])
            ridge_span = math.dist(m1, m2)
            t = min(0.5 * end / max(ridge_span, 1e-6), 0.49)
            r1 = (m1[0] + (m2[0] - m1[0]) * t, m1[1] + (m2[1] - m1[1]) * t)
            r2 = (m2[0] + (m1[0] - m2[0]) * t, m2[1] + (m1[1] - m2[1]) * t)
        else:
            r1, r2 = m1, m2
        R1 = mesh.add_vertex(r1[0], r1[1], top)
        R2 = mesh.add_vertex(r2[0], r2[1], top)
        add_face((a, b, R1, R2), "MB Roof", roof_col)
        add_face((c, d, R2, R1), "MB Roof", roof_col)
        end_mat, end_col = ("MB Roof", roof_col) if shape == "hipped" else ("MB Facade", facade)
        add_face((b, c, R1), end_mat, end_col)
        add_face((d, a, R2), end_mat, end_col)
