"""Pure (bpy-free) helpers for the Generate operator: settings from UI values, credential policy and the
human-readable report. Unit-tested without Blender (tests/test_blender_bake.py).

Credential policy: nothing the user types into the add-on's UI may carry a credential, because scene
properties, custom properties and Text blocks are saved into the .blend file. Copernicus GLO-30 is public
(no account). The Overpass endpoint is either the public default or -- for a private/authenticated
mirror -- read from the ``MAP_BUILDER_OVERPASS_URL`` environment variable at the moment Generate runs.
That URL is only held in memory and passed to the core, which records just its origin
(``scheme://host[:port]``, see ``core.http.redact``) in sources, caches, logs and packages.
"""

import json
import urllib.parse

from ..core.osm import DEFAULT_OVERPASS_URL

ENV_OVERPASS_URL = "MAP_BUILDER_OVERPASS_URL"
DEFAULT_LOCAL_DATUM = "user-declared (unknown)"


class SettingsInputError(ValueError):
    """The UI values cannot form valid generation settings (message is safe to show and persist)."""


def endpoint_problem(url):
    """None if ``url`` is a plain http(s) endpoint, else why it is unusable (never echoes the URL)."""
    try:
        p = urllib.parse.urlsplit(url)
        p.port
    except ValueError:
        return "is not a valid URL"
    if p.scheme not in ("http", "https") or not p.hostname:
        return "must be an http:// or https:// URL with a host name"
    return None


def needs_network(values):
    return values.get("elevation_source") == "copernicus" or values.get("osm_source") == "overpass"


def settings_kwargs(values, environ):
    """Keyword arguments for ``core.pipeline.Settings`` from UI ``values`` (dict of plain values with
    absolute paths) and ``environ`` (os.environ or a test dict). Raises SettingsInputError."""
    kw = {"elevation_source": values["elevation_source"], "osm_source": values["osm_source"],
          "terrain_spacing": float(values["terrain_spacing"]), "cache_dir": values.get("cache_dir") or ""}
    if kw["elevation_source"] == "file":
        path = values.get("elevation_file") or ""
        if not path:
            raise SettingsInputError("choose a local elevation file (GeoTIFF or ESRI ASCII grid)")
        lic = (values.get("elevation_license") or "").strip()
        if not lic:
            raise SettingsInputError("enter the licence/attribution of the local elevation file (it is written "
                                     "to the package manifest)")
        kw.update(elevation_file=path, elevation_crs=(values.get("elevation_crs") or "EPSG:4326").strip(),
                  elevation_vertical_datum=(values.get("elevation_vertical_datum") or "").strip()
                  or DEFAULT_LOCAL_DATUM, elevation_license=lic)
    elif kw["elevation_source"] != "copernicus":
        raise SettingsInputError(f"unknown elevation source {kw['elevation_source']!r}")
    if kw["osm_source"] == "file":
        path = values.get("osm_file") or ""
        if not path:
            raise SettingsInputError("choose a local OpenStreetMap XML file (.osm)")
        kw["osm_file"] = path
    elif kw["osm_source"] == "overpass":
        if values.get("overpass_endpoint", "default") == "env":
            url = (environ.get(ENV_OVERPASS_URL) or "").strip()
            if not url:
                raise SettingsInputError(f"Overpass endpoint is set to the environment variable {ENV_OVERPASS_URL}, "
                                         "which is not set; set it before starting Blender, or use the public "
                                         "endpoint")
            problem = endpoint_problem(url)
            if problem:
                raise SettingsInputError(f"{ENV_OVERPASS_URL} {problem}")
            kw["overpass_url"] = url
        else:
            kw["overpass_url"] = DEFAULT_OVERPASS_URL
    else:
        raise SettingsInputError(f"unknown OSM source {kw['osm_source']!r}")
    return kw


def _lic_text(lic):
    if isinstance(lic, dict):
        return " ".join(str(lic.get(k)) for k in ("name", "id", "url") if lic.get(k))
    return str(lic or "not declared")


def format_report(title, sources, report, extra=None):
    """Plain-text report: sources, licences, attribution, resolution, unsupported and invalid features,
    warnings, then the full JSON (contains no credentials: source entries are redacted by the core)."""
    lines = [title, ""]
    lines.append("SOURCES, LICENCES AND ATTRIBUTION")
    for src in sources or []:
        lines.append(f"- {src.get('kind', 'source')}: {src.get('product') or src.get('provider') or '?'}"
                     f" ({src.get('provider', '')})")
        lines.append(f"    licence: {_lic_text(src.get('license'))}")
        if src.get("attribution"):
            lines.append(f"    attribution: {src['attribution']}")
        for k in ("source_resolution_m", "resampled_spacing_m", "crs", "vertical_datum", "osm_base_timestamp",
                  "endpoint", "file_sha256", "sha256"):
            if src.get(k) is not None:
                lines.append(f"    {k}: {src[k]}")
    report = report or {}
    for key, label in (("unsupported_features", "UNSUPPORTED FEATURES"), ("invalid_features", "INVALID FEATURES"),
                       ("warnings", "WARNINGS")):
        items = report.get(key) or []
        lines += ["", f"{label} ({len(items)})"]
        lines += [f"- {json.dumps(i, sort_keys=True) if not isinstance(i, str) else i}" for i in items]
    if report.get("counts"):
        lines += ["", "COUNTS", json.dumps(report["counts"], sort_keys=True)]
    if report.get("edits"):
        ed = report["edits"]
        lines += ["", "EDITS (identities per docs/PACKAGE_FORMAT.md)"]
        lines += [f"- removed: {x}" for x in ed.get("removed", [])]
        lines += [f"- duplicated: {d.get('object')} (copy of {d.get('source_id')})" for d in ed.get("duplicated", [])]
        lines += [f"- user-added: {x}" for x in ed.get("user_added", [])]
    be = report.get("blender_export")
    if be:
        lines += ["", "BLENDER EXPORT", f"objects: {be.get('objects')}, triangles: {be.get('triangles')}",
                  f"mirrored objects: {', '.join(be.get('mirrored_objects') or []) or 'none'}"]
        lines += [f"- excluded: {e['object']} ({e['reason']})" for e in be.get("excluded_objects") or []]
    for k, v in (extra or {}).items():
        lines += ["", k.upper(), json.dumps(v, indent=1, sort_keys=True, default=str)]
    lines += ["", "FULL REPORT (JSON)", json.dumps(report, indent=1, sort_keys=True, default=str)]
    return "\n".join(lines) + "\n"
