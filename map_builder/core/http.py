"""Bounded HTTP client (stdlib urllib) with explicit failure mapping.

* Every request has a per-operation timeout, a total monotonic deadline
  (connect, redirects and body) and a hard byte cap; bodies are read in chunks.
* Redirects are limited and never carry Authorization/X-API-Key/Cookie to
  another origin or from https to http.
* Credentials are never placed in error messages or logs: callers pass them via
  ``headers`` and :func:`redact` reduces URLs to their origin (no userinfo, path,
  query or fragment) before they are shown anywhere. Errors carry only the
  redacted origin, the status code or a
  transport exception class name - never provider bodies or exception text.
* Redirect bodies are closed unread and every hop shares the total deadline.
* Partial (206) responses are checked against ``Content-Range``.
* A transport may be injected (``Transport`` protocol) so tests never touch
  the network.
"""

import http.client
import re
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from . import GENERATOR_NAME, GENERATOR_VERSION
from .errors import AuthError, CoverageError, LimitError, NetworkError

USER_AGENT = f"{GENERATOR_NAME}/{GENERATOR_VERSION} (Blender add-on; +https://github.com/lingshf/map-builder)"
DEFAULT_TIMEOUT_S = 60.0
DEFAULT_MAX_BYTES = 64 * 1024 * 1024
TOTAL_TIMEOUT_FACTOR = 4.0
MAX_REDIRECTS = 5
READ_CHUNK = 64 * 1024
SENSITIVE_HEADERS = {"authorization", "x-api-key", "cookie"}
_CONTENT_RANGE = re.compile(r"^\s*bytes\s+(\d+)-(\d+)/(\d+|\*)\s*$", re.IGNORECASE)


def redact(url):
    """Origin only (``scheme://host[:port]``) so URLs are safe to log/persist.

    Userinfo, path, query and fragment are all dropped: a caller-supplied endpoint
    may embed a credential in any of them (e.g. ``/api/<token>/interpreter``).
    """
    try:
        p = urllib.parse.urlsplit(str(url))
        port = p.port
    except ValueError:
        return "<invalid url>"
    host = (p.hostname or "").lower()
    if ":" in host:
        host = f"[{host}]"
    if port:
        host += f":{port}"
    scheme = re.sub(r"[^a-z0-9+.-]", "", (p.scheme or "").lower())
    return f"{scheme}://{host}" if scheme else (host or "<invalid url>")


class Response:
    def __init__(self, status, body, headers=None):
        self.status = status
        self.body = body
        self.headers = headers or {}


def _origin(parts):
    scheme = (parts.scheme or "").lower()
    try:
        port = parts.port
    except ValueError:
        port = -1
    if port is None:
        port = {"http": 80, "https": 443}.get(scheme)
    return scheme, (parts.hostname or "").lower(), port


def _exc_name(exc):
    """Exception class name only (never its message, which may echo URLs or credentials)."""
    return re.sub(r"[^A-Za-z0-9_]", "", type(exc).__name__)[:64] or "Error"


def _header(headers, name):
    name = name.lower()
    for k, v in (headers or {}).items():
        if str(k).lower() == name:
            return v
    return None


class _DrainedBody:
    """Stand-in for a redirect response body that was closed unread.

    urllib's ``HTTPRedirectHandler.http_error_30x`` calls ``fp.read()`` (unbounded,
    outside the byte cap and deadline) before following a redirect; handing it this
    object instead guarantees no redirect body is ever downloaded.
    """

    def read(self, *_args):
        return b""

    def readline(self, *_args):
        return b""

    def readlines(self, *_args):
        return []

    def __iter__(self):
        return iter(())

    def close(self):
        pass


def _close_quietly(fp):
    try:
        if fp is not None:
            fp.close()
    except Exception:  # noqa: BLE001 - closing is best effort
        pass


class SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Follows at most ``max_redirects`` redirects and never leaks credentials.

    When any of :data:`SENSITIVE_HEADERS` is present, a redirect that changes
    origin (scheme/host/port) or downgrades https->http is refused instead of
    forwarding the credential. Only http/https targets are ever followed.
    Redirect response bodies are closed without being read, and every hop is
    bounded by the same absolute deadline (``remaining`` returns the seconds left).
    """

    def __init__(self, max_redirects=MAX_REDIRECTS, check_deadline=None, remaining=None):
        super().__init__()
        self.max_redirections = max_redirects
        self.max_repeats = max_redirects
        self._check_deadline = check_deadline
        self._remaining = remaining

    def http_error_302(self, req, fp, code, msg, headers):
        _close_quietly(fp)  # never drain the redirect body
        if self._check_deadline:
            self._check_deadline()
        if self._remaining is not None:
            # OpenerDirector re-opens the next hop with req.timeout: clamp it to the time left.
            left = max(0.001, self._remaining())
            req.timeout = left if req.timeout is None else max(0.001, min(req.timeout, left))
        return super().http_error_302(req, _DrainedBody(), code, msg, headers)

    http_error_301 = http_error_303 = http_error_307 = http_error_308 = http_error_302

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        safe = redact(req.full_url)
        if self._check_deadline:
            self._check_deadline()
        old, new = urllib.parse.urlsplit(req.full_url), urllib.parse.urlsplit(newurl)
        names = {k.lower() for k in list(req.headers) + list(req.unredirected_hdrs)}
        reason = None
        if new.scheme.lower() not in ("http", "https"):
            reason = "redirect to a non-HTTP scheme refused"
        elif names & SENSITIVE_HEADERS and (
                _origin(old) != _origin(new) or (old.scheme.lower() == "https" and new.scheme.lower() != "https")):
            reason = "redirect to a different origin refused because the request carries credentials"
        if reason:
            _close_quietly(fp)
            raise NetworkError(f"{safe}: {reason} (HTTP {code})", code, safe)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _clamp_socket_timeout(resp, seconds):
    """Best effort: bound the next receive on the response's socket by the remaining deadline."""
    sock = getattr(getattr(getattr(resp, "fp", None), "raw", None), "_sock", None)
    if sock is not None:
        try:
            sock.settimeout(seconds)
        except OSError:
            pass


class _Watchdog:
    """Shuts down every socket of a request when its absolute deadline passes.

    A per-receive timeout cannot bound a call (TLS handshake, header, chunk-size or trailer read)
    that performs many receives, so the deadline is enforced from a timer thread instead.
    """

    def __init__(self, seconds):
        self._lock = threading.Lock()
        self._socks = []
        self.expired = False
        self._timer = threading.Timer(max(0.0, seconds), self._fire)
        self._timer.daemon = True
        self._timer.start()

    def _fire(self):
        with self._lock:
            self.expired = True
            socks = list(self._socks)
        for s in socks:
            _shutdown_quietly(s)

    def register(self, sock):
        with self._lock:
            self._socks.append(sock)
            expired = self.expired
        if expired:
            _shutdown_quietly(sock)
        return sock

    def cancel(self):
        self._timer.cancel()


def _shutdown_quietly(sock):
    try:
        sock.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass


def _watched(conn_class, watchdog):
    class Watched(conn_class):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            create = self._create_connection
            self._create_connection = lambda *a, **k: watchdog.register(create(*a, **k))
    return Watched


class _WatchedHTTPHandler(urllib.request.HTTPHandler):
    def __init__(self, watchdog):
        super().__init__()
        self._watchdog = watchdog

    def http_open(self, req):
        return self.do_open(_watched(http.client.HTTPConnection, self._watchdog), req)


class _WatchedHTTPSHandler(urllib.request.HTTPSHandler):
    def __init__(self, watchdog):
        super().__init__()
        self._watchdog = watchdog

    def https_open(self, req):
        return self.do_open(_watched(http.client.HTTPSConnection, self._watchdog), req, context=self._context)


