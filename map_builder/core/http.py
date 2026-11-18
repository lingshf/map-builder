"""Bounded HTTP client (stdlib urllib) with explicit failure mapping.

* Every request has a timeout and a hard byte cap.
* Credentials are never placed in error messages or logs: callers pass them via
  ``headers`` and :func:`redact` strips query/userinfo from URLs before they
  are shown anywhere.
* A transport may be injected (``Transport`` protocol) so tests never touch
  the network.
"""

import urllib.error
import urllib.parse
import urllib.request

from . import GENERATOR_NAME, GENERATOR_VERSION
from .errors import AuthError, CoverageError, LimitError, NetworkError

USER_AGENT = f"{GENERATOR_NAME}/{GENERATOR_VERSION} (Blender add-on; +https://github.com/lingshf/map-builder)"
DEFAULT_TIMEOUT_S = 60.0
DEFAULT_MAX_BYTES = 64 * 1024 * 1024
SENSITIVE_HEADERS = {"authorization", "x-api-key", "cookie"}


def redact(url):
    """Drop userinfo, query and fragment so URLs are safe to log/persist."""
    try:
        p = urllib.parse.urlsplit(url)
    except ValueError:
        return "<invalid url>"
    host = p.hostname or ""
    if p.port:
        host += f":{p.port}"
    return urllib.parse.urlunsplit((p.scheme, host, p.path, "", ""))


class Response:
    def __init__(self, status, body, headers=None):
        self.status = status
        self.body = body
        self.headers = headers or {}


class UrllibTransport:
    def request(self, method, url, headers, data, timeout, max_bytes):
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read(max_bytes + 1)
                return Response(resp.status, body, dict(resp.headers.items()))
        except urllib.error.HTTPError as e:
            try:
                body = e.read(4096)
            except Exception:  # noqa: BLE001 - best effort diagnostic body
                body = b""
            return Response(e.code, body, dict(e.headers.items()) if e.headers else {})
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            reason = getattr(e, "reason", e)
            raise NetworkError(f"request to {redact(url)} failed: {reason}", url=redact(url)) from None


class HttpClient:
    def __init__(self, transport=None, timeout=DEFAULT_TIMEOUT_S, max_bytes=DEFAULT_MAX_BYTES):
        self.transport = transport or UrllibTransport()
        self.timeout = timeout
        self.max_bytes = max_bytes
        self.bytes_downloaded = 0

    def fetch(self, url, method="GET", headers=None, data=None, byte_range=None, max_bytes=None,
              not_found_is_coverage=False):
        max_bytes = self.max_bytes if max_bytes is None else max_bytes
        h = {"User-Agent": USER_AGENT}
        if headers:
            h.update(headers)
        if byte_range is not None:
            start, length = byte_range
            h["Range"] = f"bytes={start}-{start + length - 1}"
        safe = redact(url)
        resp = self.transport.request(method, url, h, data, self.timeout, max_bytes)
        if resp.status in (401, 403):
            raise AuthError(f"{safe}: provider refused access (HTTP {resp.status}); check credentials/terms", resp.status, safe)
        if resp.status == 404 and not_found_is_coverage:
            raise CoverageError(f"{safe}: no data published for this location (HTTP 404)")
        if resp.status == 429:
            raise NetworkError(f"{safe}: rate limited (HTTP 429); retry later or use a local file", 429, safe)
        if resp.status not in (200, 206):
            snippet = resp.body[:200].decode("utf-8", "replace").strip() if resp.body else ""
            raise NetworkError(f"{safe}: HTTP {resp.status} {snippet}", resp.status, safe)
        if len(resp.body) > max_bytes:
            raise LimitError(f"{safe}: response exceeds limit of {max_bytes} bytes")
        if byte_range is not None:
            if resp.status == 200:
                # Server ignored Range: accept only if the whole body is small enough, then slice.
                start, length = byte_range
                body = resp.body[start:start + length]
            else:
                body = resp.body
        else:
            body = resp.body
        self.bytes_downloaded += len(resp.body)
        return body
