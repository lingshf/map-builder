"""Geodesy, map frame and axis conventions.

Map frame ("local ENU")
-----------------------
* Right-handed Cartesian frame in metres. +X = east, +Y = north, +Z = up.
* Horizontal (x, y) of a geographic point is the orthographic projection of
  that point *on the WGS84 ellipsoid* onto the tangent plane at the origin,
  i.e. the east/north components of its ECEF->ENU transform at h=0.
* z = H - z_offset, where H is the height above the declared vertical datum
  (e.g. EGM2008 orthometric height for Copernicus DEM) and ``z_offset`` is a
  per-map constant recorded in the manifest. Earth curvature is NOT applied to
  z (planar map); at 1 km from the origin the drop would be ~8 cm.

Axis conventions (all exact, no scaling)
----------------------------------------
* Blender world == map frame (Blender is Z-up right-handed).
* glTF 2.0 (Y-up, right-handed, as written by Blender's exporter with
  "+Y Up"): gltf = (x, z, -y)       ->  map = (gx, -gz, gy)
* Unity (left-handed, Y-up) after a glTF importer that negates X (glTFast and
  UnityGLTF both document this): unity = (-gx, gy, gz) = (-x, z, -y)
  -> map = (-ux, -uz, uy). Triangle winding flips with the handedness change.
  Consumers must verify with the manifest's orientation probes.
"""

import math

from .errors import AreaError

WGS84_A = 6378137.0
WGS84_F = 1.0 / 298.257223563
WGS84_E2 = WGS84_F * (2.0 - WGS84_F)


def geodetic_to_ecef(lat_deg, lon_deg, h=0.0):
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    s, c = math.sin(lat), math.cos(lat)
    n = WGS84_A / math.sqrt(1.0 - WGS84_E2 * s * s)
    return ((n + h) * c * math.cos(lon), (n + h) * c * math.sin(lon), (n * (1.0 - WGS84_E2) + h) * s)


class LocalFrame:
    """Planar map frame anchored at a WGS84 origin."""

    def __init__(self, lat0, lon0, z_offset=0.0):
        if not (-85.0 <= lat0 <= 85.0) or not (-180.0 <= lon0 <= 180.0):
            raise AreaError("origin latitude must be within +-85 deg and longitude within +-180 deg")
        self.lat0 = float(lat0)
        self.lon0 = float(lon0)
        self.z_offset = float(z_offset)
        self._o = geodetic_to_ecef(lat0, lon0, 0.0)
        p, l = math.radians(lat0), math.radians(lon0)
        self._sp, self._cp, self._sl, self._cl = math.sin(p), math.cos(p), math.sin(l), math.cos(l)

    def to_local(self, lat, lon):
        x, y, z = geodetic_to_ecef(lat, lon, 0.0)
        dx, dy, dz = x - self._o[0], y - self._o[1], z - self._o[2]
        e = -self._sl * dx + self._cl * dy
        n = -self._sp * self._cl * dx - self._sp * self._sl * dy + self._cp * dz
        return e, n

    def to_geographic(self, x, y):
        """Inverse of :meth:`to_local` (Newton iteration, sub-mm converged)."""
        m_lat = 111132.954  # rough metres/deg, only for the initial guess
        lat = self.lat0 + y / m_lat
        lon = self.lon0 + x / (m_lat * max(math.cos(math.radians(self.lat0)), 1e-6))
        for _ in range(8):
            e, n = self.to_local(lat, lon)
            d = 1e-6
            e_la, n_la = self.to_local(lat + d, lon)
            e_lo, n_lo = self.to_local(lat, lon + d)
            j11, j12 = (e_la - e) / d, (e_lo - e) / d
            j21, j22 = (n_la - n) / d, (n_lo - n) / d
            det = j11 * j22 - j12 * j21
            rx, ry = x - e, y - n
            dlat = (j22 * rx - j12 * ry) / det
            dlon = (-j21 * rx + j11 * ry) / det
            lat += dlat
            lon += dlon
            if abs(dlat) < 1e-12 and abs(dlon) < 1e-12:
                break
        return lat, lon

    def to_dict(self):
        return {"lat": self.lat0, "lon": self.lon0, "z_offset_m": self.z_offset}


# --- UTM (WGS84) forward projection, Krueger n-series (mm accuracy in zone) --

def utm_forward(lat_deg, lon_deg, zone, south):
    a, f = WGS84_A, WGS84_F
    k0 = 0.9996
    n = f / (2.0 - f)
    big_a = a / (1.0 + n) * (1.0 + n * n / 4.0 + n ** 4 / 64.0)
    alpha = (n / 2.0 - 2.0 * n * n / 3.0 + 5.0 * n ** 3 / 16.0,
             13.0 * n * n / 48.0 - 3.0 * n ** 3 / 5.0,
             61.0 * n ** 3 / 240.0)
    lat = math.radians(lat_deg)
    lon0 = math.radians(zone * 6 - 183)
    dl = math.radians(lon_deg) - lon0
    c = 2.0 * math.sqrt(n) / (1.0 + n)
    t = math.sinh(math.atanh(math.sin(lat)) - c * math.atanh(c * math.sin(lat)))
    xi = math.atan2(t, math.cos(dl))
    eta = math.atanh(math.sin(dl) / math.sqrt(1.0 + t * t))
    e = eta
    nn = xi
    for j, aj in enumerate(alpha, start=1):
        e += aj * math.cos(2 * j * xi) * math.sinh(2 * j * eta)
        nn += aj * math.sin(2 * j * xi) * math.cosh(2 * j * eta)
    easting = 500000.0 + k0 * big_a * e
    northing = (10000000.0 if south else 0.0) + k0 * big_a * nn
    return easting, northing


