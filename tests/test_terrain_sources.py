import hashlib
import io
import json
import math
import os
import random
import tempfile
import unittest
import urllib.error
import urllib.parse
import urllib.request
import zlib
from unittest import mock

from map_builder.core import dem as dem_mod
from map_builder.core import osm as osm_mod
from map_builder.core import tiff as tiff_mod
from map_builder.core.cache import MAX_META_BYTES, DiskCache
from map_builder.core.dem import COPERNICUS_BASE_URL, AsciiGrid, fetch_copernicus, load_local_elevation, parse_crs
from map_builder.core.errors import (AuthError, CoverageError, FormatError, LimitError, MapBuilderError, NetworkError,
                                     NoDataError)
from map_builder.core.geodesy import Area, utm_forward
from map_builder.core.http import HttpClient, Response, SafeRedirectHandler, UrllibTransport, redact
from map_builder.core.osm import DEFAULT_OVERPASS_URL, classify, fetch_overpass, parse_osm_xml, ring_area
from map_builder.core.tiff import BytesSource, GeoTiff, HttpRangeSource, lzw_decode

from .synthetic import AREA_H, AREA_W, ORIGIN, OsmBuilder, dem_height, rect, write_dem_asc
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
            a, b = (int(v) for v in rng.split("=")[1].split("-"))
            if a >= len(body):
                return Response(416, b"")
            part = body[a:b + 1]
            return Response(206, part, {"Content-Range": f"bytes {a}-{a + len(part) - 1}/{len(body)}"})
        return Response(200, body[:max_bytes + 1])


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
        self.assertEqual(r, "https://host.example")

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


# --- helpers for review-finding tests ----------------------------------------

class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


class FakeHttpResponse:
    def __init__(self, chunks, clock=None, step=0.0, status=200):
        self.chunks = list(chunks)
        self.clock, self.step, self.status = clock, step, status
        self.headers = {}
        self.closed = False

    def read(self, n=-1):
        if self.clock:
            self.clock.t += self.step
        return self.chunks.pop(0) if self.chunks else b""

    def getcode(self):
        return self.status

    def close(self):
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class FakeOpener:
    def __init__(self, resp=None, exc=None):
        self.resp, self.exc = resp, exc

    def open(self, req, timeout=None):
        if self.exc:
            raise self.exc
        return self.resp


