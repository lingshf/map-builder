"""Content cache for permitted sources (OSM ODbL data, Copernicus DEM tiles).

Entries are keyed by a caller-provided string that must not contain secrets
(dataset ids and fixed provider labels, never endpoint paths). Writes are atomic.
"""

import hashlib
import json
import os
import re
import tempfile
import time


MAX_META_BYTES = 64 * 1024
_DATASET_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def check_cache_dataset_id(value, endpoint_url=""):
    """Validate a caller-supplied, credential-free identity for caching a non-default endpoint.

    Endpoint URLs are never used as cache identity (their path/query may embed a
    credential), so callers that opt into caching an override must name the dataset
    explicitly. Returns the id or raises ``ValueError``.
    """
    if not isinstance(value, str) or not _DATASET_ID.match(value):
        raise ValueError("cache_dataset_id must be 1-64 characters of [A-Za-z0-9._-] when caching a "
                         "caller-supplied endpoint")
    try:
        from urllib.parse import unquote, urlsplit
        p = urlsplit(str(endpoint_url))
        private = " ".join(unquote(s) for s in (p.username or "", p.password or "", p.path, p.query, p.fragment))
    except ValueError:
        private = ""
    if len(value) >= 6 and value.lower() in private.lower():
        raise ValueError("cache_dataset_id must not be copied from the endpoint URL path, query or credentials")
    return value


def _read_capped(path, limit):
    """Read a file only if it is at most ``limit`` bytes; otherwise None."""
    with open(path, "rb") as f:
        if os.fstat(f.fileno()).st_size > limit:
            return None
        data = f.read(limit + 1)
    return data if len(data) <= limit else None


class DiskCache:
    def __init__(self, root, max_entry_bytes=128 * 1024 * 1024):
        self.root = os.path.abspath(root)
        self.max_entry_bytes = max_entry_bytes

    def _path(self, namespace, key):
        h = hashlib.sha256(f"{namespace}\n{key}".encode("utf-8")).hexdigest()
        return os.path.join(self.root, namespace, h[:2], h)

    def get(self, namespace, key):
        p = self._path(namespace, key)
        try:
            raw_meta = _read_capped(p + ".json", MAX_META_BYTES)
            if raw_meta is None:
                return None
            meta = json.loads(raw_meta.decode("utf-8"))
            body = _read_capped(p + ".bin", self.max_entry_bytes)
        except (OSError, ValueError):
            return None
        if body is None or not isinstance(meta, dict):
            return None
        if meta.get("sha256") != hashlib.sha256(body).hexdigest():
            return None  # corrupt entry: ignore, it will be refetched
        return body

    def put(self, namespace, key, body, meta=None):
        if len(body) > self.max_entry_bytes:
            return
        p = self._path(namespace, key)
        info = dict(meta or {})
        info.update({"key": key, "sha256": hashlib.sha256(body).hexdigest(), "stored_unix": int(time.time())})
        meta_bytes = json.dumps(info, indent=1).encode("utf-8")
        if len(meta_bytes) > MAX_META_BYTES:
            return
        os.makedirs(os.path.dirname(p), exist_ok=True)
        for suffix, data in ((".bin", body), (".json", meta_bytes)):
            fd, tmp = tempfile.mkstemp(dir=os.path.dirname(p))
            try:
                with os.fdopen(fd, "wb") as f:
                    f.write(data)
                os.replace(tmp, p + suffix)
            except BaseException:
                if os.path.exists(tmp):
                    os.unlink(tmp)
                raise

    def delete(self, namespace, key):
        """Remove an entry (e.g. one that later failed validation); missing entries are ignored."""
        p = self._path(namespace, key)
        for suffix in (".json", ".bin"):
            try:
                os.unlink(p + suffix)
            except FileNotFoundError:
                pass


class NullCache:
    def get(self, namespace, key):
        return None

    def put(self, namespace, key, body, meta=None):
        pass

    def delete(self, namespace, key):
        pass
