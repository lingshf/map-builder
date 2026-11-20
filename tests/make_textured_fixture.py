"""Complete textured schema-2.1.0 ``.mbmap`` fixtures (S3-TEX-FORMAT).

``python -m tests.make_textured_fixture OUT.mbmap`` writes one package built from the synthetic test input
through the normal pipeline and package writer: real manifest, .mbcol, heightfield, NOTICES and report. The
terrain material carries a 4x4 PNG (with UVs) and the manifest carries its ``asset_notices`` entry. CI feeds it
to the frozen v0.3.0 Python validator and C# reader, which must accept it and ignore the texture.

The module also builds the negative fixtures (one per row of the validator table) shared by the Python and C#
validator tests; see :func:`negative_fixtures`.
"""

import hashlib
import json
import os
import random
import struct
import sys
import tempfile
import zipfile
import zlib
from unittest import mock

from map_builder.core import pipeline
from map_builder.core.generate import MATERIALS, PlanOptions, build_plan
from map_builder.core.package import file_entry, manifest_bytes
from map_builder.core.glb import MAX_TEXTURE_BYTES

from .synthetic import synthetic_inputs

UTC = "2024-01-01T00:00:00Z"
TEXTURED_MATERIAL = "MB Terrain"
NOTICE_URL = "https://example.invalid/test-texture-licence"


def make_png(width=4, height=4):
    """A small RGB checker PNG (deterministic bytes)."""
    def chunk(tag, data):
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))
    rows = b"".join(b"\x00" + b"".join(b"\xff\x80\x20" if (x + y) % 2 else b"\x20\x60\xff" for x in range(width))
                    for y in range(height))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


def asset_notice(png):
    return {"name": "Test checker texture (4x4)",
            "attribution": "Test checker texture by the map-builder tests (synthetic, public domain)",
            "license": {"id": "CC0-1.0", "name": "Creative Commons Zero v1.0 Universal", "url": NOTICE_URL,
                        "text": "Test texture dedicated to the public domain; no rights reserved."},
            "sha256": [hashlib.sha256(png).hexdigest()]}


def _assign_terrain_uvs(plan):
    seen = set()
    for o in plan.objects:
        md = o.mesh if o.mesh is not None else plan.shared_meshes[o.mesh_key]
        if id(md) in seen:
            continue
        seen.add(id(md))
        if TEXTURED_MATERIAL not in md.materials:
            continue
        ti = md.materials.index(TEXTURED_MATERIAL)
        md.face_uvs = [tuple((md.vertices[i][0] / 4.0, md.vertices[i][1] / 4.0) for i in f) if mi == ti else None
                       for f, mi in zip(md.faces, md.face_materials)]


def build_textured_package(path, schema_version="2.1.0", png=None, notices=None):
    """Write the complete textured package to ``path``; returns (manifest, png bytes)."""
    png = png or make_png()
    notices = [asset_notice(png)] if notices is None else notices
    materials = dict(MATERIALS)
    materials[TEXTURED_MATERIAL] = tuple(MATERIALS[TEXTURED_MATERIAL][:3]) + (png,)
    real_write_glb, real_assemble = pipeline.write_glb, pipeline.assemble
    with tempfile.TemporaryDirectory() as tmp:
        area, grid, cl, _ids, sources = synthetic_inputs(os.path.join(tmp, "src"))
        plan = build_plan(area, grid, cl, PlanOptions(seed=1))
        _assign_terrain_uvs(plan)
        with mock.patch.object(pipeline, "write_glb", lambda nodes, _m, **k: real_write_glb(nodes, materials, **k)), \
                mock.patch.object(pipeline, "assemble", lambda *a, **k: real_assemble(
                    *a, schema_version=schema_version, asset_notices=notices, **k)):
            manifest, _ = pipeline.plan_to_package(plan, path, "synthetic_textured", sources,
                                                   heightfield_spacing=5, created_utc=UTC)
    return manifest, png


# --- negative fixtures ---------------------------------------------------------------------

def _load(path):
    with zipfile.ZipFile(path) as z:
        members = {n: z.read(n) for n in z.namelist() if n != "manifest.json"}
        return members, json.loads(z.read("manifest.json"))


def _write(path, members, manifest):
    """Write WITHOUT validation, with files[] re-hashed so only the targeted rule is violated."""
    manifest["files"] = [file_entry(p, members[p]) for p in sorted(members)]
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", manifest_bytes(manifest))
        for name in sorted(members):
            z.writestr(name, members[name])