# --- Axis conversions ------------------------------------------------------

def map_to_gltf(p):
    x, y, z = p
    return (x, z, -y)


def gltf_to_map(p):
    gx, gy, gz = p
    return (gx, -gz, gy)


def map_to_unity_x_negated(p):
    x, y, z = p
    return (-x, z, -y)


def unity_x_negated_to_map(p):
    ux, uy, uz = p
    return (-ux, -uz, uy)


# --- Area ------------------------------------------------------------------

DEFAULT_MAX_SIDE_M = 2000.0
HARD_MAX_SIDE_M = 5000.0
MIN_SIDE_M = 50.0
MAX_ABS_LAT = 84.0          # UTM validity; DEM reprojection relies on it
MAX_BBOX_SPAN_DEG = 0.2     # far beyond the 5 km cap; rejects inputs the local projection would fold
ANTIMERIDIAN_GUARD_M = 1000.0  # covers every acquisition margin used by the data sources


class Area:
    """Axis-aligned rectangle in the map frame centred on the origin."""

    def __init__(self, lat, lon, width_m, height_m, max_side_m=DEFAULT_MAX_SIDE_M):
        try:
            max_side_m = float(max_side_m)
        except (TypeError, ValueError):
            raise AreaError("max_side_m must be a number") from None
        if not (math.isfinite(max_side_m) and max_side_m >= MIN_SIDE_M):
            raise AreaError(f"max_side_m must be finite and >= {MIN_SIDE_M:.0f} m")
        max_side_m = min(max_side_m, HARD_MAX_SIDE_M)
        for name, v in (("width", width_m), ("height", height_m)):
            if not (isinstance(v, (int, float)) and math.isfinite(v)):
                raise AreaError(f"area {name} must be a finite number")
            if v < MIN_SIDE_M:
                raise AreaError(f"area {name} {v:.0f} m is below the minimum {MIN_SIDE_M:.0f} m")
            if v > max_side_m:
                raise AreaError(f"area {name} {v:.0f} m exceeds the limit {max_side_m:.0f} m")
        if not (isinstance(lat, (int, float)) and isinstance(lon, (int, float))
                and math.isfinite(lat) and math.isfinite(lon)):
            raise AreaError("area centre must be finite")
        if not (-MAX_ABS_LAT <= lat <= MAX_ABS_LAT and -180.0 <= lon <= 180.0):
            raise AreaError(f"area centre must have |lat| <= {MAX_ABS_LAT} and -180 <= lon <= 180")
        self.frame = LocalFrame(lat, lon)
        self.width = float(width_m)
        self.height = float(height_m)
        self.geographic_bbox(margin_m=ANTIMERIDIAN_GUARD_M)  # raises if the area nears the antimeridian
        s, _, n, _ = self.geographic_bbox()
        if s < -MAX_ABS_LAT or n > MAX_ABS_LAT:
            raise AreaError(f"area footprint must stay within |lat| <= {MAX_ABS_LAT}")

    @classmethod
    def from_bbox(cls, south, west, north, east, max_side_m=DEFAULT_MAX_SIDE_M):
        if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in (south, west, north, east)):
            raise AreaError("bbox values must be finite numbers")
        if not (south < north and west < east):
            raise AreaError("bbox must satisfy south < north and west < east (antimeridian crossing unsupported)")
        if not (-MAX_ABS_LAT <= south and north <= MAX_ABS_LAT and -180.0 <= west and east <= 180.0):
            raise AreaError(f"bbox must lie within |lat| <= {MAX_ABS_LAT} and -180 <= lon <= 180")
        if north - south > MAX_BBOX_SPAN_DEG or (east - west) * math.cos(math.radians(max(abs(south), abs(north)))) \
                > MAX_BBOX_SPAN_DEG:
            raise AreaError(f"bbox spans more than {MAX_BBOX_SPAN_DEG} degrees; map areas are local (<= "
                            f"{HARD_MAX_SIDE_M:.0f} m)")
        lat, lon = (south + north) / 2.0, (west + east) / 2.0
        f = LocalFrame(lat, lon)
        # Smallest centred rectangle enclosing the corners and edge midpoints of the request.
        pts = [f.to_local(la, lo) for la in (south, lat, north) for lo in (west, lon, east)]
        half_w = max(abs(p[0]) for p in pts)
        half_h = max(abs(p[1]) for p in pts)
        return cls(lat, lon, 2.0 * half_w, 2.0 * half_h, max_side_m)

    @property
    def half(self):
        return self.width / 2.0, self.height / 2.0

    def contains(self, x, y):
        hx, hy = self.half
        return -hx <= x <= hx and -hy <= y <= hy

    def geographic_bbox(self, margin_m=0.0):
        """(south, west, north, east) enclosing the rectangle plus margin."""
        hx, hy = self.half
        hx += margin_m
        hy += margin_m
        pts = [self.frame.to_geographic(sx * hx, sy * hy) for sx in (-1, 0, 1) for sy in (-1, 0, 1)]
        lats = [p[0] for p in pts]
        lons = [p[1] for p in pts]
        s, w, n, e = min(lats), min(lons), max(lats), max(lons)
        if w < -180.0 or e > 180.0 or s < -90.0 or n > 90.0:
            raise AreaError("area (plus acquisition margin) crosses the antimeridian or a pole; unsupported")
        return s, w, n, e

    def to_dict(self):
        s, w, n, e = self.geographic_bbox()
        return {
            "width_m": self.width,
            "height_m": self.height,
            "local_rect_m": [-self.width / 2, -self.height / 2, self.width / 2, self.height / 2],
            "geographic_bbox_deg": {"south": s, "west": w, "north": n, "east": e},
        }