class ScriptedTransport:
    """Returns pre-built Response objects in order; records requests."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    def request(self, method, url, headers, data, timeout, max_bytes):
        self.requests.append((method, url, dict(headers), data))
        return self.responses.pop(0)


class MemoryCache:
    def __init__(self):
        self.store = {}
        self.gets, self.puts = [], []

    def get(self, namespace, key):
        self.gets.append((namespace, key))
        return self.store.get((namespace, key))

    def put(self, namespace, key, body, meta=None):
        self.puts.append((namespace, key, meta))
        self.store[(namespace, key)] = body

    def delete(self, namespace, key):
        self.store.pop((namespace, key), None)


def osm_doc(inner, header='<?xml version="1.0" encoding="UTF-8"?>'):
    return f'{header}<osm version="0.6">{inner}</osm>'.encode("utf-8")


def ids_of(items):
    return {i["id"] if isinstance(i, dict) else i.id for i in items}


class RedirectSafetyTest(unittest.TestCase):
    """Finding 1: credentials are never forwarded cross-origin or downgraded to http."""

    def redirect(self, url, newurl, headers):
        req = urllib.request.Request(url, headers=headers)
        return SafeRedirectHandler().redirect_request(req, io.BytesIO(b""), 302, "Found", {}, newurl)

    def test_cross_origin_or_downgrade_with_credentials_refused(self):
        for hdr in ({"Authorization": "Bearer SECRET"}, {"X-API-Key": "SECRET"}, {"Cookie": "s=SECRET"}):
            for new in ("https://evil.example/x", "http://api.example/x", "https://api.example:8443/x"):
                with self.subTest(hdr=hdr, new=new), self.assertRaises(NetworkError) as cm:
                    self.redirect("https://api.example/a?key=SECRET", new, hdr)
                self.assertNotIn("SECRET", str(cm.exception))

    def test_allowed_redirects(self):
        new = self.redirect("https://api.example/a", "https://api.example:443/b", {"Authorization": "Bearer t"})
        self.assertEqual(new.full_url, "https://api.example:443/b")
        new = self.redirect("https://a.example/a", "http://b.example/b", {"Accept": "*/*"})
        self.assertEqual(new.full_url, "http://b.example/b")
        with self.assertRaises(NetworkError):
            self.redirect("https://a.example/a", "file:///etc/passwd", {})
        self.assertLessEqual(SafeRedirectHandler().max_redirections, 5)


class SecretLeakTest(unittest.TestCase):
    """Finding 2: no reasons, bodies, userinfo or queries in errors/provenance."""

    def test_transport_error_message_is_fixed(self):
        url = "https://user:PW@h.example/a?token=SECRET"
        for exc in (urllib.error.URLError("SECRET-reason https://user:PW@x"), OSError("SECRET in os error")):
            t = UrllibTransport(opener=FakeOpener(exc=exc))
            with self.assertRaises(NetworkError) as cm:
                t.request("GET", url, {}, None, 5, 100)
            msg = str(cm.exception)
            self.assertNotIn("SECRET", msg)
            self.assertNotIn("PW", msg)
            self.assertIn(type(exc).__name__, msg)

    def test_http_error_body_not_in_message(self):
        tr = ScriptedTransport(Response(500, b"internal error: api_key=SECRET"))
        with self.assertRaises(NetworkError) as cm:
            HttpClient(tr).fetch("https://h.example/a")
        self.assertNotIn("SECRET", str(cm.exception))
        self.assertIn("HTTP 500", str(cm.exception))

    def test_copernicus_provenance_redacts_base_url(self):
        base = "https://user:SECRET@example.invalid/cop"
        name = "Copernicus_DSM_COG_10_N47_00_E008_00_DEM"
        tr = FakeTransport({f"{base}/{name}/{name}.tif": CopernicusTest().tile()})
        cache = MemoryCache()
        g = fetch_copernicus(Area(47.5, 8.5, 400, 400), HttpClient(tr), 20.0, cache, base,
                             allow_cache_override=True, cache_dataset_id="example-mirror")
        self.assertNotIn("SECRET", json.dumps(g.provenance))
        self.assertIn("https://example.invalid", g.provenance["access"])
        self.assertNotIn("/cop", g.provenance["access"])
        self.assertTrue(cache.puts)
        self.assertFalse(any("SECRET" in json.dumps(p) for p in cache.puts))


class TiffBoundsTest(unittest.TestCase):
    """Finding 3: validated geometry, capped decompression, tag budget, byte-bounded cache, window check."""

    VALS = [[float(r * 8 + c) for c in range(8)] for r in range(8)]

    def test_deflate_and_lzw_bombs_are_capped(self):
        for comp, enc in ((8, zlib.compress), (5, lzw_encode)):
            with self.subTest(comp=comp):
                data = make_geotiff(self.VALS, 8.0, 47.0, 0.1, 0.1, compression=comp,
                                    payload_hook=lambda raw, enc=enc: enc(raw + b"\0" * 200_000))
                with self.assertRaises(LimitError):
                    GeoTiff(BytesSource(data)).pixel(0, 0)
        with self.assertRaises(LimitError):
            lzw_decode(lzw_encode(b"x" * 5000), max_out=1000)

    def test_block_size_validated_before_payload_read(self):
        data = make_geotiff(self.VALS, 8.0, 47.0, 0.1, 0.1, tile=(16, 16),
                            tag_overrides={322: (3, [4096]), 323: (3, [4096])})
        with self.assertRaises(LimitError):
            GeoTiff(BytesSource(data))
        data = make_geotiff(self.VALS, 8.0, 47.0, 0.1, 0.1, tag_overrides={256: (4, [5_000_000])})
        with self.assertRaises(LimitError):
            GeoTiff(BytesSource(data))

    def test_unused_tags_skipped_and_tag_budget(self):
        big = 2 * 1024 * 1024
        data = make_geotiff(self.VALS, 8.0, 47.0, 0.1, 0.1, tag_overrides={50000: (7, b"\x01" * big)})
        src = BytesSource(data)
        reads = []
        orig = src.read
        src.read = lambda off, n: (reads.append(n), orig(off, n))[1]
        t = GeoTiff(src)
        self.assertNotIn(50000, t.tags)
        self.assertLess(max(reads), big)
        with mock.patch.object(tiff_mod, "MAX_TAG_BYTES", 16), self.assertRaises(LimitError):
            GeoTiff(BytesSource(data))

    def test_block_cache_bounded_by_bytes(self):
        vals = [[float(r + c) for c in range(64)] for r in range(64)]
        t = GeoTiff(BytesSource(make_geotiff(vals, 8.0, 47.0, 0.1, 0.1, tile=(16, 16))))
        t.max_cache_bytes = 2 * 16 * 16 * 4
        for r in range(0, 64, 4):
            for c in range(0, 64, 4):
                self.assertEqual(t.pixel(c, r), float(r + c))
        self.assertLessEqual(t._cache_bytes, t.max_cache_bytes)
        self.assertLessEqual(len(t._blocks), 2)

    def test_window_check_runs_when_reading(self):
        lat0, lon0 = ORIGIN
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "w.tif")
        with open(path, "wb") as f:
            f.write(make_geotiff([[400.0] * 40 for _ in range(40)], lon0 - 0.02, lat0 + 0.02, 0.001, 0.001))
        self.assertIsNotNone(load_local_elevation(Area(lat0, lon0, 300, 300), path, 10.0))
        with mock.patch.object(tiff_mod, "MAX_RASTER_PIXELS_READ", 10), self.assertRaises(LimitError):
            load_local_elevation(Area(lat0, lon0, 300, 300), path, 10.0)


def write_small_asc(path, nodata_token, center_token, n=41, cell=0.0005, extra=""):
    lat0, lon0 = ORIGIN
    half = (n - 1) / 2 * cell
    rows = []
    for r in range(n):
        rows.append(" ".join(center_token if (r, c) == (n // 2, n // 2) else "400.0" for c in range(n)))
    with open(path, "w", encoding="ascii") as f:
        f.write(f"ncols {n}\nnrows {n}\nxllcenter {lon0 - half}\nyllcenter {lat0 - half}\ncellsize {cell}\n"
                f"NODATA_value {nodata_token}\n" + "\n".join(rows) + "\n" + extra)
    return path


class NoDataPrecisionTest(unittest.TestCase):
    """Finding 4: float32-rounded and non-finite NoData always fails, never fills."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.lat0, self.lon0 = ORIGIN

    def tif(self, special, nodata):
        vals = [[400.0] * 40 for _ in range(40)]
        vals[20][20] = special
        path = os.path.join(self.tmp, f"t{len(os.listdir(self.tmp))}.tif")
        with open(path, "wb") as f:
            f.write(make_geotiff(vals, self.lon0 - 0.02, self.lat0 + 0.02, 0.001, 0.001, nodata=nodata))
        return path

    def test_float32_max_sentinel_matches(self):
        path = self.tif(-3.4028235e38, "-3.4028235e+38")
        with open(path, "rb") as f:
            t = GeoTiff(BytesSource(f.read()))
        self.assertIsNone(t.pixel(20, 20))
        with self.assertRaises(NoDataError):
            load_local_elevation(Area(self.lat0, self.lon0, 1000, 1000), path, 10.0)

    def test_non_finite_tiff_samples_are_nodata(self):
        for special in (math.inf, -math.inf, math.nan):
            with self.subTest(special=special), self.assertRaises(NoDataError):
                load_local_elevation(Area(self.lat0, self.lon0, 1000, 1000), self.tif(special, None), 10.0)

    def test_ascii_nan_sentinel_and_non_finite_values(self):
        for nod, centre in (("nan", "nan"), ("NaN", "NaN"), ("-9999", "inf"), ("-9999", "nan")):
            with self.subTest(nodata=nod, value=centre):
                path = write_small_asc(os.path.join(self.tmp, "a.asc"), nod, centre)
                with self.assertRaises(NoDataError):
                    load_local_elevation(Area(self.lat0, self.lon0, 600, 600), path, 10.0)


