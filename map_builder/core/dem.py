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

from __future__ import annotations

import hashlib
import math
import os
from array import array
from collections.abc import Callable, Iterable, Sequence
from typing import TYPE_CHECKING, Any, BinaryIO, Protocol, TypeAlias

from .cache import check_cache_dataset_id
from .errors import CoverageError, FormatError, LimitError, NoDataError
from .geodesy import utm_forward
from .http import redact
from .tiff import FileSource, GeoTiff, HttpRangeSource

if TYPE_CHECKING:
    from .cache import CacheLike
    from .geodesy import Area
    from .tiff import Crs, RangeClient

Provenance: TypeAlias = "dict[str, object]"
ProgressFn: TypeAlias = "Callable[[float], None]"


class RasterSource(Protocol):
    """Georeferenced single-band raster (:class:`GeoTiff` or :class:`AsciiGrid`)."""

    width: int
    height: int
    sx: float
    sy: float
    x_c0: float
    y_c0: float
    crs: Crs

    def col_row(self, x: float, y: float) -> tuple[float, float]: ...

    def pixel(self, col: int, row: int) -> float | None: ...

COPERNICUS_BASE_URL = "https://copernicus-dem-30m.s3.amazonaws.com"
COPERNICUS_ATTRIBUTION = (
    "Copernicus DEM GLO-30: (c) DLR e.V. 2010-2014 and (c) Airbus Defence and Space GmbH 2014-2018 "
    "provided under COPERNICUS by the European Union and ESA; all rights reserved. "
    "Produced using Copernicus WorldDEM-30 (c) DLR e.V. 2010-2014 and (c) Airbus Defence and Space GmbH "
    "2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved."
)
COPERNICUS_LICENSE: dict[str, object] = {
    "id": "Copernicus-DEM",
    "name": "Licence for the use of the Copernicus WorldDEM-30 / Copernicus DEM (free, worldwide, attribution)",
    "url": "https://spacedata.copernicus.eu/collections/copernicus-digital-elevation-model",
    "doi": "https://doi.org/10.5270/ESA-c5d3d65",
    "permits_offline_derivation": True,
    "permits_redistribution": True,
}
MAX_GRID_POINTS = 400_000
COPERNICUS_DATASET_ID = "copernicus-dem-glo30-public"
HASH_CHUNK = 1024 * 1024


def _sha256_file(path: str, chunk: int = HASH_CHUNK) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


class ElevationGrid:
    """Heights H (above the provider's vertical datum) on a regular map grid.

    Point (i, j) is at x = x0 + i*spacing, y = y0 + j*spacing; heights[j][i].
    """

    x0: float
    y0: float
    spacing: float
    nx: int
    ny: int

    def __init__(self, x0: float, y0: float, spacing: float, nx: int, ny: int,
                 heights: list[list[float]], provenance: Provenance) -> None:
        self.x0, self.y0, self.spacing, self.nx, self.ny = x0, y0, spacing, nx, ny
        self.heights: list[list[float]] = heights
        self.provenance: Provenance = provenance

    def min_max(self) -> tuple[float, float]:
        flat = [h for row in self.heights for h in row]
        return min(flat), max(flat)

    def sample(self, x: float, y: float) -> float:
        """Bilinear height; positions outside are clamped to the grid edge."""
        fx = min(max((x - self.x0) / self.spacing, 0.0), self.nx - 1.000001)
        fy = min(max((y - self.y0) / self.spacing, 0.0), self.ny - 1.000001)
        i, j = int(fx), int(fy)
        tx, ty = fx - i, fy - j
        h = self.heights
        return ((h[j][i] * (1 - tx) + h[j][i + 1] * tx) * (1 - ty)
                + (h[j + 1][i] * (1 - tx) + h[j + 1][i + 1] * tx) * ty)


def grid_layout(area: Area, spacing: float) -> tuple[float, float, int, int]:
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

    def __init__(self, tiff: RasterSource) -> None:
        self.tiff: RasterSource = tiff
        crs = tiff.crs
        self.project: Callable[[float, float], tuple[float, float]]
        if crs["kind"] == "geographic":
            self.project = lambda lat, lon: (lon, lat)
        else:
            zone, south = crs["zone"], crs["south"]
            self.project = lambda lat, lon: utm_forward(lat, lon, zone, south)

    def contains_pixel(self, col: int, row: int) -> bool:
        return 0 <= col < self.tiff.width and 0 <= row < self.tiff.height


def _bilinear(rasters: Sequence[_Raster], pick: Callable[[float, float], _Raster | None], lat: float,
              lon: float) -> float | None:
    """Bilinear sample over possibly several tiles. Returns None for NoData/no coverage."""
    r = pick(lat, lon)
    if r is None:
        return None
    t = r.tiff
    x, y = r.project(lat, lon)
    fc, fr = t.col_row(x, y)
    c0, r0 = math.floor(fc), math.floor(fr)
    tx, ty = fc - c0, fr - r0
    vals: list[float] = []
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


