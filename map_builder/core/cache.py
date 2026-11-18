"""Content cache for permitted sources (OSM ODbL data, Copernicus DEM tiles).

Entries are keyed by a caller-provided string that must not contain secrets
(use :func:`map_builder.core.http.redact` on URLs). Writes are atomic.
"""

import hashlib
import json
import os
import tempfile
import time


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
            with open(p + ".bin", "rb") as f:
                body = f.read()
            with open(p + ".json", "r", encoding="utf-8") as f:
                meta = json.load(f)
        except (OSError, ValueError):
            return None
        if meta.get("sha256") != hashlib.sha256(body).hexdigest():
            return None  # corrupt entry: ignore, it will be refetched
        return body

    def put(self, namespace, key, body, meta=None):
        if len(body) > self.max_entry_bytes:
            return
        p = self._path(namespace, key)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        info = dict(meta or {})
        info.update({"key": key, "sha256": hashlib.sha256(body).hexdigest(), "stored_unix": int(time.time())})
        for suffix, data in ((".bin", body), (".json", json.dumps(info, indent=1).encode("utf-8"))):
            fd, tmp = tempfile.mkstemp(dir=os.path.dirname(p))
            try:
                with os.fdopen(fd, "wb") as f:
                    f.write(data)
                os.replace(tmp, p + suffix)
            except BaseException:
                if os.path.exists(tmp):
                    os.unlink(tmp)
                raise


class NullCache:
    def get(self, namespace, key):
        return None

    def put(self, namespace, key, body, meta=None):
        pass