class OverpassValidationTest(unittest.TestCase):
    """Finding 5: remarks anywhere reject the result; cache only validated responses."""

    GOOD = osm_doc('<node id="1" lat="47.0" lon="8.0"/>')
    PARTIAL = osm_doc('<node id="1" lat="47.0" lon="8.0"/>' + "<!-- pad -->" * 600
                      + "<remark> runtime error: Query timed out </remark>")

    def setUp(self):
        self.area = Area(*ORIGIN, 200, 200)

    def test_remark_late_in_document_rejected_and_not_cached(self):
        self.assertGreater(self.PARTIAL.index(b"<remark>"), 4096)
        cache = MemoryCache()
        with self.assertRaises(FormatError):
            fetch_overpass(self.area, HttpClient(ScriptedTransport(Response(200, self.PARTIAL))), cache=cache)
        self.assertEqual(cache.puts, [])

    def test_cached_partial_is_revalidated_and_replaced(self):
        cache = MemoryCache()
        fetch_overpass(self.area, HttpClient(ScriptedTransport(Response(200, self.GOOD))), cache=cache)
        key = cache.puts[0][:2]
        cache.store[key] = self.PARTIAL  # poisoned entry
        tr = ScriptedTransport(Response(200, self.GOOD))
        data = fetch_overpass(self.area, HttpClient(tr), cache=cache)
        self.assertEqual(len(tr.requests), 1)
        self.assertFalse(data.source["from_cache"])
        self.assertEqual(cache.store[key], self.GOOD)
        data = fetch_overpass(self.area, HttpClient(ScriptedTransport()), cache=cache)
        self.assertTrue(data.source["from_cache"])


class OverpassBuildingRelationTest(unittest.TestCase):
    """Round 7: type=building relations (no building tags) are fetched, with their members, and
    an Overpass import classifies like a local XML import of the same data."""

    def response(self):
        b = OsmBuilder()
        big = b.way(rect(0, 0, 60, 60), {"building": "yes", "height": "20"}, closed=True)
        small = b.way(rect(0, 0, 20, 20), {"building": "yes", "height": "20"}, closed=True)
        part = b.way(rect(0, 0, 4, 4), {"building:part": "yes", "height": "20"}, closed=True)
        rid = b._next()
        b.relations.append((rid, [("way", big, "outline"), ("way", part, "part")], {"type": "building"}))
        return b.xml().encode("utf-8"), *(f"osm:way/{x}" for x in (big, small, part))

    def test_query_selects_building_relations_and_their_members(self):
        q = osm_mod.overpass_query(1.0, 2.0, 3.0, 4.0)
        bb = "(1.0000000,2.0000000,3.0000000,4.0000000)"
        self.assertIn(f'relation["type"="building"]{bb};', q)
        self.assertIn('rel(bw.feat)["type"="building"];', q)  # parents of building:part ways
        self.assertIn('rel(br.feat)["type"="building"];', q)  # parents of building:part relations
        self.assertIn("rel(r.bldg);", q)  # member relations (multipolygon outlines / parts)
        # the relations feed the final recursion that fetches member ways and their nodes
        self.assertLess(q.index("->.bldg;"), q.index("(.feat; .bldg; rel(r.bldg););"))
        self.assertLess(q.index("(.feat; .bldg; rel(r.bldg););"), q.index("(._;>;);"))
        self.assertTrue(q.startswith(f"[out:xml][timeout:90][maxsize:{osm_mod.MAX_OSM_BYTES}];"))
        self.assertTrue(q.endswith("out body qt;\n"))

    def test_fetch_to_classification_honours_declared_ownership(self):
        body, big, small, part = self.response()
        area = Area(*ORIGIN, AREA_W, AREA_H)
        tr = ScriptedTransport(Response(200, body))
        cache = MemoryCache()
        data = fetch_overpass(area, HttpClient(tr), cache=cache)
        sent = urllib.parse.parse_qs(tr.requests[0][3].decode("ascii"))["data"][0]
        self.assertIn('relation["type"="building"](', sent)
        self.assertIn('relation["type"="building"](', cache.puts[0][1])  # new query text -> new cache key
        self.assertEqual(data.source["query"], sent)
        cl = classify(data, area)
        # declared: the relation names ``big``; spatial matching alone would pick ``small``
        self.assertEqual(cl.outline_for, {part: [big]})
        self.assertEqual(cl.replaced_outlines, [big])
        local = classify(parse_osm_xml(body), area)
        self.assertEqual((local.outline_for, [f.id for f in local.buildings]),
                         (cl.outline_for, [f.id for f in cl.buildings]))

