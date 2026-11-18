import math
import os
import random
import tempfile
import unittest

from map_builder.core.dem import fetch_copernicus, load_local_elevation
from map_builder.core.errors import AuthError, CoverageError, FormatError, LimitError, NetworkError, NoDataError
from map_builder.core.geodesy import Area, utm_forward
from map_builder.core.http import HttpClient, Response, redact
from map_builder.core.tiff import BytesSource, GeoTiff, lzw_decode

from .synthetic import AREA_H, AREA_W, ORIGIN, dem_height, write_dem_asc
from .tiffwriter import lzw_encode, make_geotiff


class FakeTransport:
    """Serves in-memory files with HTTP Range semantics; records requests."""

    def __init__(self, files=None, status=None, ignore_range=False):
        self.files = files or {}
        self.status = status
        self.ignore_range = ignore_range
        self.requests = []

    def request(self, method, url, headers, data, timeout, max_bytes):
        self.requests.append((method, url, dict(headers), data))
        if self.status:
            return Response(self.status, b"denied")
        body = self.files.get(url)
        if body is None:
            return Response(404, b"not found")
        rng = headers.get("Range")
        if rng and not self.ignore_range:
            a, b = rng.split("=")[1].split("-")
            return Response(206, body[int(a):int(b) + 1])
        return Response(200, body)


class TiffTest(unittest.TestCase):
    def test_lzw_round_trip_with_width_growth_and_reset(self):
        rng = random.Random(1)
        data = bytes(rng.randrange(0, 16) for _ in range(60000)) + bytes(range(256)) * 20
        self.assertEqual(lzw_decode(lzw_encode(data)), data)

    def test_layouts_compressions_predictors(self):
        vals = [[(r * 37 + c * 11) % 500 - 100.5 for c in range(37)] for r in range(23)]
        ivals = [[(r * 37 + c * 11) % 500 - 100 for c in range(37)] for r in range(23)]
        cases = []
        for big in (False, True):
            for layout in ({"tile": (16, 16)}, {"rows_per_strip": 5}, {}):
                for comp in (1, 5, 8):
                    cases.append((big, layout, comp, 1, "f32", vals))
                    cases.append((big, layout, comp, 3, "f32", vals))
                    cases.append((big, layout, comp, 2, "i16", ivals))
        for big, layout, comp, pred, sample, src in cases:
            with self.subTest(big=big, layout=layout, comp=comp, pred=pred):
                data = make_geotiff(src, 8.0, 47.1, 0.001, 0.001, big_endian=big, compression=comp,
                                    predictor=pred, sample=sample, **layout)
                t = GeoTiff(BytesSource(data))
                for r, c in ((0, 0), (22, 36), (7, 17), (16, 16), (15, 15)):
                    self.assertAlmostEqual(t.pixel(c, r), src[r][c], places=4)

    def test_georeference_area_vs_point_and_nodata(self):
        vals = [[1.0, 2.0], [3.0, -9999.0]]
        area = GeoTiff(BytesSource(make_geotiff(vals, 8.0, 47.0, 0.5, 0.5, nodata=-9999)))
        self.assertEqual(area.col_row(8.25, 46.75), (0.0, 0.0))  # first pixel centre
        self.assertIsNone(area.pixel(1, 1))
        point = GeoTiff(BytesSource(make_geotiff(vals, 8.0, 47.0, 0.5, 0.5, pixel_is_point=True)))
        self.assertEqual(point.col_row(8.0, 47.0), (0.0, 0.0))

    def test_rejects_unsupported_crs_and_garbage(self):
        with self.assertRaises(FormatError):
            GeoTiff(BytesSource(make_geotiff([[1.0, 2.0]], 0, 0, 1, 1, epsg=3857)))
        with self.assertRaises(FormatError):
            GeoTiff(BytesSource(b"GIF89a" + b"\0" * 50))


class LocalElevationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.area = Area(*ORIGIN, AREA_W, AREA_H)

    def test_ascii_grid_matches_synthetic_surface(self):
        path = write_dem_asc(os.path.join(self.tmp, "d.asc"))
        g = load_local_elevation(self.area, path, 10.0, "EPSG:4326", "SYNTHETIC datum", "SYNTHETIC")
        for x, y in ((0, 0), (150, -100), (-180, 120)):
            self.assertAlmostEqual(g.sample(x, y), dem_height(x, y), delta=0.05)
        self.assertEqual(g.provenance["vertical_datum"], "SYNTHETIC datum")
        self.assertEqual(len(g.provenance["sha256"]), 64)

    def test_utm_geotiff(self):
        lat0, lon0 = ORIGIN
        e0, n0 = utm_forward(lat0, lon0, 32, False)
        size, cell = 70, 10.0
        x_ul, y_ul = e0 - size * cell / 2, n0 + size * cell / 2
        vals = [[(y_ul - (r + 0.5) * cell) * 0.01 - n0 * 0.01 + 500 for c in range(size)] for r in range(size)]
        path = os.path.join(self.tmp, "u.tif")
        with open(path, "wb") as f:
            f.write(make_geotiff(vals, x_ul, y_ul, cell, cell, epsg=32632, tile=(32, 32)))
        g = load_local_elevation(Area(lat0, lon0, 300, 300), path, 10.0)
        _, north = utm_forward(*Area(lat0, lon0, 300, 300).frame.to_geographic(0, 100), 32, False)
        self.assertAlmostEqual(g.sample(0, 100), (north - n0) * 0.01 + 500, delta=0.02)
        self.assertEqual(g.provenance["horizontal_crs"], "EPSG:32632")

    def test_nodata_inside_area_is_an_error_not_flat_ground(self):
        lat0, lon0 = ORIGIN
        vals = [[400.0] * 40 for _ in range(40)]
        vals[20][20] = -32768.0
        path = os.path.join(self.tmp, "n.tif")
        with open(path, "wb") as f:
            f.write(make_geotiff(vals, lon0 - 0.02, lat0 + 0.02, 0.001, 0.001, nodata=-32768))
        with self.assertRaises(NoDataError) as cm:
            load_local_elevation(Area(lat0, lon0, 1000, 1000), path, 10.0)
        self.assertIn("no terrain was generated", str(cm.exception))

    def test_partial_coverage_is_an_error(self):
        lat0, lon0 = ORIGIN
        path = os.path.join(self.tmp, "p.tif")
        with open(path, "wb") as f:
            f.write(make_geotiff([[1.0] * 10 for _ in range(10)], lon0, lat0 + 0.001, 0.0005, 0.0005))
        with self.assertRaises(NoDataError):
            load_local_elevation(Area(lat0, lon0, 200, 200), path, 10.0)

    def test_unknown_extension(self):
        with self.assertRaises(FormatError):
            load_local_elevation(self.area, os.path.join(self.tmp, "x.xyz"))


class CopernicusTest(unittest.TestCase):
    BASE = "https://example.invalid/cop"

    def tile(self):
        # SYNTHETIC stand-in for tile N47/E008: 0.004 deg pixels, PixelIsPoint, predictor 3, tiled.
        n = 251
        vals = [[500.0 + r * 0.5 + c * 0.25 for c in range(n)] for r in range(n)]
        return make_geotiff(vals, 8.0, 48.0, 0.004, 0.004, tile=(64, 64), predictor=3, pixel_is_point=True)

    def url(self, name):
        return f"{self.BASE}/{name}/{name}.tif"

    def test_fetch_success_and_provenance(self):
        name = "Copernicus_DSM_COG_10_N47_00_E008_00_DEM"
        tr = FakeTransport({self.url(name): self.tile()})
        g = fetch_copernicus(Area(47.5, 8.5, 400, 400), HttpClient(tr), 20.0, base_url=self.BASE)
        lat, lon = 47.5, 8.5
        expect = 500.0 + (48.0 - lat) / 0.004 * 0.5 + (lon - 8.0) / 0.004 * 0.25
        self.assertAlmostEqual(g.sample(0, 0), expect, delta=0.01)
        self.assertIn("EGM2008", g.provenance["vertical_datum"])
        self.assertIn("SURFACE", g.provenance["product"])
        self.assertTrue(all("Range" in h for _, _, h, _ in tr.requests))

    def test_missing_tile_is_coverage_error(self):
        with self.assertRaises(CoverageError) as cm:
            fetch_copernicus(Area(47.5, 8.5, 400, 400), HttpClient(FakeTransport({})), 20.0, base_url=self.BASE)
        self.assertIn("local elevation file", str(cm.exception))

    def test_auth_error_propagates(self):
        with self.assertRaises(AuthError):
            fetch_copernicus(Area(47.5, 8.5, 400, 400), HttpClient(FakeTransport(status=403)), 20.0,
                             base_url=self.BASE)

    def test_area_across_tile_corner_needs_all_tiles(self):
        name = "Copernicus_DSM_COG_10_N47_00_E008_00_DEM"
        tr = FakeTransport({self.url(name): self.tile()})
        with self.assertRaises(CoverageError):
            fetch_copernicus(Area(47.0, 8.0, 400, 400), HttpClient(tr), 20.0, base_url=self.BASE)


class HttpTest(unittest.TestCase):
    def test_redaction(self):
        u = "https://user:secret@host.example/path/x.tif?token=abc&key=def"
        r = redact(u)
        self.assertNotIn("secret", r)
        self.assertNotIn("abc", r)
        self.assertIn("host.example/path/x.tif", r)

    def test_status_mapping_never_leaks_query(self):
        url = "https://h.example/a?api_key=SECRET123"
        for status, exc in ((401, AuthError), (403, AuthError), (429, NetworkError), (500, NetworkError)):
            with self.assertRaises(exc) as cm:
                HttpClient(FakeTransport(status=status)).fetch(url)
            self.assertNotIn("SECRET123", str(cm.exception))
        with self.assertRaises(NetworkError):
            HttpClient(FakeTransport({})).fetch(url)  # plain 404 without coverage semantics
        with self.assertRaises(CoverageError):
            HttpClient(FakeTransport({})).fetch(url, not_found_is_coverage=True)

    def test_size_limit_and_ignored_range(self):
        tr = FakeTransport({"u": bytes(range(200))}, ignore_range=True)
        self.assertEqual(HttpClient(tr).fetch("u", byte_range=(10, 5)), bytes(range(10, 15)))
        with self.assertRaises(LimitError):
            HttpClient(tr, max_bytes=100).fetch("u")


if __name__ == "__main__":
    unittest.main()