def edit_glb(glb, fn):
    """Parse ``glb``, call ``fn(json, bin_bytearray)`` (in-place edits), rebuild; buffer byteLength follows."""
    jl = struct.unpack_from("<I", glb, 12)[0]
    gl = json.loads(glb[20:20 + jl])
    bl = struct.unpack_from("<I", glb, 20 + jl)[0]
    binb = bytearray(glb[28 + jl:28 + jl + bl])
    fn(gl, binb)
    while len(binb) % 4:
        binb.append(0)
    gl["buffers"][0]["byteLength"] = len(binb)
    js = json.dumps(gl, separators=(",", ":")).encode()
    js += b" " * (-len(js) % 4)
    total = 12 + 8 + len(js) + 8 + len(binb)
    return (struct.pack("<III", 0x46546C67, 2, total) + struct.pack("<II", len(js), 0x4E4F534A) + js
            + struct.pack("<II", len(binb), 0x004E4942) + bytes(binb))


def _image_offset(gl, i=0):
    return gl["bufferViews"][gl["images"][i]["bufferView"]]["byteOffset"]


def _textured_primitive(gl):
    textured = {i for i, m in enumerate(gl["materials"]) if "baseColorTexture" in m["pbrMetallicRoughness"]}
    return next(p for mesh in gl["meshes"] for p in mesh["primitives"] if p.get("material") in textured)


def _set_ihdr(field, value):
    def fn(gl, binb):
        struct.pack_into(">I", binb, _image_offset(gl) + 16 + 4 * field, value)
    return fn


def _glb_edit(fn):
    return lambda members, manifest: members.__setitem__("visual/map.glb", edit_glb(members["visual/map.glb"], fn))


def _fx_uri(gl, binb):
    gl["images"][0]["uri"] = "tex.png"


def _fx_mime(gl, binb):
    gl["images"][0]["mimeType"] = "image/jpeg"


def _fx_signature(gl, binb):
    binb[_image_offset(gl)] ^= 0xFF


def _fx_ihdr(gl, binb):
    binb[_image_offset(gl) + 12:_image_offset(gl) + 16] = b"IHDX"


def _fx_total(gl, binb):
    big = make_png() + random.Random(7).randbytes(MAX_TEXTURE_BYTES)   # incompressible; only headers are read
    while len(binb) % 4:
        binb.append(0)
    gl["bufferViews"].append({"buffer": 0, "byteOffset": len(binb), "byteLength": len(big)})
    binb.extend(big)
    gl["images"].append({"bufferView": len(gl["bufferViews"]) - 1, "mimeType": "image/png"})


def _fx_view_range(gl, binb):
    gl["images"][0]["bufferView"] = 9999


def _fx_view_outside(gl, binb):
    gl["bufferViews"][gl["images"][0]["bufferView"]]["byteLength"] = len(binb) * 2


def _fx_tex_source(gl, binb):
    gl["textures"][0]["source"] = 5


def _fx_tex_sampler(gl, binb):
    gl["textures"][0]["sampler"] = 5


def _fx_mat_index(gl, binb):
    next(m for m in gl["materials"] if "baseColorTexture" in m["pbrMetallicRoughness"])[
        "pbrMetallicRoughness"]["baseColorTexture"]["index"] = 7


def _fx_prim_material(gl, binb):
    _textured_primitive(gl)["material"] = len(gl["materials"])


def _fx_prim_material_null(gl, binb):
    _textured_primitive(gl)["material"] = None


def _fx_points_material(gl, binb):
    p = dict(_textured_primitive(gl))
    p["mode"] = 0
    p["material"] = len(gl["materials"])
    next(m for m in gl["meshes"] if any(q is _textured_primitive(gl) for q in m["primitives"]))["primitives"].append(p)


def _fx_texcoord(gl, binb):
    next(m for m in gl["materials"] if "baseColorTexture" in m["pbrMetallicRoughness"])[
        "pbrMetallicRoughness"]["baseColorTexture"]["texCoord"] = 1


def _fx_uv_missing(gl, binb):
    del _textured_primitive(gl)["attributes"]["TEXCOORD_0"]


def _fx_uv_count(gl, binb):
    gl["accessors"][_textured_primitive(gl)["attributes"]["TEXCOORD_0"]]["count"] -= 3


def _fx_uv_nan(gl, binb):
    a = gl["accessors"][_textured_primitive(gl)["attributes"]["TEXCOORD_0"]]
    struct.pack_into("<f", binb, gl["bufferViews"][a["bufferView"]]["byteOffset"], float("nan"))