class OsmClassifyTest(unittest.TestCase):
    def setUp(self):
        self.area = Area(*ORIGIN, AREA_W, AREA_H)

    def classify(self, b):
        return classify(parse_osm_xml(b.xml()), self.area)

    # Finding 6
    def test_tagged_outer_way_does_not_fill_courtyard(self):
        b = OsmBuilder()
        rid = b.multipolygon(rect(0, 0, 40, 40), [rect(0, 0, 16, 16)[::-1]], {"building": "yes"},
                             outer_tags={"building": "yes", "highway": "footway"})
        outer = b.relations[-1][1][0][1]
        cl = self.classify(b)
        self.assertEqual([f.id for f in cl.buildings], [f"osm:relation/{rid}"])
        self.assertEqual(len(cl.buildings[0].geometry.holes), 1)
        self.assertFalse(any(f.geometry.contains(0, 0) for f in cl.buildings))
        self.assertIn(f"osm:way/{outer}", ids_of(cl.roads))  # independent role kept

    def test_missing_or_unclosed_inner_skips_relation(self):
        for case in ("missing", "unclosed"):
            with self.subTest(case=case):
                b = OsmBuilder()
                o = b.way(rect(0, 0, 40, 40), closed=True)
                inner = 999999 if case == "missing" else b.way(rect(0, 0, 16, 16)[::-1])
                b.relations.append((5, [("way", o, "outer"), ("way", inner, "inner")],
                                    {"type": "multipolygon", "building": "yes"}))
                cl = self.classify(b)
                self.assertEqual(cl.buildings, [])
                self.assertIn("osm:relation/5", ids_of(cl.invalid))

    # Finding 12
    def test_passages_bridges_tunnels_reported_before_exclusions(self):
        b = OsmBuilder()
        corridor = b.way([(-50, 0), (50, 0)], {"highway": "corridor", "tunnel": "building_passage"})
        park = b.way(rect(60, 60, 30, 30), {"leisure": "park", "bridge": "yes"}, closed=True)
        culvert = b.way(rect(-60, -60, 30, 30), {"natural": "water", "tunnel": "culvert"}, closed=True)
        cl = self.classify(b)
        unsup = {u["id"]: u["reason"] for u in cl.unsupported}
        self.assertEqual([f.id for f in cl.passages], [f"osm:way/{corridor}"])   # routed to the passage stage
        self.assertIn("bridge", unsup[f"osm:way/{park}"])
        self.assertIn("tunnel", unsup[f"osm:way/{culvert}"])
        self.assertEqual(cl.roads, [])
        self.assertEqual(cl.areas, [])


class OsmParserSafetyTest(unittest.TestCase):
    """Finding 11: parser-level DTD/entity rejection (any encoding); limits enforced while parsing."""

    def test_dtd_rejected_in_any_encoding(self):
        doc = '<?xml version="1.0" encoding="{}"?><!DOCTYPE osm [<!ENTITY a "aaaa">]><osm>&a;</osm>'
        for enc in ("utf-8", "utf-16", "utf-16-le"):
            with self.subTest(enc=enc), self.assertRaises(FormatError):
                parse_osm_xml(doc.format(enc.upper()).encode(enc))
        with self.assertRaises(MapBuilderError):
            parse_osm_xml(b'<!DOCTYPE osm SYSTEM "http://evil.example/x.dtd"><osm/>')

    def test_limits_enforced_during_parse(self):
        nodes = "".join(f'<node id="{i}" lat="47" lon="8"/>' for i in range(10))
        # The trailing garbage would be a FormatError; hitting LimitError first proves streaming enforcement.
        doc = osm_doc(nodes)[:-6] + b"<<<garbage"
        with self.assertRaises(LimitError):
            parse_osm_xml(doc, max_elements=5)
        deep = osm_doc("<a>" * 30 + "</a>" * 30)
        with self.assertRaises(LimitError):
            parse_osm_xml(deep)
        self.assertEqual(len(parse_osm_xml(osm_doc(nodes)).nodes), 10)


class RangeValidationTest(unittest.TestCase):
    """Finding 7: Content-Range validated; full response always charged."""

    def fetch(self, resp, rng, **kw):
        return HttpClient(ScriptedTransport(resp), **kw).fetch("https://h.example/f", byte_range=rng)

    def test_content_range_validation(self):
        body = bytes(range(100))
        bad = [Response(206, body[10:20]),                                            # missing header
               Response(206, body[11:21], {"Content-Range": "bytes 11-20/100"}),      # wrong start
               Response(206, body[10:15], {"Content-Range": "bytes 10-19/100"}),      # length mismatch
               Response(206, body[10:15], {"Content-Range": "bytes 10-14/100"}),      # short, not at EOF
               Response(206, body[10:25], {"Content-Range": "bytes 10-24/100"})]      # more than asked
        for resp in bad:
            with self.subTest(cr=resp.headers), self.assertRaises(NetworkError):
                self.fetch(resp, (10, 10))
        ok = self.fetch(Response(206, body[95:], {"content-range": "bytes 95-99/100"}), (95, 10))
        self.assertEqual(ok, body[95:])  # short read only at a verified EOF
        with self.assertRaises(NetworkError):
            self.fetch(Response(206, body), None)  # 206 without a Range request

    def test_ignored_range_charges_full_body(self):
        body = bytes(200)
        c = HttpClient(ScriptedTransport(Response(200, body)))
        self.assertEqual(len(c.fetch("https://h.example/f", byte_range=(10, 5))), 5)
        self.assertEqual(c.bytes_downloaded, 200)
        with self.assertRaises(LimitError):
            self.fetch(Response(200, body), (10, 5), max_bytes=100)

    def test_range_source_budget_counts_full_response(self):
        data = bytes(400_000)
        tr = FakeTransport({"https://h.example/f.tif": data}, ignore_range=True)
        src = HttpRangeSource(HttpClient(tr), "https://h.example/f.tif", "f", max_total_bytes=500_000)
        self.assertEqual(src.fetched, 400_000)
        with self.assertRaises(LimitError):
            src.read(300_000, 1000)


