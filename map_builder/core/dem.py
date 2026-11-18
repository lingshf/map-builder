"""Elevation acquisition and sampling.

Providers return an :class:`ElevationGrid` sampled on a regular grid in the map
frame plus provenance. A provider *never* substitutes flat ground: missing
coverage, NoData or auth failure raise :mod:`errors` exceptions that the UI
reports.

Default automatic provider: Copernicus DEM GLO-30 public release, published as
cloud-optimised GeoTIFFs on the AWS Open Data registry (no credentials). The
Copernicus DEM licence allows free use, modification and redistribution,
including commercial, with attribution. It is a *surface* model (DSM) that
includes buildings and canopy at ~30 m; see docs for consequences.
"""

import math

from .errors import CoverageError, FormatError, LimitError, NoDataError
from .geodesy import utm_forward
from .tiff import FileSource, GeoTiff, HttpRangeSource

COPERNICUS_BASE_URL = "https://copernicus-dem-30m.s3.amazonaws.com"
COPERNICUS_ATTRIBUTION = (
    "Copernicus DEM GLO-30: (c) DLR e.V. 2010-2014 and (c) Airbus Defence and Space GmbH 2014-2018 "
    "provided under COPERNICUS by the European Union and ESA; all rights reserved. "
    "Produced using Copernicus WorldDEM-30 (c) DLR e.V. 2010-2014 and (c) Airbus Defence and Space GmbH "
    "2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved."
)
COPERNICUS_LICENSE = {
    "id": "Copernicus-DEM",
    "name": "Licence for the use of the Copernicus WorldDEM-30 / Copernicus DEM (free, worldwide, attribution)",
    "url": "https://spacedata.copernicus.eu/collections/copernicus-digital-elevation-model",
    "doi": "https://doi.org/10.5270/ESA-c5d3d65",
    "permits_offline_derivation": True,
    "permits_redistribution": True,
}
MAX_GRID_POINTS = 400_000


class ElevationGrid:
    """Heights H (above the provider's vertical datum) on a regular map grid.

    Point (i, j) is at x = x0 + i*spacing, y = y0 + j*spacing; heights[j][i].
    """

    def __init__(self, x0, y0, spacing, nx, ny, heights, provenance):
        self.x0, self.y0, self.spacing, self.nx, self.ny = x0, y0, spacing, nx, ny
        self.heights = heights
        self.provenance = provenance

    def min_max(self):
        flat = [h for row in self.heights for h in row]
        return min(flat), max(flat)

    def sample(self, x, y):
        """Bilinear height; positions outside are clamped to the grid edge."""
        fx = min(max((x - self.x0) / self.spacing, 0.0), self.nx - 1.000001)
        fy = min(max((y - self.y0) / self.spacing, 0.0), self.ny - 1.000001)
        i, j = int(fx), int(fy)
        tx, ty = fx - i, fy - j
        h = self.heights
        return ((h[j][i] * (1 - tx) + h[j][i + 1] * tx) * (1 - ty)
                + (h[j + 1][i] * (1 - tx) + h[j + 1][i + 1] * tx) * ty)


def grid_layout(area, spacing):
    if not (1.0 <= spacing <= 100.0):
        raise LimitError("terrain spacing must be between 1 and 100 m")
    hx, hy = area.half
    nx = int(math.ceil(2 * hx / spacing)) + 1
    ny = int(math.ceil(2 * hy / spacing)) + 1
    if nx * ny > MAX_GRID_POINTS:
        raise LimitError(f"terrain grid {nx}x{ny} exceeds {MAX_GRID_POINTS} points; increase spacing or shrink area")
    return -hx, -hy, nx, ny


class _Raster:
    """A GeoTIFF plus a function mapping (lat, lon) to raster CRS coordinates."""

    def __init__(self, tiff):
        self.tiff = tiff
        crs = tiff.crs
        if crs["kind"] == "geographic":
            self.project = lambda lat, lon: (lon, lat)
        else:
            zone, south = crs["zone"], crs["south"]
            self.project = lambda lat, lon: utm_forward(lat, lon, zone, south)

    def contains_pixel(self, col, row):
        return 0 <= col < self.tiff.width and 0 <= row < self.tiff.height


def _bilinear(rasters, pick, lat, lon):
    """Bilinear sample over possibly several tiles. Returns None for NoData/no coverage."""
    r = pick(lat, lon)
    if r is None:
        return None
    t = r.tiff
    x, y = r.project(lat, lon)
    fc, fr = t.col_row(x, y)
    c0, r0 = math.floor(fc), math.floor(fr)
    tx, ty = fc - c0, fr - r0
    vals = []
    for dr in (0, 1):
        for dc in (0, 1):
            c, rr = c0 + dc, r0 + dr
            if r.contains_pixel(c, rr):
                v = t.pixel(c, rr)
            else:
                # neighbour lives in an adjacent tile (or nowhere)
                px = t.x_c0 + c * t.sx
                py = t.y_c0 - rr * t.sy
                v = None
                if t.crs["kind"] == "geographic":
                    other = pick(py, px)
                    if other is not None and other is not r:
                        oc, orow = other.tiff.col_row(px, py)
                        oc, orow = int(round(oc)), int(round(orow))
                        if other.contains_pixel(oc, orow):
                            v = other.tiff.pixel(oc, orow)
            if v is None:
                return None
            vals.append(v)
    return ((vals[0] * (1 - tx) + vals[1] * tx) * (1 - ty) + (vals[2] * (1 - tx) + vals[3] * tx) * ty)