def _fx_ext_required(gl, binb):
    gl["extensionsRequired"] = ["KHR_texture_basisu"]


def _fx_no_provenance(members, manifest):
    del manifest["asset_notices"]


def _fx_notice_attribution(members, manifest):
    members["NOTICES.txt"] = members["NOTICES.txt"].replace(manifest["asset_notices"][0]["attribution"].encode(), b"")


def _fx_notice_url(members, manifest):
    members["NOTICES.txt"] = members["NOTICES.txt"].replace(NOTICE_URL.encode(), b"")


def _fx_major(members, manifest):
    manifest["schema_version"] = "3.0.0"


def _fx_unused_sha(members, manifest):
    manifest["asset_notices"][0]["sha256"].append("0" * 64)


# name -> (mutation(members, manifest), fragment of the expected error, "error" | "warning")
_FIXTURES = {
    "image_uri": (_glb_edit(_fx_uri), "external image URIs are not allowed", "error"),
    "image_mime": (_glb_edit(_fx_mime), "must have mimeType image/png", "error"),
    "image_signature": (_glb_edit(_fx_signature), "is not a PNG", "error"),
    "image_ihdr": (_glb_edit(_fx_ihdr), "is not a PNG", "error"),
    "image_not_pow2": (_glb_edit(_set_ihdr(0, 3)), "power of two", "error"),
    "image_too_big": (_glb_edit(_set_ihdr(1, 2048)), "<= 1024", "error"),
    "image_total_bytes": (_glb_edit(_fx_total), "embedded images exceed", "error"),
    "image_view_range": (_glb_edit(_fx_view_range), "bufferView is missing or out of range", "error"),
    "image_view_outside": (_glb_edit(_fx_view_outside), "points outside the BIN chunk", "error"),
    "texture_source": (_glb_edit(_fx_tex_source), "source is missing or out of range", "error"),
    "texture_sampler": (_glb_edit(_fx_tex_sampler), "sampler is out of range", "error"),
    "material_index": (_glb_edit(_fx_mat_index), "baseColorTexture.index is missing or out of range", "error"),
    "primitive_material": (_glb_edit(_fx_prim_material), "primitive material index out of range", "error"),
    "primitive_material_null": (_glb_edit(_fx_prim_material_null), "primitive material index out of range", "error"),
    "points_material": (_glb_edit(_fx_points_material), "primitive material index out of range", "error"),
    "material_texcoord": (_glb_edit(_fx_texcoord), "texCoord must be 0", "error"),
    "uv_missing": (_glb_edit(_fx_uv_missing), "is missing TEXCOORD_0", "error"),
    "uv_count": (_glb_edit(_fx_uv_count), "TEXCOORD_0 count differs", "error"),
    "uv_non_finite": (_glb_edit(_fx_uv_nan), "non-finite TEXCOORD_0", "error"),
    "extension_required": (_glb_edit(_fx_ext_required), "required extensions are not allowed", "error"),
    "no_provenance": (_fx_no_provenance, "texture without provenance", "error"),
    "notice_attribution": (_fx_notice_attribution, "lacks the attribution of asset_notices[0]", "error"),
    "notice_licence_url": (_fx_notice_url, "lacks the licence url of asset_notices[0]", "error"),
    "unknown_major": (_fx_major, "unsupported schema major version 3", "error"),
    "notice_sha_not_in_glb": (_fx_unused_sha, "is not an image in visual/map.glb", "warning"),
}


def negative_fixtures(directory):
    """Write the good textured package and one broken copy per validator rule into ``directory``.
    Returns {name: (path, expected fragment, 'error' | 'warning')}; 'good' maps to (path, None, None)."""
    good = os.path.join(directory, "good.mbmap")
    build_textured_package(good)
    out = {"good": (good, None, None)}
    for name, (mutate, fragment, kind) in _FIXTURES.items():
        members, manifest = _load(good)
        mutate(members, manifest)
        path = os.path.join(directory, f"{name}.mbmap")
        _write(path, members, manifest)
        out[name] = (path, fragment, kind)
    return out


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("usage: python -m tests.make_textured_fixture OUT.mbmap", file=sys.stderr)
        return 2
    manifest, _ = build_textured_package(argv[0])
    print(f"wrote {argv[0]} (schema {manifest['schema_version']}, {len(manifest['asset_notices'])} asset notice(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