class DeadlineTest(unittest.TestCase):
    """Finding 8: a total monotonic deadline across connect/redirects/body."""

    def test_slow_body_hits_total_deadline(self):
        clock = FakeClock()
        resp = FakeHttpResponse([b"x" * 10] * 100, clock=clock, step=10.0)
        t = UrllibTransport(total_timeout=25.0, opener=FakeOpener(resp), clock=clock)
        with self.assertRaises(NetworkError) as cm:
            t.request("GET", "https://h.example/a?k=SECRET", {}, None, 5.0, 10_000)
        self.assertIn("time limit", str(cm.exception))
        self.assertNotIn("SECRET", str(cm.exception))
        self.assertTrue(resp.closed)

    def test_fast_body_ok_and_defaults(self):
        clock = FakeClock()
        t = UrllibTransport(opener=FakeOpener(FakeHttpResponse([b"ab", b"cd"], clock=clock, step=0.1)), clock=clock)
        self.assertEqual(t.request("GET", "https://h.example/", {}, None, 5.0, 100).body, b"abcd")
        self.assertEqual(HttpClient(timeout=10).total_timeout, 40)
        self.assertEqual(HttpClient(timeout=10).transport.total_timeout, 40)

    def test_client_enforces_deadline_for_any_transport(self):
        clock = FakeClock()

        class Slow:
            def request(self, *a):
                clock.t += 100
                return Response(200, b"ok")
        c = HttpClient(Slow(), timeout=5, total_timeout=20)
        c.clock = clock
        with self.assertRaises(NetworkError):
            c.fetch("https://h.example/")


class CachePermissionTest(unittest.TestCase):
    """Finding 9: caching only for default public endpoints or explicit override; namespaced keys."""

    NAME = "Copernicus_DSM_COG_10_N47_00_E008_00_DEM"

    def run_cop(self, base, **kw):
        tr = FakeTransport({f"{base}/{self.NAME}/{self.NAME}.tif": CopernicusTest().tile()})
        cache = MemoryCache()
        fetch_copernicus(Area(47.5, 8.5, 400, 400), HttpClient(tr), 20.0, cache, base, **kw)
        return cache

    def test_copernicus(self):
        self.assertEqual(self.run_cop("https://mirror.example/cop").gets, [])
        cache = self.run_cop(COPERNICUS_BASE_URL)
        self.assertTrue(cache.puts)
        cache = self.run_cop("https://mirror.example/cop", allow_cache_override=True, cache_dataset_id="mirror-1")
        self.assertTrue(all(k.startswith(f"copernicus-dem-glo30-public|override:mirror-1|{self.NAME}#")
                            for _, k, _ in cache.puts))

    def test_overpass(self):
        area = Area(*ORIGIN, 200, 200)
        good = OverpassValidationTest.GOOD
        cache = MemoryCache()
        fetch_overpass(area, HttpClient(ScriptedTransport(Response(200, good))), "https://op.example/api", cache)
        self.assertEqual((cache.gets, cache.puts), ([], []))
        fetch_overpass(area, HttpClient(ScriptedTransport(Response(200, good))), "https://op.example/api", cache,
                       allow_cache_override=True, cache_dataset_id="op-mirror")
        self.assertTrue(cache.puts[0][1].startswith("openstreetmap-overpass-xml|override:op-mirror\n"))
        fetch_overpass(area, HttpClient(ScriptedTransport(Response(200, good))), DEFAULT_OVERPASS_URL, cache)
        self.assertEqual(len(cache.puts), 2)