def _check_windows(area: Area, spacing: float, rasters: Iterable[_Raster]) -> None:
    """Bound the pixel window each raster must serve before any block is decoded."""
    s, w, n, e = area.geographic_bbox(margin_m=2 * spacing + 60.0)
    pts = [(la, lo) for la in (s, (s + n) / 2, n) for lo in (w, (w + e) / 2, e)]
    for r in rasters:
        t = r.tiff
        if not hasattr(t, "check_window"):
            continue
        cr = [t.col_row(*r.project(la, lo)) for la, lo in pts]
        c0 = max(0, math.floor(min(c for c, _ in cr)) - 1)
        r0 = max(0, math.floor(min(rr for _, rr in cr)) - 1)
        c1 = min(t.width - 1, math.ceil(max(c for c, _ in cr)) + 1)
        r1 = min(t.height - 1, math.ceil(max(rr for _, rr in cr)) + 1)
        t.check_window(c0, r0, c1, r1)


def _sample_grid(area: Area, spacing: float, rasters: Sequence[_Raster],
                 pick: Callable[[float, float], _Raster | None], provenance: Provenance,
                 progress: ProgressFn | None = None) -> ElevationGrid:
    x0, y0, nx, ny = grid_layout(area, spacing)
    _check_windows(area, spacing, rasters)
    heights: list[list[float]] = []
    missing = 0
    first_missing: tuple[float, float] | None = None
    for j in range(ny):
        row: list[float] = []
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
            f"(first at lat {first_missing[0]:.6f}, lon {first_missing[1]:.6f}); "  # type: ignore[index]  # set whenever missing > 0
            "no terrain was generated - choose another area or import a local elevation file")
    return ElevationGrid(x0, y0, spacing, nx, ny, heights, provenance)


def _source_resolution_m(tiff: RasterSource, lat: float) -> tuple[float, float]:
    if tiff.crs["kind"] == "geographic":
        return (tiff.sx * 111320.0 * math.cos(math.radians(lat)), tiff.sy * 110574.0)
    return (tiff.sx, tiff.sy)


# --- Copernicus --------------------------------------------------------------

def copernicus_tile_name(lat_floor: int, lon_floor: int) -> str:
    ns = "N" if lat_floor >= 0 else "S"
    ew = "E" if lon_floor >= 0 else "W"
    return f"Copernicus_DSM_COG_10_{ns}{abs(lat_floor):02d}_00_{ew}{abs(lon_floor):03d}_00_DEM"


def _is_default_endpoint(url: object, default: str) -> bool:
    return isinstance(url, str) and url.strip().rstrip("/") == default.rstrip("/")


def _open_remote_tiff(client: RangeClient, url: str, description: str, cache: CacheLike | None,
                      cache_key: str, name: str) -> GeoTiff:
    """Open a remote GeoTIFF; ranges are cached only after validation. If data served from the
    cache fails validation, those entries are evicted and the tile is fetched once more."""
    for attempt in (0, 1):
        try:
            src = HttpRangeSource(client, url, description=description, cache=cache, cache_key=cache_key,
                                  read_cache=attempt == 0)
        except CoverageError:
            raise CoverageError(
                f"Copernicus DEM tile {name} is not published (ocean, or excluded from the public "
                "GLO-30 release); no terrain was generated - import a local elevation file instead") from None
        try:
            tiff = GeoTiff(src)  # invalidates the source's cache entries on failure
            if tiff.crs["kind"] != "geographic":
                src.invalidate()  # provider-specific rejection: evict like any other validation failure
                raise FormatError(f"{name}: unexpected CRS {tiff.crs}")
            return tiff
        except (FormatError, LimitError):
            if attempt or not src.cache_hits:
                raise
    raise AssertionError("unreachable")