def _sample_grid(area, spacing, rasters, pick, provenance, progress=None):
    x0, y0, nx, ny = grid_layout(area, spacing)
    heights = []
    missing = 0
    first_missing = None
    for j in range(ny):
        row = []
        y = y0 + j * spacing
        for i in range(nx):
            x = x0 + i * spacing
            lat, lon = area.frame.to_geographic(x, y)
            v = _bilinear(rasters, pick, lat, lon)
            if v is None:
                missing += 1
                if first_missing is None:
                    first_missing = (lat, lon)
                v = 0.0
            row.append(v)
        heights.append(row)
        if progress:
            progress((j + 1) / ny)
    if missing:
        raise NoDataError(
            f"elevation source has NoData/no coverage at {missing} of {nx * ny} terrain samples "
            f"(first at lat {first_missing[0]:.6f}, lon {first_missing[1]:.6f}); "
            "no terrain was generated - choose another area or import a local elevation file")
    return ElevationGrid(x0, y0, spacing, nx, ny, heights, provenance)


def _source_resolution_m(tiff, lat):
    if tiff.crs["kind"] == "geographic":
        return (tiff.sx * 111320.0 * math.cos(math.radians(lat)), tiff.sy * 110574.0)
    return (tiff.sx, tiff.sy)


# --- Copernicus --------------------------------------------------------------

def copernicus_tile_name(lat_floor, lon_floor):
    ns = "N" if lat_floor >= 0 else "S"
    ew = "E" if lon_floor >= 0 else "W"
    return f"Copernicus_DSM_COG_10_{ns}{abs(lat_floor):02d}_00_{ew}{abs(lon_floor):03d}_00_DEM"


def fetch_copernicus(area, client, spacing=10.0, cache=None, base_url=COPERNICUS_BASE_URL, progress=None):
    s, w, n, e = area.geographic_bbox(margin_m=2 * spacing + 60.0)
    tiles = {}
    for la in range(math.floor(s), math.floor(n) + 1):
        for lo in range(math.floor(w), math.floor(e) + 1):
            tiles[(la, lo)] = copernicus_tile_name(la, lo)
    if len(tiles) > 4:
        raise LimitError("area spans more than 4 Copernicus tiles")
    rasters = {}
    for key, name in tiles.items():
        url = f"{base_url.rstrip('/')}/{name}/{name}.tif"
        try:
            src = HttpRangeSource(client, url, description=f"copernicus:{name}", cache=cache)
        except CoverageError:
            raise CoverageError(
                f"Copernicus DEM tile {name} is not published (ocean, or excluded from the public "
                "GLO-30 release); no terrain was generated - import a local elevation file instead") from None
        tiff = GeoTiff(src)
        if tiff.crs["kind"] != "geographic":
            raise FormatError(f"{name}: unexpected CRS {tiff.crs}")
        rasters[key] = _Raster(tiff)

    def pick(lat, lon):
        return rasters.get((math.floor(lat), math.floor(lon)))

    any_t = next(iter(rasters.values())).tiff
    res = _source_resolution_m(any_t, area.frame.lat0)
    prov = {
        "kind": "elevation",
        "provider": "copernicus-glo30-aws",
        "product": "Copernicus DEM GLO-30 (public release), digital SURFACE model",
        "access": f"{base_url} (AWS Open Data, no credentials)",
        "tiles": sorted(tiles.values()),
        "horizontal_crs": "EPSG:4326",
        "vertical_datum": "EGM2008 (EPSG:3855) orthometric height, metres",
        "source_resolution_m": [round(res[0], 2), round(res[1], 2)],
        "resampled_spacing_m": spacing,
        "resampling": "bilinear",
        "license": COPERNICUS_LICENSE,
        "attribution": COPERNICUS_ATTRIBUTION,
        "notes": "DSM: includes buildings and vegetation canopy smoothed at ~30 m; not bare earth.",
        "bytes_downloaded": sum(r.tiff.src.fetched for r in rasters.values()),
    }
    return _sample_grid(area, spacing, list(rasters.values()), pick, prov, progress)


# --- Local files -------------------------------------------------------------

def load_local_geotiff(area, path, spacing=10.0, vertical_datum="user-declared (unknown)", license_note="",
                       progress=None):
    import hashlib
    import os
    src = FileSource(path)
    try:
        tiff = GeoTiff(src)
        raster = _Raster(tiff)
        prov = _local_provenance(path, tiff, area, spacing, vertical_datum, license_note)
        with open(path, "rb") as f:
            prov["sha256"] = hashlib.sha256(f.read()).hexdigest()
        prov["file_name"] = os.path.basename(path)
        return _sample_grid(area, spacing, [raster], lambda la, lo: raster, prov, progress)
    finally:
        src.close()