class BoundedReadsTest(unittest.TestCase):
    """Finding 10: chunked hashing, incremental ASCII parsing, size-checked cache reads."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def test_chunked_hash(self):
        path = os.path.join(self.tmp, "h.bin")
        data = os.urandom(10_000)
        with open(path, "wb") as f:
            f.write(data)
        self.assertEqual(dem_mod._sha256_file(path, chunk=7), hashlib.sha256(data).hexdigest())

    def test_ascii_token_limits(self):
        crs = parse_crs("EPSG:4326")
        too_many = write_small_asc(os.path.join(self.tmp, "m.asc"), "-9999", "1", n=5, extra="1 2 3\n")
        with mock.patch.object(AsciiGrid, "CHUNK", 16), self.assertRaises(FormatError) as cm:
            AsciiGrid(too_many, crs)
        self.assertIn("found more", str(cm.exception))
        long_tok = write_small_asc(os.path.join(self.tmp, "l.asc"), "-9999", "1" * 500, n=5)
        with self.assertRaises(FormatError):
            AsciiGrid(long_tok, crs)
        with mock.patch.object(AsciiGrid, "CHUNK", 16):
            g = AsciiGrid(write_small_asc(os.path.join(self.tmp, "ok.asc"), "-9999", "12.5", n=5), crs)
        self.assertEqual(g.pixel(2, 2), 12.5)

    def test_cache_reads_are_size_checked(self):
        DiskCache(self.tmp, max_entry_bytes=1000).put("ns", "k", b"x" * 100, {"a": 1})
        self.assertEqual(DiskCache(self.tmp, max_entry_bytes=1000).get("ns", "k"), b"x" * 100)
        self.assertIsNone(DiskCache(self.tmp, max_entry_bytes=50).get("ns", "k"))
        c = DiskCache(self.tmp)
        with open(c._path("ns", "k") + ".json", "w", encoding="utf-8") as f:
            json.dump({"sha256": hashlib.sha256(b"x" * 100).hexdigest(), "pad": "p" * MAX_META_BYTES}, f)
        self.assertIsNone(c.get("ns", "k"))
        c.put("ns", "big", b"y", {"pad": "p" * MAX_META_BYTES})
        self.assertIsNone(c.get("ns", "big"))
        self.assertFalse(os.path.exists(c._path("ns", "big") + ".bin"))


# --- review round 3 ----------------------------------------------------------

class _BombBody(io.BytesIO):
    """A redirect body that must never be read (reading it would bypass the byte cap and deadline)."""

    msg = "Found"

    def __init__(self):
        super().__init__(b"x" * 64)
        self.read_calls = 0

    def read(self, *args):
        self.read_calls += 1
        raise AssertionError("redirect body was read")

    readline = read


class _FakeNet(urllib.request.BaseHandler):
    """Network-free https handler: /start redirects to /final; advances a fake clock per hop."""

    handler_order = 100

    def __init__(self, clock, step):
        self.clock, self.step = clock, step
        self.timeouts, self.bombs = [], []

    def https_open(self, req):
        import email.message
        import urllib.response
        self.timeouts.append(req.timeout)
        self.clock.t += self.step
        hdrs = email.message.Message()
        if "/start" in req.full_url:
            hdrs["Location"] = "https://h.example/final"
            bomb = _BombBody()
            self.bombs.append(bomb)
            return urllib.response.addinfourl(bomb, hdrs, req.full_url, 302)
        resp = urllib.response.addinfourl(io.BytesIO(b"payload"), hdrs, req.full_url, 200)
        resp.msg = "OK"
        return resp


class RedirectBodyAndDeadlineTest(unittest.TestCase):
    """Round 3, finding 1: redirect bodies are closed unread; all hops share one absolute deadline."""

    def transport(self, step):
        clock = FakeClock()
        net = _FakeNet(clock, step)
        real = urllib.request.build_opener
        patch = mock.patch.object(urllib.request, "build_opener", lambda *h: real(*h, net))
        patch.start()
        self.addCleanup(patch.stop)
        return UrllibTransport(total_timeout=25.0, clock=clock), net

    def test_redirect_body_closed_unread_and_next_hop_gets_remaining_time(self):
        t, net = self.transport(step=10.0)
        resp = t.request("GET", "https://h.example/start", {}, None, 20.0, 1000)
        self.assertEqual(resp.body, b"payload")
        self.assertEqual(net.bombs[0].read_calls, 0)
        self.assertTrue(net.bombs[0].closed)
        self.assertEqual(net.timeouts, [20.0, 15.0])  # second hop limited to the 15 s left of 25 s

    def test_deadline_expired_before_following_redirect(self):
        t, net = self.transport(step=30.0)
        with self.assertRaises(NetworkError) as cm:
            t.request("GET", "https://h.example/start?k=SECRET", {}, None, 20.0, 1000)
        self.assertIn("time limit", str(cm.exception))
        self.assertNotIn("SECRET", str(cm.exception))
        self.assertEqual(len(net.timeouts), 1)  # the redirect target was never opened
        self.assertEqual(net.bombs[0].read_calls, 0)
        self.assertTrue(net.bombs[0].closed)


class RejectedMultipolygonOuterTest(unittest.TestCase):
    """Round 3, finding 2: outers of rejected multipolygons never become solid buildings."""

    def setUp(self):
        self.area = Area(*ORIGIN, AREA_W, AREA_H)

    def check(self, b, outer):
        cl = classify(parse_osm_xml(b.xml()), self.area)
        self.assertEqual(cl.buildings, [])
        self.assertFalse(any(f.geometry.contains(0, 0) for f in cl.buildings + cl.areas))
        reasons = {i["id"]: i["reason"] for i in cl.invalid}
        self.assertIn(f"osm:way/{outer}", reasons)  # reported, not silently dropped
        self.assertIn(f"osm:way/{outer}", ids_of(cl.roads))  # independent role kept
        return reasons[f"osm:way/{outer}"]

    def test_rejected_relation_suppresses_tagged_outer(self):
        outer_tags = {"building": "yes", "highway": "footway"}
        for case in ("missing", "unclosed", "outside"):
            with self.subTest(case=case):
                b = OsmBuilder()
                o = b.way(rect(0, 0, 40, 40), outer_tags, closed=True)
                if case == "missing":
                    inner = 999999
                elif case == "unclosed":
                    inner = b.way(rect(0, 0, 16, 16)[::-1])
                else:  # inner ring lies outside the outer: relation is invalid
                    inner = b.way(rect(100, 100, 10, 10)[::-1], closed=True)
                b.relations.append((7, [("way", o, "outer"), ("way", inner, "inner")],
                                    {"type": "multipolygon", "building": "yes"}))
                reason = self.check(b, o)
                self.assertIn("osm:relation/7", reason)

    def test_old_style_untagged_relation_with_holes_suppresses_outer(self):
        b = OsmBuilder()
        rid = b.multipolygon(rect(0, 0, 40, 40), [rect(0, 0, 16, 16)[::-1]], {},
                             outer_tags={"building": "yes", "highway": "footway"})
        outer = b.relations[-1][1][0][1]
        self.assertIn(f"osm:relation/{rid}", self.check(b, outer))

    def test_other_family_outer_is_kept(self):
        b = OsmBuilder()
        o = b.way(rect(0, 0, 40, 40), {"building": "yes"}, closed=True)
        b.relations.append((8, [("way", o, "outer"), ("way", 999999, "inner")],
                            {"type": "multipolygon", "landuse": "grass"}))
        cl = classify(parse_osm_xml(b.xml()), self.area)
        self.assertEqual([f.id for f in cl.buildings], [f"osm:way/{o}"])


class EndpointRedactionTest(unittest.TestCase):
    """Round 3, finding 3: endpoint paths never reach errors, provenance, cache keys or metadata."""

    TOKEN = "S3cr3tPathToken"
    NAME = "Copernicus_DSM_COG_10_N47_00_E008_00_DEM"

    def test_redact_is_origin_only(self):
        self.assertEqual(redact(f"https://u:p@H.example:8443/api/{self.TOKEN}/x?q=1#f"), "https://h.example:8443")
        self.assertEqual(redact("not a url"), "<invalid url>")
        self.assertEqual(redact("https://h.example:99999/x"), "<invalid url>")

    def test_error_messages_omit_path(self):
        with self.assertRaises(NetworkError) as cm:
            HttpClient(FakeTransport(status=500)).fetch(f"https://h.example/{self.TOKEN}/f")
        self.assertNotIn(self.TOKEN, str(cm.exception))
        self.assertNotIn(self.TOKEN, str(cm.exception.url))

    def test_overpass_override_requires_dataset_id_and_never_persists_path(self):
        area = Area(*ORIGIN, 200, 200)
        url = f"https://op.example/{self.TOKEN}/api/interpreter"
        good = OverpassValidationTest.GOOD
        with self.assertRaises(ValueError):
            fetch_overpass(area, HttpClient(ScriptedTransport()), url, MemoryCache(), allow_cache_override=True)
        with self.assertRaises(ValueError):  # dataset id copied from the secret path
            fetch_overpass(area, HttpClient(ScriptedTransport()), url, MemoryCache(), allow_cache_override=True,
                           cache_dataset_id=self.TOKEN)
        cache = MemoryCache()
        data = fetch_overpass(area, HttpClient(ScriptedTransport(Response(200, good))), url, cache,
                              allow_cache_override=True, cache_dataset_id="team-mirror")
        self.assertEqual(data.source["endpoint"], "https://op.example")
        dumped = json.dumps([data.source, cache.puts, [k for k in cache.store]])
        self.assertNotIn(self.TOKEN, dumped)
        self.assertNotIn("/api", dumped)
        default = fetch_overpass(area, HttpClient(ScriptedTransport(Response(200, good))))
        self.assertEqual(default.source["endpoint"], DEFAULT_OVERPASS_URL)  # known public label kept

    def test_copernicus_override_cache_keys_and_metadata_omit_path(self):
        base = f"https://mirror.example/{self.TOKEN}/cop"
        tr = FakeTransport({f"{base}/{self.NAME}/{self.NAME}.tif": CopernicusTest().tile()})
        cache = MemoryCache()
        g = fetch_copernicus(Area(47.5, 8.5, 400, 400), HttpClient(tr), 20.0, cache, base,
                             allow_cache_override=True, cache_dataset_id="team-mirror")
        self.assertTrue(cache.puts)
        self.assertNotIn(self.TOKEN, json.dumps([g.provenance, cache.puts]))
        with self.assertRaises(ValueError):
            fetch_copernicus(Area(47.5, 8.5, 400, 400), HttpClient(tr), 20.0, MemoryCache(), base,
                             allow_cache_override=True)
        # Without a cache, an override needs no dataset id.
        self.assertIsNotNone(fetch_copernicus(Area(47.5, 8.5, 400, 400), HttpClient(tr), 20.0, None, base))


class FlakyTransport(FakeTransport):
    """First request for each URL gets a non-TIFF 200 (e.g. a provider error page); later ones are real."""

    def __init__(self, files):
        super().__init__(files)
        self.seen = set()

    def request(self, method, url, headers, data, timeout, max_bytes):
        if url not in self.seen:
            self.seen.add(url)
            self.requests.append((method, url, dict(headers), data))
            return Response(200, b"<html>Service temporarily unavailable</html>")
        return super().request(method, url, headers, data, timeout, max_bytes)


class RangeCacheValidationTest(unittest.TestCase):
    """Round 3, finding 4: ranges are cached only after TIFF validation; bad entries are evicted."""

    NAME = CachePermissionTest.NAME
    BASE = COPERNICUS_BASE_URL

    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.cache = DiskCache(td.name)
        self.root = td.name
        self.url = f"{self.BASE}/{self.NAME}/{self.NAME}.tif"

    def fetch(self, transport):
        return fetch_copernicus(Area(47.5, 8.5, 400, 400), HttpClient(transport), 20.0, self.cache)

    def cached_files(self):
        return [f for _, _, fs in os.walk(self.root) for f in fs]

    def test_non_tiff_response_not_cached_then_valid_import_succeeds(self):
        tr = FlakyTransport({self.url: CopernicusTest().tile()})
        with self.assertRaises(FormatError):
            self.fetch(tr)
        self.assertEqual(self.cached_files(), [])
        g = self.fetch(tr)  # same cache: must not replay the error page
        self.assertIsNotNone(g)
        self.assertTrue(self.cached_files())
        offline = FakeTransport({})
        self.assertIsNotNone(self.fetch(offline))  # now served from the validated cache
        self.assertEqual(offline.requests, [])

    def test_poisoned_cache_entry_is_evicted_and_refetched_once(self):
        key = f"copernicus-dem-glo30-public|{self.BASE}|{self.NAME}#0+{HttpRangeSource.HEAD_BYTES}"
        self.cache.put("ranges", key, b"<html>stale error page</html>")
        tr = FakeTransport({self.url: CopernicusTest().tile()})
        self.assertIsNotNone(self.fetch(tr))
        self.assertTrue(tr.requests)
        self.assertNotEqual(self.cache.get("ranges", key)[:2], b"<h")

    def test_corrupt_block_invalidates_cached_ranges(self):
        data = make_geotiff(TiffBoundsTest.VALS, 8.0, 47.0, 0.1, 0.1, compression=8,
                            payload_hook=lambda raw: b"\x78\x9cnot-deflate")
        cache = MemoryCache()
        src = HttpRangeSource(HttpClient(FakeTransport({"https://h.example/t.tif": data})),
                              "https://h.example/t.tif", "t", cache=cache)
        t = GeoTiff(src)
        self.assertTrue(cache.store)  # header/IFD validated -> committed
        with self.assertRaises(FormatError):
            t.pixel(0, 0)
        self.assertEqual(cache.store, {})

    def test_wrong_crs_tile_is_evicted_after_provider_recovers(self):
        utm = make_geotiff([[1.0] * 8 for _ in range(8)], 500000.0, 5210000.0, 10.0, 10.0, epsg=32632)
        tr = FakeTransport({self.url: utm})
        with self.assertRaises(FormatError):
            self.fetch(tr)
        tr.files[self.url] = CopernicusTest().tile()
        self.assertIsNotNone(self.fetch(tr))  # same cache: the UTM header must not be replayed


class RoundFourTest(unittest.TestCase):
    def test_nested_inner_ring_goes_to_smallest_enclosing_outer(self):
        b = OsmBuilder()
        rings = [rect(0, 0, 80, 80), rect(0, 0, 60, 60)[::-1], rect(0, 0, 40, 40), rect(0, 0, 20, 20)[::-1]]
        ids = [b.way(r, closed=True) for r in rings]
        roles = ["outer", "inner", "outer", "inner"]
        b.relations.append((7, [("way", i, r) for i, r in zip(ids, roles)],
                            {"type": "multipolygon", "building": "yes"}))
        cl = classify(parse_osm_xml(b.xml()), Area(*ORIGIN, AREA_W, AREA_H))
        polys = sorted((f.geometry for f in cl.buildings), key=lambda p: abs(ring_area(p.outer)))
        self.assertEqual([len(p.holes) for p in polys], [1, 1])
        self.assertFalse(any(p.contains(0, 0) for p in polys))  # inner courtyard stays open
        self.assertTrue(any(p.contains(15, 0) for p in polys))  # ring between 10 m and 20 m is solid
        self.assertFalse(any(p.contains(25, 0) for p in polys))  # outer courtyard (20-30 m) stays open

    def test_body_read_uses_single_receive_reads(self):
        clock = FakeClock()

        class Read1Only(FakeHttpResponse):
            def read(self, n=-1):
                raise AssertionError("buffered read must not be used")

            def read1(self, n=-1):
                return FakeHttpResponse.read(self, n)
        resp = Read1Only([b"x" * 10] * 100, clock=clock, step=10.0)
        t = UrllibTransport(total_timeout=25.0, opener=FakeOpener(resp), clock=clock)
        with self.assertRaises(NetworkError):
            t.request("GET", "https://h.example/", {}, None, 5.0, 10_000)

    def test_dribbled_chunk_framing_hits_deadline_on_a_real_socket(self):
        import socket as socket_mod
        import threading
        import time as time_mod
        srv = socket_mod.socket()
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        self.addCleanup(srv.close)
        stop = threading.Event()

        def serve():
            conn, _ = srv.accept()
            with conn:
                conn.recv(4096)
                conn.sendall(b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n")
                while not stop.is_set():  # endless chunk-size line, one byte per 50 ms
                    try:
                        conn.sendall(b"0")
                    except OSError:
                        return
                    time_mod.sleep(0.05)
        th = threading.Thread(target=serve, daemon=True)
        th.start()
        self.addCleanup(stop.set)
        port = srv.getsockname()[1]
        start = time_mod.monotonic()
        with self.assertRaises(NetworkError) as cm:
            UrllibTransport(total_timeout=0.6).request("GET", f"http://127.0.0.1:{port}/", {}, None, 0.4, 10_000)
        self.assertLess(time_mod.monotonic() - start, 3.0)
        self.assertIn("time limit", str(cm.exception))

    def test_blocked_dns_resolution_returns_at_deadline(self):
        import socket as socket_mod
        import threading
        import time as time_mod
        release = threading.Event()
        self.addCleanup(release.set)
        real = socket_mod.getaddrinfo

        def blocked(*a, **k):
            release.wait(5.0)
            return real(*a, **k)
        with mock.patch("socket.getaddrinfo", blocked):
            start = time_mod.monotonic()
            with self.assertRaises(NetworkError) as cm:
                UrllibTransport(total_timeout=0.3).request("GET", "http://resolver-stall.invalid/", {}, None,
                                                           10.0, 1000)
            elapsed = time_mod.monotonic() - start
            release.set()
        self.assertLess(elapsed, 1.0)
        self.assertIn("time limit", str(cm.exception))

    def test_stalled_workers_are_capped(self):
        import socket as socket_mod
        import threading
        from map_builder.core import http as http_mod
        release = threading.Event()
        self.addCleanup(release.set)
        real = socket_mod.getaddrinfo

        def blocked(*a, **k):
            release.wait(5.0)
            return real(*a, **k)

        def alive():
            return sum(t.name == "map-builder-http" and t.is_alive() for t in threading.enumerate())
        base = alive()
        with mock.patch("socket.getaddrinfo", blocked):
            msgs = []
            for _ in range(http_mod.MAX_OUTSTANDING_WORKERS + 2):
                with self.assertRaises(NetworkError) as cm:
                    UrllibTransport(total_timeout=0.05).request("GET", "http://stall.invalid/", {}, None, 1.0, 10)
                msgs.append(str(cm.exception))
            self.assertLessEqual(alive() - base, http_mod.MAX_OUTSTANDING_WORKERS)
            self.assertIn("too many earlier requests", msgs[-1])
            release.set()
            for t in threading.enumerate():
                if t.name == "map-builder-http":
                    t.join(5.0)
        self.assertEqual(alive(), 0)
        self.assertEqual(http_mod._WORKER_SLOTS._value, http_mod.MAX_OUTSTANDING_WORKERS)  # all slots released

    def test_stalled_tls_handshake_hits_deadline(self):
        import socket as socket_mod
        import threading
        import time as time_mod
        srv = socket_mod.socket()
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        self.addCleanup(srv.close)
        stop = threading.Event()
        self.addCleanup(stop.set)

        def serve():  # TLS handshake record header announcing 16 KiB, then one byte per 50 ms
            conn, _ = srv.accept()
            with conn:
                conn.recv(4096)
                try:
                    conn.sendall(b"\x16\x03\x03\x40\x00")
                    while not stop.is_set():
                        conn.sendall(b"\x00")
                        time_mod.sleep(0.05)
                except OSError:
                    return
        threading.Thread(target=serve, daemon=True).start()
        port = srv.getsockname()[1]
        start = time_mod.monotonic()
        with self.assertRaises(NetworkError) as cm:  # each receive makes progress: only the watchdog stops it
            UrllibTransport(total_timeout=0.6).request("GET", f"https://127.0.0.1:{port}/", {}, None, 10.0, 1000)
        self.assertLess(time_mod.monotonic() - start, 3.0)
        self.assertIn("time limit", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