def fetch_copernicus(area: Area, client: RangeClient, spacing: float = 10.0, cache: CacheLike | None = None,
                     base_url: str = COPERNICUS_BASE_URL, progress: ProgressFn | None = None,
                     allow_cache_override: bool = False, cache_dataset_id: str | None = None) -> ElevationGrid:
    """``cache`` is used only for the public default endpoint (whose licence permits caching) unless the
    caller explicitly sets ``allow_cache_override`` for a mirror it knows may be cached; caching such an
    override additionally requires a caller-chosen, credential-free ``cache_dataset_id`` because the
    endpoint URL (whose path may embed a credential) is never used as cache identity or metadata."""
    grid_layout(area, spacing)  # resource bounds are enforced before any network access
    is_default = _is_default_endpoint(base_url, COPERNICUS_BASE_URL)
    if is_default:
        endpoint = COPERNICUS_BASE_URL  # fixed public label
        cache_scope: str | None = COPERNICUS_BASE_URL
    else:
        endpoint = redact(base_url)  # origin only
        cache_scope = None
        if not allow_cache_override:
            cache = None
        elif cache is not None:
            if cache_dataset_id is None:
                raise ValueError("allow_cache_override requires an explicit, credential-free cache_dataset_id")
            cache_scope = "override:" + check_cache_dataset_id(cache_dataset_id, base_url)
    s, w, n, e = area.geographic_bbox(margin_m=2 * spacing + 60.0)
    tiles: dict[tuple[int, int], str] = {}
    for la in range(math.floor(s), math.floor(n) + 1):
        for lo in range(math.floor(w), math.floor(e) + 1):
            tiles[(la, lo)] = copernicus_tile_name(la, lo)
    if len(tiles) > 4:
        raise LimitError("area spans more than 4 Copernicus tiles")
    rasters: dict[tuple[int, int], _Raster] = {}
    for key, name in tiles.items():
        url = f"{base_url.rstrip('/')}/{name}/{name}.tif"
        tiff = _open_remote_tiff(client, url, f"copernicus:{name}", cache,
                                 f"{COPERNICUS_DATASET_ID}|{cache_scope}|{name}", name)
        rasters[key] = _Raster(tiff)

    def pick(lat: float, lon: float) -> _Raster | None:
        return rasters.get((math.floor(lat), math.floor(lon)))

    any_t = next(iter(rasters.values())).tiff
    res = _source_resolution_m(any_t, area.frame.lat0)
    prov: Provenance = {
        "kind": "elevation",
        "provider": "copernicus-glo30-aws",
        "product": "Copernicus DEM GLO-30 (public release), digital SURFACE model",
        "access": (f"{endpoint} (AWS Open Data, no credentials)" if is_default
                   else f"{endpoint} (caller-supplied endpoint)"),
        "tiles": sorted(tiles.values()),
        "horizontal_crs": "EPSG:4326",
        "vertical_datum": "EGM2008 (EPSG:3855) orthometric height, metres",
        "source_resolution_m": [round(res[0], 2), round(res[1], 2)],
        "resampled_spacing_m": spacing,
        "resampling": "bilinear",
        "license": COPERNICUS_LICENSE,
        "attribution": COPERNICUS_ATTRIBUTION,
        "notes": "DSM: includes buildings and vegetation canopy smoothed at ~30 m; not bare earth.",
        "bytes_downloaded": sum(r.tiff.src.fetched for r in rasters.values()),  # type: ignore[attr-defined]  # only GeoTiff over HttpRangeSource reaches here
    }
    return _sample_grid(area, spacing, list(rasters.values()), pick, prov, progress)


# --- Local files -------------------------------------------------------------

def load_local_geotiff(area: Area, path: str, spacing: float = 10.0, vertical_datum: str = "user-declared (unknown)",
                       license_note: str = "", progress: ProgressFn | None = None) -> ElevationGrid:
    src = FileSource(path)
    try:
        tiff = GeoTiff(src)
        raster = _Raster(tiff)
        prov = _local_provenance(path, tiff, area, spacing, vertical_datum, license_note)
        prov["sha256"] = _sha256_file(path)
        prov["file_name"] = os.path.basename(path)
        return _sample_grid(area, spacing, [raster], lambda la, lo: raster, prov, progress)
    finally:
        src.close()