def _local_provenance(path, tiff, area, spacing, vertical_datum, license_note):
    res = _source_resolution_m(tiff, area.frame.lat0)
    return {
        "kind": "elevation",
        "provider": "local-file",
        "product": "user-supplied elevation raster",
        "horizontal_crs": f"EPSG:{tiff.crs['epsg']}",
        "vertical_datum": vertical_datum,
        "source_resolution_m": [round(res[0], 3), round(res[1], 3)],
        "resampled_spacing_m": spacing,
        "resampling": "bilinear",
        "license": {"id": "user-declared", "name": license_note or "not declared by user"},
        "attribution": license_note or "",
    }


class AsciiGrid:
    """ESRI ASCII grid presented with the same interface as GeoTiff."""

    MAX_CELLS = 25_000_000

    def __init__(self, path, crs):
        self.src = type("S", (), {"description": path, "fetched": 0})()
        header = {}
        with open(path, "r", encoding="ascii", errors="strict") as f:
            pos = f.tell()
            line = f.readline()
            while line and line.split() and line.split()[0].lower() in (
                    "ncols", "nrows", "xllcorner", "yllcorner", "xllcenter", "yllcenter", "cellsize", "nodata_value"):
                k, v = line.split()[:2]
                header[k.lower()] = float(v)
                pos = f.tell()
                line = f.readline()
            f.seek(pos)
            try:
                self.width, self.height = int(header["ncols"]), int(header["nrows"])
                cs = header["cellsize"]
            except KeyError as e:
                raise FormatError(f"{path}: missing ASCII grid header {e}") from None
            if self.width * self.height > self.MAX_CELLS or self.width <= 1 or self.height <= 1 or cs <= 0:
                raise FormatError(f"{path}: implausible grid size")
            vals = f.read().split()
        if len(vals) != self.width * self.height:
            raise FormatError(f"{path}: expected {self.width * self.height} values, found {len(vals)}")
        try:
            self.values = [float(v) for v in vals]
        except ValueError:
            raise FormatError(f"{path}: non-numeric value in grid") from None
        self.nodata = header.get("nodata_value")
        self.sx = self.sy = cs
        if "xllcorner" in header:
            self.x_c0 = header["xllcorner"] + cs / 2
            ylow = header["yllcorner"] + cs / 2
        else:
            self.x_c0 = header["xllcenter"]
            ylow = header["yllcenter"]
        self.y_c0 = ylow + (self.height - 1) * cs
        self.crs = crs

    def col_row(self, x, y):
        return (x - self.x_c0) / self.sx, (self.y_c0 - y) / self.sy

    def pixel(self, col, row):
        if not (0 <= col < self.width and 0 <= row < self.height):
            return None
        v = self.values[row * self.width + col]
        if self.nodata is not None and v == self.nodata:
            return None
        return v


def parse_crs(text):
    """'EPSG:4326' or 'EPSG:326zz'/'EPSG:327zz' -> crs dict."""
    t = text.strip().upper().replace("EPSG:", "")
    try:
        code = int(t)
    except ValueError:
        raise FormatError(f"unsupported CRS {text!r}") from None
    if code == 4326:
        return {"kind": "geographic", "epsg": 4326}
    if 32601 <= code <= 32660 or 32701 <= code <= 32760:
        return {"kind": "utm", "epsg": code, "zone": code % 100, "south": code >= 32701}
    raise FormatError(f"unsupported CRS EPSG:{code}; use EPSG:4326 or a WGS84 UTM zone")


def load_ascii_grid(area, path, crs_text, spacing=10.0, vertical_datum="user-declared (unknown)",
                    license_note="", progress=None):
    import hashlib
    import os
    grid = AsciiGrid(path, parse_crs(crs_text))
    raster = _Raster(grid)
    raster.contains_pixel = lambda c, r: 0 <= c < grid.width and 0 <= r < grid.height
    prov = _local_provenance(path, grid, area, spacing, vertical_datum, license_note)
    with open(path, "rb") as f:
        prov["sha256"] = hashlib.sha256(f.read()).hexdigest()
    prov["file_name"] = os.path.basename(path)
    return _sample_grid(area, spacing, [raster], lambda la, lo: raster, prov, progress)


def load_local_elevation(area, path, spacing=10.0, crs_text="EPSG:4326", vertical_datum="user-declared (unknown)",
                         license_note="", progress=None):
    lower = path.lower()
    if lower.endswith((".tif", ".tiff")):
        return load_local_geotiff(area, path, spacing, vertical_datum, license_note, progress)
    if lower.endswith(".asc"):
        return load_ascii_grid(area, path, crs_text, spacing, vertical_datum, license_note, progress)
    raise FormatError(f"{path}: unsupported elevation file type (use .tif/.tiff GeoTIFF or .asc ESRI ASCII grid)")