class UrllibTransport:
    """urllib transport with safe redirects and a total (monotonic) deadline.

    ``opener`` and ``clock`` may be injected for tests.
    """

    def __init__(self, total_timeout=None, max_redirects=MAX_REDIRECTS, opener=None, clock=time.monotonic):
        self.total_timeout = total_timeout
        self.max_redirects = max_redirects
        self.opener = opener
        self.clock = clock

    def request(self, method, url, headers, data, timeout, max_bytes):
        safe = redact(url)
        total = self.total_timeout if self.total_timeout is not None else timeout * TOTAL_TIMEOUT_FACTOR
        deadline = self.clock() + total

        def check_deadline():
            if self.clock() > deadline:
                raise NetworkError(f"{safe}: request exceeded the total time limit of {total:g} s", url=safe)

        watchdog = None if self.opener else _Watchdog(deadline - self.clock())
        opener = self.opener or urllib.request.build_opener(
            SafeRedirectHandler(self.max_redirects, check_deadline, lambda: deadline - self.clock()),
            _WatchedHTTPHandler(watchdog), _WatchedHTTPSHandler(watchdog))
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            return self._exchange(opener, req, timeout, max_bytes, deadline, check_deadline)
        except urllib.error.HTTPError as e:
            hdrs = dict(e.headers.items()) if e.headers else {}
            try:
                e.close()
            except Exception:  # noqa: BLE001 - closing is best effort
                pass
            return Response(e.code, b"", hdrs)  # error bodies are never surfaced
        except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException, ValueError) as e:
            if watchdog is not None and watchdog.expired:
                raise NetworkError(f"{safe}: request exceeded the total time limit of {total:g} s",
                                   url=safe) from None
            cause = getattr(e, "reason", e)
            cause = cause if isinstance(cause, BaseException) else e
            raise NetworkError(f"{safe}: request failed ({_exc_name(cause)})", url=safe) from None
        finally:
            if watchdog is not None:
                watchdog.cancel()

    def _exchange(self, opener, req, timeout, max_bytes, deadline, check_deadline):
        resp = opener.open(req, timeout=max(0.001, min(timeout, deadline - self.clock())))
        with resp:
            limit = max_bytes + 1
            chunks, n = [], 0
            while n < limit:
                check_deadline()
                _clamp_socket_timeout(resp, max(0.001, min(timeout, deadline - self.clock())))
                want = min(READ_CHUNK, limit - n)
                reader = getattr(resp, "read1", None)
                chunk = reader(want) if reader is not None else resp.read(want)
                if not chunk:
                    break
                chunks.append(chunk)
                n += len(chunk)
            check_deadline()
            status = getattr(resp, "status", None) or resp.getcode()
            return Response(status, b"".join(chunks), dict(resp.headers.items()))


class HttpClient:
    def __init__(self, transport=None, timeout=DEFAULT_TIMEOUT_S, max_bytes=DEFAULT_MAX_BYTES, total_timeout=None):
        self.timeout = timeout
        self.total_timeout = total_timeout if total_timeout is not None else timeout * TOTAL_TIMEOUT_FACTOR
        self.transport = transport or UrllibTransport(total_timeout=self.total_timeout)
        self.max_bytes = max_bytes
        self.bytes_downloaded = 0
        self.clock = time.monotonic

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
        started = self.clock()
        resp = self.transport.request(method, url, h, data, self.timeout, max_bytes)
        body = resp.body or b""
        self.bytes_downloaded += len(body)  # charge everything received, even if rejected below
        if self.clock() - started > self.total_timeout:
            raise NetworkError(f"{safe}: request exceeded the total time limit of {self.total_timeout:g} s", url=safe)
        if resp.status in (401, 403):
            raise AuthError(f"{safe}: provider refused access (HTTP {resp.status}); check credentials/terms", resp.status, safe)
        if resp.status == 404 and not_found_is_coverage:
            raise CoverageError(f"{safe}: no data published for this location (HTTP 404)")
        if resp.status == 429:
            raise NetworkError(f"{safe}: rate limited (HTTP 429); retry later or use a local file", 429, safe)
        if resp.status not in (200, 206):
            raise NetworkError(f"{safe}: HTTP {resp.status}", resp.status, safe)
        if len(body) > max_bytes:
            raise LimitError(f"{safe}: response exceeds limit of {max_bytes} bytes")
        if byte_range is None:
            if resp.status == 206:
                raise NetworkError(f"{safe}: unexpected partial response (HTTP 206)", 206, safe)
            return body
        start, length = byte_range
        if resp.status == 200:
            # Server ignored Range: the whole body (already within max_bytes and charged) is sliced.
            return body[start:start + length]
        return self._check_partial(safe, resp, body, start, length)

    @staticmethod
    def _check_partial(safe, resp, body, start, length):
        m = _CONTENT_RANGE.match(str(_header(resp.headers, "Content-Range") or ""))
        if not m:
            raise NetworkError(f"{safe}: partial response without a valid Content-Range", 206, safe)
        first, last = int(m.group(1)), int(m.group(2))
        total = None if m.group(3) == "*" else int(m.group(3))
        want_last = start + length - 1
        if (first != start or last < first or last > want_last or len(body) != last - first + 1
                or (total is not None and last >= total)):
            raise NetworkError(f"{safe}: partial response does not match the requested byte range", 206, safe)
        if last < want_last and (total is None or last != total - 1):
            raise NetworkError(f"{safe}: short partial response before end of file", 206, safe)
        return body