def _local_provenance(path: str, tiff: RasterSource, area: Area, spacing: float, vertical_datum: str,
                      license_note: str) -> Provenance:
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
    """ESRI ASCII grid presented with the same interface as GeoTiff.

    Parsed incrementally in bounded chunks: the file size, header line length,
    token length and token count are all checked while reading, and values are
    stored compactly. NaN/Inf samples and the NODATA_value sentinel (including
    a NaN sentinel) read as NoData.
    """

    MAX_CELLS = 25_000_000
    MAX_FILE_BYTES = 1024 ** 3
    MAX_HEADER_LINE = 256
    MAX_TOKEN = 64
    CHUNK = 256 * 1024
    _HEADER_KEYS = ("ncols", "nrows", "xllcorner", "yllcorner", "xllcenter", "yllcenter", "cellsize", "nodata_value")

    width: int
    height: int

    def __init__(self, path: str, crs: Crs) -> None:
        self.src: Any = type("S", (), {"description": path, "fetched": 0})()  # Any: ad-hoc stand-in object
        header: dict[str, float] = {}
        with open(path, "rb") as f:
            if os.fstat(f.fileno()).st_size > self.MAX_FILE_BYTES:
                raise LimitError(f"{path}: ASCII grid larger than {self.MAX_FILE_BYTES} bytes")
            while True:
                pos = f.tell()
                line = f.readline(self.MAX_HEADER_LINE)
                parts = line.split()
                if not parts or parts[0].decode("ascii", "replace").lower() not in self._HEADER_KEYS:
                    break
                if len(parts) < 2:
                    raise FormatError(f"{path}: malformed ASCII grid header line")
                try:
                    header[parts[0].decode("ascii").lower()] = float(parts[1])
                except (UnicodeDecodeError, ValueError):
                    raise FormatError(f"{path}: malformed ASCII grid header value") from None
            f.seek(pos)
            try:
                self.width, self.height = int(header["ncols"]), int(header["nrows"])
                cs = header["cellsize"]
            except KeyError as e:
                raise FormatError(f"{path}: missing ASCII grid header {e}") from None
            except (ValueError, OverflowError):
                raise FormatError(f"{path}: implausible grid size") from None
            if (self.width * self.height > self.MAX_CELLS or self.width <= 1 or self.height <= 1
                    or not (math.isfinite(cs) and cs > 0)):
                raise FormatError(f"{path}: implausible grid size")
            self.values = self._read_values(f, path, self.width * self.height)
        self.nodata: float | None = header.get("nodata_value")
        self.sx: float
        self.sy: float
        self.sx = self.sy = cs
        if "xllcorner" in header:
            self.x_c0 = header["xllcorner"] + cs / 2
            ylow = header["yllcorner"] + cs / 2
        else:
            self.x_c0 = header["xllcenter"]
            ylow = header["yllcenter"]
        self.y_c0 = ylow + (self.height - 1) * cs
        self.crs: Crs = crs

    def _read_values(self, f: BinaryIO, path: str, expected: int) -> array[float]:
        values = array("d")
        carry = b""
        while True:
            chunk = f.read(self.CHUNK)
            data = carry + chunk
            toks = data.split()
            carry = b""
            if chunk and toks and not data[-1:].isspace():
                carry = toks.pop()  # possibly split token; finish it with the next chunk
                if len(carry) > self.MAX_TOKEN:
                    raise FormatError(f"{path}: over-long value in grid")
            if len(values) + len(toks) > expected:
                raise FormatError(f"{path}: expected {expected} values, found more")
            try:
                for t in toks:
                    if len(t) > self.MAX_TOKEN:
                        raise ValueError
                    values.append(float(t))
            except ValueError:
                raise FormatError(f"{path}: non-numeric value in grid") from None
            if not chunk:
                break
        if len(values) != expected:
            raise FormatError(f"{path}: expected {expected} values, found {len(values)}")
        return values

    def col_row(self, x: float, y: float) -> tuple[float, float]:
        return (x - self.x_c0) / self.sx, (self.y_c0 - y) / self.sy

    def pixel(self, col: int, row: int) -> float | None:
        if not (0 <= col < self.width and 0 <= row < self.height):
            return None
        v = self.values[row * self.width + col]
        if not math.isfinite(v):
            return None  # NaN/Inf (including a NaN NODATA_value) are NoData
        if self.nodata is not None and v == self.nodata:
            return None
        return v


def parse_crs(text: str) -> Crs:
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


def load_ascii_grid(area: Area, path: str, crs_text: str, spacing: float = 10.0,
                    vertical_datum: str = "user-declared (unknown)", license_note: str = "",
                    progress: ProgressFn | None = None) -> ElevationGrid:
    grid = AsciiGrid(path, parse_crs(crs_text))
    raster = _Raster(grid)
    raster.contains_pixel = lambda c, r: 0 <= c < grid.width and 0 <= r < grid.height  # type: ignore[method-assign,assignment]  # per-instance override
    prov = _local_provenance(path, grid, area, spacing, vertical_datum, license_note)
    prov["sha256"] = _sha256_file(path)
    prov["file_name"] = os.path.basename(path)
    return _sample_grid(area, spacing, [raster], lambda la, lo: raster, prov, progress)


def load_local_elevation(area: Area, path: str, spacing: float = 10.0, crs_text: str = "EPSG:4326",
                         vertical_datum: str = "user-declared (unknown)", license_note: str = "",
                         progress: ProgressFn | None = None) -> ElevationGrid:
    grid_layout(area, spacing)  # resource bounds are enforced before the file is opened
    lower = path.lower()
    if lower.endswith((".tif", ".tiff")):
        return load_local_geotiff(area, path, spacing, vertical_datum, license_note, progress)
    if lower.endswith(".asc"):
        return load_ascii_grid(area, path, crs_text, spacing, vertical_datum, license_note, progress)
    raise FormatError(f"{path}: unsupported elevation file type (use .tif/.tiff GeoTIFF or .asc ESRI ASCII grid)")
