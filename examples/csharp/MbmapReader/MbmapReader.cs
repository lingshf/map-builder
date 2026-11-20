// Reference reader for .mbmap packages (map-builder.package 2.x). The contract is docs/PACKAGE_FORMAT.md;
// struct layouts and checks mirror map_builder/core/collision.py, glb.py and package.py.
//
// It illustrates the consumer side of the contract and is NOT a production loader:
// * it reads every member into memory (bounded by the package limits);
// * its triangle query is brute force (a real Core adapter needs a deterministic BVH);
// * its GLB reader only extracts world-space triangles for the binding and orientation-probe checks
//   (Unity presentation should use a real importer such as glTFast, then repeat the probe check on the
//   meshes that importer produced).
//
// Code style: C# 8 and APIs available in netstandard2.1 (a netstandard2.1 library gets System.Text.Json
// from the System.Text.Json NuGet package). No other dependencies.
using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace MapBuilder.Reference
{
    public sealed class MbmapException : Exception
    {
        public MbmapException(string message) : base(message) { }
    }

    /// <summary>Bounds from docs/PACKAGE_FORMAT.md and the reference implementation.</summary>
    public static class Limits
    {
        public const int MaxEntries = 64;
        public const long MaxTotalUncompressed = 1536L * 1024 * 1024;
        public const long MaxManifestBytes = 32L * 1024 * 1024;
        public const long MaxRatio = 200;
        public const int MaxNameLength = 255;
        // .mbcol (collision.py)
        public const uint MaxTriangles = 8_000_000, MaxVertices = 12_000_000, MaxObjects = 1_000_000;
        public const uint MaxTableBytes = 256u * 1024 * 1024;
        public const double AabbTableTolM = 1e-3;
        // .mbhf
        public const long MaxHeightfieldPoints = 4_000_000;
        // GLB (glb.py)
        public const long MaxGlbBytes = 1024L * 1024 * 1024;
        public const long MaxVisualTriangles = 8_000_000;
        public const long MaxVisualPositions = 3 * MaxVisualTriangles; // decoded POSITION vertices, this reader's cap
        public const int MaxNodes = 1_000_000, MaxNodeDepth = 64;
        // embedded textures (glb.py, schema 2.1)
        public const long MaxTextureBytes = 4L * 1024 * 1024;
        public const long MaxTextureSide = 1024;
        // orientation probes (package.py)
        public const int ProbeMax = 3;
        public const double ProbeMatchM = 0.05, ProbeMinDot = 0.99, ProbeUnitTol = 1e-4, ProbeVertexTolM = 1e-6;
        public const double ProbeMinNormalXZ = 0.05, ProbeMinAbsXYM = 1.0, ProbeMirrorClearanceM = 0.5;
        // passage probes (package.py)
        public const int PassageProbeMax = 256, PassagePathMin = 2, PassagePathMax = 64;
        public const double PassageRadiusMaxM = 10.0, MaxAbsCoordM = 1.0e6;
    }

    public struct Vec3
    {
        public double X, Y, Z;
        public Vec3(double x, double y, double z) { X = x; Y = y; Z = z; }
        public static Vec3 operator -(Vec3 a, Vec3 b) => new Vec3(a.X - b.X, a.Y - b.Y, a.Z - b.Z);
        public static Vec3 Cross(Vec3 u, Vec3 v) => new Vec3(u.Y * v.Z - u.Z * v.Y, u.Z * v.X - u.X * v.Z, u.X * v.Y - u.Y * v.X);
        public static double Dot(Vec3 u, Vec3 v) => u.X * v.X + u.Y * v.Y + u.Z * v.Z;
        public double Length => Math.Sqrt(X * X + Y * Y + Z * Z);
        public static double Distance(Vec3 a, Vec3 b) => (a - b).Length;
        /// <summary>Unit front-face normal of (a, b, c): normalize(Cross(b - a, c - a)); null if degenerate.</summary>
        public static Vec3? FaceNormal(Vec3 a, Vec3 b, Vec3 c)
        {
            var n = Cross(b - a, c - a);
            double l = n.Length;
            if (l == 0) return null;
            return new Vec3(n.X / l, n.Y / l, n.Z / l);
        }
        public override string ToString() => $"({X:0.###}, {Y:0.###}, {Z:0.###})";
    }

    public struct Triangle
    {
        public Vec3 A, B, C;
        public Triangle(Vec3 a, Vec3 b, Vec3 c) { A = a; B = b; C = c; }
        public Vec3 this[int i] => i == 0 ? A : i == 1 ? B : C;
    }

    /// <summary>
    /// Frames (docs/PACKAGE_FORMAT.md "Frames, axes and units"). Map frame = Core frame: right-handed ENU,
    /// +X east, +Y north, +Z up, metres. Core needs no conversion.
    /// </summary>
    public static class Axes
    {
        /// <summary>glTF = (x, z, -y): a proper rotation, winding preserved.</summary>
        public static Vec3 MapToGltf(Vec3 p) => new Vec3(p.X, p.Z, -p.Y);
        public static Vec3 GltfToMap(Vec3 g) => new Vec3(g.X, -g.Z, g.Y);

        /// <summary>Unity (left-handed, Y up) as produced by a glTF importer that negates X:
        /// unity = (-x, z, -y). This is a reflection, so triangle index order must be reversed.</summary>
        public static Vec3 MapToUnity(Vec3 p) => new Vec3(-p.X, p.Z, -p.Y);
        public static Vec3 UnityToMap(Vec3 u) => new Vec3(-u.X, -u.Z, u.Y);

        /// <summary>A map-frame CCW-outward triangle in Unity space, index order reversed (a, c, b) so that
        /// Unity's Vector3.Cross(b - a, c - a) on the result is the Unity-space front-face normal.</summary>
        public static Triangle MapTriangleToUnity(Triangle t) => new Triangle(MapToUnity(t.A), MapToUnity(t.C), MapToUnity(t.B));

        /// <summary>What glTFast/UnityGLTF do to glTF data: negate X and reverse index order. The flags
        /// exist only so the self-test can show that a wrong importer convention is detected.</summary>
        public static Triangle GltfTriangleToUnity(Triangle t, bool negateX = true, bool reverseWinding = true)
        {
            Vec3 f(Vec3 p) => negateX ? new Vec3(-p.X, p.Y, p.Z) : p;
            return reverseWinding ? new Triangle(f(t.A), f(t.C), f(t.B)) : new Triangle(f(t.A), f(t.B), f(t.C));
        }
    }

    public enum CollisionClass : byte { User = 0, Terrain = 1, Building = 2, Road = 3, Vegetation = 4, Water = 5, Prop = 6, Bridge = 7, Tunnel = 8, Structure = 9 }

    public sealed class CollisionObject
    {
        public int Index;
        public string Name, MbId, Class;
        public int TriStart, TriCount;
        public double[] Aabb; // min xyz, max xyz (map frame)
    }

    /// <summary>collision/map.mbcol v2: authoritative static collision in the map frame. Triangles are two-sided
    /// for intersection; the CCW winding gives the contact normal (outward for solids, up for surfaces, inward
    /// into the free space for tubes).</summary>
    public sealed class CollisionMesh
    {
        public const string Magic = "MBCOL\0\0\0";
        public const int HeaderSize = 64;
        public const uint FlagCcwOutward = 1;
        public static readonly string[] ClassNames = { "user", "terrain", "building", "road", "vegetation", "water", "prop", "bridge", "tunnel", "structure" };
        /// <summary>Collision kind per class id (collision.py CLASS_KINDS): "solid", "surface", "tube" or null (no rule).</summary>
        public static readonly string[] ClassKinds = { null, "surface", "solid", "surface", null, "surface", null, "solid", "tube", "solid" };

        public uint Version, Flags;
        public float[] BoundsMin = new float[3], BoundsMax = new float[3];
        public float[] Vertices;      // xyz per vertex: map frame, world space, metres
        public uint[] Indices;        // 3 per triangle, CCW seen from outside (normal = (b - a) x (c - a))
        public uint[] TriangleObject; // object index per triangle
        public byte[] TriangleClass;  // CollisionClass per triangle
        public CollisionObject[] Objects;

        public int VertexCount => Vertices.Length / 3;
        public int TriangleCount => TriangleObject.Length;

        public Vec3 Vertex(uint i) => new Vec3(Vertices[3 * i], Vertices[3 * i + 1], Vertices[3 * i + 2]);
        public Triangle GetTriangle(int t) => new Triangle(Vertex(Indices[3 * t]), Vertex(Indices[3 * t + 1]), Vertex(Indices[3 * t + 2]));

        /// <summary>Highest surface hit by a vertical ray at map (x, y); NaN if none. Brute force, for
        /// illustration only. classFilter &lt; 0 accepts every class. Same barycentric rule and tolerances as
        /// the reference heightfield rasteriser.</summary>
        public double HighestZ(double x, double y, int classFilter = -1)
        {
            double best = double.NaN;
            for (int t = 0; t < TriangleCount; t++)
            {
                if (classFilter >= 0 && TriangleClass[t] != classFilter) continue;
                var tri = GetTriangle(t);
                Vec3 a = tri.A, b = tri.B, c = tri.C;
                double d = (b.Y - c.Y) * (a.X - c.X) + (c.X - b.X) * (a.Y - c.Y);
                if (Math.Abs(d) < 1e-12) continue; // vertical or degenerate in plan view
                double l1 = ((b.Y - c.Y) * (x - c.X) + (c.X - b.X) * (y - c.Y)) / d;
                double l2 = ((c.Y - a.Y) * (x - c.X) + (a.X - c.X) * (y - c.Y)) / d;
                double l3 = 1 - l1 - l2;
                const double e = -1e-7;
                if (l1 < e || l2 < e || l3 < e) continue;
                double z = l1 * a.Z + l2 * b.Z + l3 * c.Z;
                if (double.IsNaN(best) || z > best) best = z;
            }
            return best;
        }

        /// <summary>Parse and fully bounds-check an .mbcol file (mirrors collision.read_collision).
        /// Diagnostics never echo strings from the file.</summary>
        public static CollisionMesh Read(byte[] d)
        {
            if (d.Length < HeaderSize) throw new MbmapException("collision: file too short for the 64-byte header");
            if (Encoding.ASCII.GetString(d, 0, 8) != Magic) throw new MbmapException("collision: bad magic");
            var c = new CollisionMesh { Version = Bin.U32(d, 8), Flags = Bin.U32(d, 12) };
            uint nv = Bin.U32(d, 16), nt = Bin.U32(d, 20), no = Bin.U32(d, 24), tlen = Bin.U32(d, 28);
            for (int k = 0; k < 3; k++) { c.BoundsMin[k] = Bin.F32(d, 32 + 4 * k); c.BoundsMax[k] = Bin.F32(d, 44 + 4 * k); }
            uint r0 = Bin.U32(d, 56), r1 = Bin.U32(d, 60);
            if (c.Version != 2) throw new MbmapException($"collision: unsupported version {c.Version}");
            if ((c.Flags & FlagCcwOutward) == 0) throw new MbmapException("collision: flags bit0 (CCW outward winding) is not set");
            if ((c.Flags & ~FlagCcwOutward) != 0) throw new MbmapException("collision: unknown flag bits");
            if (r0 != 0 || r1 != 0) throw new MbmapException("collision: reserved header fields must be 0");
            if (nv > Limits.MaxVertices || nt > Limits.MaxTriangles || no > Limits.MaxObjects || tlen > Limits.MaxTableBytes)
                throw new MbmapException("collision: header counts exceed limits");
            if (tlen % 4 != 0) throw new MbmapException("collision: object table length is not padded to 4 bytes");
            if (no > nt) throw new MbmapException("collision: more objects than triangles");
            long pad = (4 - nt % 4) % 4;
            long expected = HeaderSize + 12L * nv + 12L * nt + 4L * nt + nt + pad + tlen;
            if (d.LongLength != expected) throw new MbmapException($"collision: size {d.LongLength} does not match the size computed from the header ({expected})");
            for (int k = 0; k < 3; k++)
                if (!float.IsFinite(c.BoundsMin[k]) || !float.IsFinite(c.BoundsMax[k])) throw new MbmapException("collision: non-finite bounds");

            int o = HeaderSize;
            c.Vertices = new float[3L * nv];
            var lo = new float[] { float.PositiveInfinity, float.PositiveInfinity, float.PositiveInfinity };
            var hi = new float[] { float.NegativeInfinity, float.NegativeInfinity, float.NegativeInfinity };
            for (int k = 0; k < c.Vertices.Length; k++, o += 4)
            {
                float v = Bin.F32(d, o);
                if (!float.IsFinite(v)) throw new MbmapException("collision: non-finite vertex");
                c.Vertices[k] = v;
                lo[k % 3] = Math.Min(lo[k % 3], v);
                hi[k % 3] = Math.Max(hi[k % 3], v);
            }
            if (nv == 0) { lo = new float[3]; hi = new float[3]; }
            for (int k = 0; k < 3; k++)
                if (lo[k] != c.BoundsMin[k] || hi[k] != c.BoundsMax[k]) throw new MbmapException("collision: header bounds do not match the vertices");

            c.Indices = new uint[3L * nt];
            for (int k = 0; k < c.Indices.Length; k++, o += 4)
                if ((c.Indices[k] = Bin.U32(d, o)) >= nv) throw new MbmapException("collision: triangle vertex index out of range");
            c.TriangleObject = new uint[nt];
            for (int k = 0; k < nt; k++, o += 4)
                if ((c.TriangleObject[k] = Bin.U32(d, o)) >= no) throw new MbmapException("collision: triangle object index out of range");
            c.TriangleClass = new byte[nt];
            Array.Copy(d, o, c.TriangleClass, 0, nt);
            foreach (var b in c.TriangleClass) if (b >= ClassNames.Length) throw new MbmapException("collision: unknown class id");
            for (long k = 0; k < pad; k++) if (d[o + nt + k] != 0) throw new MbmapException("collision: class padding bytes must be 0");
            o += (int)(nt + pad);

            int len = (int)tlen;
            while (len > 0 && d[o + len - 1] == 0) len--;
            if (Array.IndexOf(d, (byte)0, o, len) >= 0) throw new MbmapException("collision: object table contains NUL bytes before its padding");
            using (var doc = StrictJson.Parse(new ReadOnlyMemory<byte>(d, o, len), "collision: object table"))
                c.Objects = ReadTable(doc.RootElement, c, (int)no);
            return c;
        }

        static CollisionObject[] ReadTable(JsonElement table, CollisionMesh c, int no)
        {
            if (table.ValueKind != JsonValueKind.Array || table.GetArrayLength() != no)
                throw new MbmapException("collision: object table count does not match the header");
            var result = new CollisionObject[no];
            var names = new HashSet<string>(StringComparer.Ordinal);
            int nt = c.TriangleCount, k = 0;
            long total = 0;
            foreach (var e in table.EnumerateArray())
            {
                string tag = $"collision: object entry {k}";
                if (e.ValueKind != JsonValueKind.Object) throw new MbmapException($"{tag} is not an object");
                var obj = new CollisionObject
                {
                    Index = Json.Int(e, "index", tag),
                    Name = Json.Str(e, "name", tag),
                    MbId = Json.Str(e, "mb_id", tag),
                    Class = Json.Str(e, "class", tag),
                    TriStart = Json.Int(e, "tri_start", tag),
                    TriCount = Json.Int(e, "tri_count", tag),
                };
                if (obj.Index != k) throw new MbmapException($"{tag} has an index other than {k}");
                if (obj.Name.Length == 0 || !names.Add(obj.Name)) throw new MbmapException($"{tag} has a missing or duplicate name");
                if (obj.MbId.Length == 0) throw new MbmapException($"{tag} has no mb_id");
                int cid = Array.IndexOf(ClassNames, obj.Class);
                if (cid < 0) throw new MbmapException($"{tag} has an unknown class");
                int s = obj.TriStart, n = obj.TriCount;
                if (s < 0 || n < 1 || (long)s + n > nt) throw new MbmapException($"{tag} has a bad triangle range");
                for (int t = s; t < s + n; t++)
                {
                    if (c.TriangleObject[t] != k) throw new MbmapException($"{tag}: its triangles are not contiguous in [tri_start, tri_start + tri_count)");
                    if (c.TriangleClass[t] != cid) throw new MbmapException($"{tag}: per-triangle class ids differ from its class");
                }
                total += n;
                obj.Aabb = Json.NumArray(e, "aabb", 6, tag);
                var want = new double[] { double.PositiveInfinity, double.PositiveInfinity, double.PositiveInfinity,
                                          double.NegativeInfinity, double.NegativeInfinity, double.NegativeInfinity };
                for (long i = 3L * s; i < 3L * (s + n); i++)
                {
                    uint vi = c.Indices[i];
                    for (int a = 0; a < 3; a++)
                    {
                        double v = c.Vertices[3 * vi + a];
                        want[a] = Math.Min(want[a], v);
                        want[3 + a] = Math.Max(want[3 + a], v);
                    }
                }
                for (int a = 0; a < 6; a++)
                    if (Math.Abs(obj.Aabb[a] - want[a]) > Limits.AabbTableTolM) throw new MbmapException($"{tag}: aabb does not match its triangles");
                result[k++] = obj;
            }
            if (total != nt) throw new MbmapException("collision: object triangle ranges do not cover every triangle");
            return result;
        }
    }

    /// <summary>collision/terrain.mbhf v1: derived terrain height grid (triangles stay authoritative).</summary>
    public sealed class HeightField
    {
        public const string Magic = "MBHF\0\0\0\0";
        public const int HeaderSize = 48;
        public int Nx, Ny;
        public double X0, Y0, Spacing;  // map frame: x0 = west edge, y0 = south edge
        public float[] Z;               // row j (y = y0 + j*spacing) outer, column i (x = x0 + i*spacing) inner; NaN = no terrain

        public float At(int i, int j) => Z[(long)j * Nx + i];

        public static HeightField Read(byte[] d)
        {
            if (d.Length < HeaderSize) throw new MbmapException("heightfield: file too short for the 48-byte header");
            if (Encoding.ASCII.GetString(d, 0, 8) != Magic) throw new MbmapException("heightfield: bad magic");
            uint ver = Bin.U32(d, 8), nx = Bin.U32(d, 12), ny = Bin.U32(d, 16), reserved = Bin.U32(d, 20);
            if (ver != 1) throw new MbmapException($"heightfield: unsupported version {ver}");
            if (reserved != 0) throw new MbmapException("heightfield: reserved header field must be 0");
            if (nx < 2 || ny < 2 || (long)nx * ny > Limits.MaxHeightfieldPoints) throw new MbmapException("heightfield: implausible dimensions");
            var h = new HeightField { Nx = (int)nx, Ny = (int)ny, X0 = Bin.F64(d, 24), Y0 = Bin.F64(d, 32), Spacing = Bin.F64(d, 40) };
            if (!double.IsFinite(h.X0) || !double.IsFinite(h.Y0) || !double.IsFinite(h.Spacing) || !(h.Spacing > 0))
                throw new MbmapException("heightfield: non-finite origin or non-positive spacing");
            if (d.LongLength != HeaderSize + 4L * nx * ny) throw new MbmapException("heightfield: size does not match nx * ny");
            h.Z = new float[(long)nx * ny];
            for (int k = 0; k < h.Z.Length; k++)
            {
                h.Z[k] = Bin.F32(d, HeaderSize + 4 * k);
                if (float.IsInfinity(h.Z[k])) throw new MbmapException("heightfield: infinite value");
            }
            return h;
        }
    }

    public sealed class VisualNode
    {
        public string Name;
        public List<Triangle> TrianglesGltf = new List<Triangle>(); // world space, glTF axes, CCW front faces
    }

    /// <summary>Minimal defensive GLB reader (mirrors core/glb.py read_glb): world-space triangles per node
    /// of the default scene, with the glTF negative-determinant winding rule applied. Not a renderer.</summary>
    public static class Glb
    {
        const uint MagicGlTF = 0x46546C67, ChunkJson = 0x4E4F534A, ChunkBin = 0x004E4942;

        public static List<VisualNode> Read(byte[] data) => Read(data, out _);

        /// <summary>As <see cref="Read(byte[])"/>; also returns the lowercase hex SHA-256 of every embedded
        /// image (schema 2.1), in image order, for the asset_notices provenance check.</summary>
        public static List<VisualNode> Read(byte[] data, out List<string> imageSha256)
        {
            if (data.LongLength > Limits.MaxGlbBytes) throw new MbmapException("glb: file exceeds size limit");
            if (data.Length < 20) throw new MbmapException("glb: too short");
            if (Bin.U32(data, 0) != MagicGlTF || Bin.U32(data, 4) != 2) throw new MbmapException("glb: not a glTF 2.0 binary");
            if (Bin.U32(data, 8) != data.Length) throw new MbmapException("glb: length header mismatch");
            var chunks = new List<(uint type, int offset, int length)>();
            for (long o = 12; o < data.Length;)
            {
                if (o + 8 > data.Length) throw new MbmapException("glb: truncated chunk header");
                uint clen = Bin.U32(data, (int)o), ctype = Bin.U32(data, (int)o + 4);
                o += 8;
                if (clen % 4 != 0 || o + clen > data.Length) throw new MbmapException("glb: chunk is misaligned or overruns the file");
                chunks.Add((ctype, (int)o, (int)clen));
                o += clen;
            }
            if (chunks.Count == 0 || chunks[0].type != ChunkJson) throw new MbmapException("glb: the first chunk must be JSON");
            bool hasBin = chunks.Count > 1 && chunks[1].type == ChunkBin;
            for (int i = hasBin ? 2 : 1; i < chunks.Count; i++)
                if (chunks[i].type == ChunkJson || chunks[i].type == ChunkBin) throw new MbmapException("glb: unexpected extra JSON/BIN chunk");
            int jsonLen = chunks[0].length;
            while (jsonLen > 0 && data[chunks[0].offset + jsonLen - 1] == (byte)' ') jsonLen--;
            int binOff = hasBin ? chunks[1].offset : 0, binLen = hasBin ? chunks[1].length : 0;
            using (var doc = StrictJson.Parse(new ReadOnlyMemory<byte>(data, chunks[0].offset, jsonLen), "glb: JSON chunk"))
                return ReadNodes(doc.RootElement, data, binOff, binLen, hasBin, out imageSha256);
        }

        static bool IsIndex(JsonElement e, string key, long limit, out long value)
        {
            value = 0;
            return e.TryGetProperty(key, out var v) && v.ValueKind == JsonValueKind.Number && v.TryGetInt64(out value) && value >= 0 && value < limit;
        }

        static string HexSha256(byte[] data, int offset, int length)
        {
            using (var h = SHA256.Create())
            {
                var sb = new StringBuilder();
                foreach (byte b in h.ComputeHash(data, offset, length)) sb.Append(b.ToString("x2"));
                return sb.ToString();
            }
        }

        static List<VisualNode> ReadNodes(JsonElement gl, byte[] data, int binOff, int binLen, bool hasBin, out List<string> imageSha256)
        {
            if (gl.ValueKind != JsonValueKind.Object) throw new MbmapException("glb: JSON chunk must be an object");
            if (Json.Str(Json.Obj(gl, "asset", "glb"), "version", "glb: asset") != "2.0") throw new MbmapException("glb: asset.version must be 2.0");
            if (gl.TryGetProperty("extensionsRequired", out var req) && !(req.ValueKind == JsonValueKind.Array && req.GetArrayLength() == 0))
                throw new MbmapException("glb: required extensions are not allowed");
            var buffers = Json.OptObjects(gl, "buffers", "glb");
            if (buffers.Count > 1) throw new MbmapException("glb: at most one (GLB-stored) buffer is allowed");
            long blen = 0;
            if (buffers.Count == 1)
            {
                if (!hasBin) throw new MbmapException("glb: buffer declared without a BIN chunk");
                if (buffers[0].TryGetProperty("uri", out _)) throw new MbmapException("glb: external or data-URI buffers are not allowed");
                blen = Json.Long(buffers[0], "byteLength", "glb: buffer");
                if (blen < 0 || blen > binLen || binLen - blen > 3) throw new MbmapException("glb: buffer byteLength does not match the BIN chunk");
            }
            var views = Json.OptObjects(gl, "bufferViews", "glb");

            // Schema 2.1 textures: PNG headers only (no decode), embedded in the BIN chunk (glb.py _check_textures).
            var images = Json.OptObjects(gl, "images", "glb");
            var textures = Json.OptObjects(gl, "textures", "glb");
            var samplers = Json.OptObjects(gl, "samplers", "glb");
            var materials = Json.OptObjects(gl, "materials", "glb");
            imageSha256 = new List<string>();
            long imageBytes = 0;
            for (int i = 0; i < images.Count; i++)
            {
                var im = images[i];
                if (im.TryGetProperty("uri", out _)) throw new MbmapException("glb: external image URIs are not allowed");
                if (!im.TryGetProperty("mimeType", out var mt) || mt.ValueKind != JsonValueKind.String || mt.GetString() != "image/png")
                    throw new MbmapException($"glb: image #{i} must have mimeType image/png");
                if (blen == 0 || !IsIndex(im, "bufferView", views.Count, out long vi))
                    throw new MbmapException($"glb: image #{i} bufferView is missing or out of range");
                var v = views[(int)vi];
                long voff = 0, vlen = 0;
                bool ok = (!v.TryGetProperty("buffer", out var vb) || (vb.ValueKind == JsonValueKind.Number && vb.TryGetInt64(out long bn) && bn == 0))
                          && (!v.TryGetProperty("byteOffset", out var vo) || (vo.ValueKind == JsonValueKind.Number && vo.TryGetInt64(out voff)))
                          && v.TryGetProperty("byteLength", out var vl) && vl.ValueKind == JsonValueKind.Number && vl.TryGetInt64(out vlen);
                if (!ok || voff < 0 || vlen < 0 || voff > blen || vlen > blen - voff)
                    throw new MbmapException($"glb: image #{i} bufferView points outside the BIN chunk");
                imageBytes += vlen;
                if (imageBytes > Limits.MaxTextureBytes) throw new MbmapException($"glb: embedded images exceed {Limits.MaxTextureBytes} bytes in total");
                int at = (int)(binOff + voff);
                if (vlen < 33 || Bin.U32(data, at) != 0x474E5089u || Bin.U32(data, at + 4) != 0x0A1A0A0Du
                    || Bin.U32(data, at + 8) != 0x0D000000u || Bin.U32(data, at + 12) != 0x52444849u)
                    throw new MbmapException($"glb: image #{i} is not a PNG (signature or IHDR mismatch)");
                long w = BinaryPrimitives.ReadUInt32BigEndian(new ReadOnlySpan<byte>(data, at + 16, 4));
                long h = BinaryPrimitives.ReadUInt32BigEndian(new ReadOnlySpan<byte>(data, at + 20, 4));
                foreach (long side in new[] { w, h })
                    if (side < 1 || side > Limits.MaxTextureSide || (side & (side - 1)) != 0)
                        throw new MbmapException($"glb: image #{i} is {w}x{h}; each side must be a power of two <= {Limits.MaxTextureSide}");
                imageSha256.Add(HexSha256(data, at, (int)vlen));
            }
            for (int i = 0; i < textures.Count; i++)
            {
                if (!IsIndex(textures[i], "source", images.Count, out _)) throw new MbmapException($"glb: texture #{i} source is missing or out of range");
                if (textures[i].TryGetProperty("sampler", out _) && !IsIndex(textures[i], "sampler", samplers.Count, out _))
                    throw new MbmapException($"glb: texture #{i} sampler is out of range");
            }
            var texturedMaterials = new HashSet<long>();
            for (int i = 0; i < materials.Count; i++)
            {
                if (!materials[i].TryGetProperty("pbrMetallicRoughness", out var pbr) || pbr.ValueKind != JsonValueKind.Object
                    || !pbr.TryGetProperty("baseColorTexture", out var bct) || bct.ValueKind == JsonValueKind.Null) continue;
                if (bct.ValueKind != JsonValueKind.Object || !IsIndex(bct, "index", textures.Count, out _))
                    throw new MbmapException($"glb: material #{i} baseColorTexture.index is missing or out of range");
                if (bct.TryGetProperty("texCoord", out var tc) && !(tc.ValueKind == JsonValueKind.Number && tc.TryGetInt64(out long tcv) && tcv == 0))
                    throw new MbmapException($"glb: material #{i} baseColorTexture.texCoord must be 0");
                texturedMaterials.Add(i);
            }
            var accessors = Json.OptObjects(gl, "accessors", "glb");
            var meshes = Json.OptObjects(gl, "meshes", "glb");
            var nodes = Json.OptObjects(gl, "nodes", "glb", Limits.MaxNodes);

            long triBudget = 0, posBudget = 0;
            var meshCache = new Dictionary<int, List<Triangle>>();
            var posCache = new Dictionary<int, float[]>();

            void SpendTriangles(long n)
            {
                if (n < 0 || n > Limits.MaxVisualTriangles - triBudget) throw new MbmapException($"glb: more than {Limits.MaxVisualTriangles} visual triangles");
                triBudget += n;
            }

            List<Triangle> MeshTriangles(int mi)
            {
                if (meshCache.TryGetValue(mi, out var cached))
                {
                    SpendTriangles(cached.Count); // instanced mesh: its triangles count again
                    return cached;
                }
                var outList = new List<Triangle>();
                int pk = 0;
                foreach (var p in Json.Array(meshes[mi], "primitives", "glb: mesh"))
                {
                    string tag = $"glb: mesh {mi} primitive {pk++}";
                    if (p.ValueKind != JsonValueKind.Object) throw new MbmapException($"{tag} must be an object");
                    long mode = p.TryGetProperty("mode", out var md) ? Json.AsLong(md, $"{tag}.mode") : 4;
                    if (mode == 5 || mode == 6) throw new MbmapException("glb: triangle strips/fans are not supported");
                    if (mode < 0 || mode > 6) throw new MbmapException("glb: invalid primitive mode");
                    if (p.TryGetProperty("targets", out var tg) && !(tg.ValueKind == JsonValueKind.Array && tg.GetArrayLength() == 0))
                        throw new MbmapException("glb: morph targets are not allowed");
                    if (mode != 4) continue;
                    var attrs = Json.Obj(p, "attributes", tag);
                    int pai = Json.Index(attrs, "POSITION", accessors.Count, $"{tag}.attributes");

                    // Validate all metadata and budgets before allocating anything.
                    var pos = Locate(pai, true, $"glb: accessor {pai}");
                    int nverts = (int)pos.Count; // Locate bounds count by the buffer length (< 2 GiB)
                    AccessorView idx = default;
                    long nIdx;
                    if (p.TryGetProperty("indices", out var ie))
                    {
                        int iai = Json.AsIndex(ie, accessors.Count, $"{tag}.indices");
                        idx = Locate(iai, false, $"glb: accessor {iai}");
                        nIdx = idx.Count;
                    }
                    else nIdx = nverts;
                    if (nIdx % 3 != 0) throw new MbmapException($"{tag}: triangle index count is not a multiple of 3");
                    SpendTriangles(nIdx / 3);

                    if (!posCache.TryGetValue(pai, out var pv))
                    {
                        if (pos.Count > Limits.MaxVisualPositions - posBudget) throw new MbmapException($"glb: more than {Limits.MaxVisualPositions} decoded POSITION vertices");
                        posBudget += pos.Count;
                        pv = new float[3L * nverts];
                        for (long k = 0; k < nverts; k++)
                            for (int c = 0; c < 3; c++)
                            {
                                float x = Bin.F32(data, (int)(pos.Start + k * pos.Stride + 4 * c));
                                if (!float.IsFinite(x)) throw new MbmapException("glb: non-finite POSITION");
                                pv[3 * k + c] = x;
                            }
                        posCache[pai] = pv;
                    }
                    if (p.TryGetProperty("material", out var pmat) && pmat.ValueKind == JsonValueKind.Number && pmat.TryGetInt64(out long pmi)
                        && texturedMaterials.Contains(pmi))
                    {
                        if (!attrs.TryGetProperty("TEXCOORD_0", out _)) throw new MbmapException("glb: a textured primitive is missing TEXCOORD_0");
                        int uai = Json.Index(attrs, "TEXCOORD_0", accessors.Count, $"{tag}.attributes");
                        var uv = Locate(uai, false, $"glb: accessor {uai}", true);
                        if (uv.Count != pos.Count) throw new MbmapException("glb: TEXCOORD_0 count differs from POSITION count");
                        for (long k = 0; k < uv.Count; k++)
                            for (int c = 0; c < 2; c++)
                                if (!float.IsFinite(Bin.F32(data, (int)(uv.Start + k * uv.Stride + 4 * c)))) throw new MbmapException("glb: non-finite TEXCOORD_0");
                    }
                    int[] ix = new int[nIdx];
                    if (idx.Count == 0) for (int k = 0; k < ix.Length; k++) ix[k] = k;
                    else
                        for (long k = 0; k < nIdx; k++)
                        {
                            int o = (int)(idx.Start + k * idx.Stride);
                            uint v = idx.ComponentType == 5125 ? Bin.U32(data, o)
                                   : idx.ComponentType == 5123 ? BinaryPrimitives.ReadUInt16LittleEndian(new ReadOnlySpan<byte>(data, o, 2)) : data[o];
                            if (v >= (uint)nverts) throw new MbmapException($"{tag}: vertex index out of range");
                            ix[k] = (int)v;
                        }
                    Vec3 P(int i) => new Vec3(pv[3L * i], pv[3L * i + 1], pv[3L * i + 2]);
                    for (int k = 0; k < ix.Length; k += 3) outList.Add(new Triangle(P(ix[k]), P(ix[k + 1]), P(ix[k + 2])));
                }
                meshCache[mi] = outList;
                return outList;
            }

            // Validates an accessor (position: float32 VEC3; otherwise unsigned integer scalars) and its
            // bufferView against the BIN chunk, without allocating. Every range check is subtraction-based on
            // values already known to be non-negative, so no untrusted sum can overflow.
            AccessorView Locate(int ai, bool position, string tag, bool uv = false)
            {
                var a = accessors[ai];
                if (a.TryGetProperty("sparse", out _)) throw new MbmapException("glb: sparse accessors are not supported");
                long ct = Json.Long(a, "componentType", tag);
                string type = Json.Str(a, "type", tag);
                int size = ct == 5126 || ct == 5125 ? 4 : ct == 5123 || ct == 5122 ? 2 : ct == 5121 || ct == 5120 ? 1 : 0;
                int nc = type == "SCALAR" ? 1 : type == "VEC2" ? 2 : type == "VEC3" ? 3 : 0;
                bool normalized = a.TryGetProperty("normalized", out var nz) && Json.AsBool(nz, $"{tag}.normalized");
                if (position && (ct != 5126 || nc != 3 || normalized))
                    throw new MbmapException("glb: POSITION must be float32 VEC3");
                if (uv && (ct != 5126 || nc != 2 || normalized))
                    throw new MbmapException("glb: TEXCOORD_0 must be float32 VEC2");
                if (!position && !uv && (nc != 1 || normalized || !(ct == 5121 || ct == 5123 || ct == 5125)))
                    throw new MbmapException("glb: indices must be unsigned integer scalars");
                long count = Json.Long(a, "count", tag);
                if (count < 1) throw new MbmapException($"{tag}.count must be at least 1");
                int vi = Json.Index(a, "bufferView", views.Count, tag);
                var v = views[vi];
                string vtag = $"glb: bufferView {vi}";
                if ((v.TryGetProperty("buffer", out var bi) ? Json.AsLong(bi, $"{vtag}.buffer") : 0) != 0 || blen == 0)
                    throw new MbmapException("glb: only buffer 0 (the BIN chunk) is supported");
                long voff = v.TryGetProperty("byteOffset", out var vo) ? Json.AsLong(vo, $"{vtag}.byteOffset") : 0;
                long vlen = Json.Long(v, "byteLength", vtag);
                if (voff < 0 || voff > blen || vlen < 0 || vlen > blen - voff) throw new MbmapException($"{vtag}: range is outside the buffer");
                long aoff = a.TryGetProperty("byteOffset", out var ao) ? Json.AsLong(ao, $"{tag}.byteOffset") : 0;
                if (aoff < 0 || aoff > vlen || aoff % size != 0) throw new MbmapException($"{tag}: byteOffset is outside its bufferView or misaligned");
                int elem = size * nc;
                long stride = elem;
                if (v.TryGetProperty("byteStride", out var st))
                {
                    stride = Json.AsLong(st, $"{vtag}.byteStride");
                    if (stride < elem || stride > 252 || stride % 4 != 0) throw new MbmapException($"{vtag}: invalid byteStride");
                }
                long avail = vlen - aoff;
                if (avail < elem || count - 1 > (avail - elem) / stride) throw new MbmapException($"{tag}: count overruns its bufferView");
                // Now binOff + voff + aoff + stride * (count - 1) + elem <= binOff + blen <= data.Length.
                return new AccessorView { Start = binOff + voff + aoff, Count = count, Stride = stride, ComponentType = ct };
            }

            List<int> roots = new List<int>();
            var scenes = Json.OptObjects(gl, "scenes", "glb");
            if (scenes.Count > 0)
            {
                int si = gl.TryGetProperty("scene", out var se) ? Json.AsIndex(se, scenes.Count, "glb: scene") : 0;
                foreach (var r in Json.OptArray(scenes[si], "nodes")) roots.Add(Json.AsIndex(r, nodes.Count, "glb: scene node"));
            }
            else for (int i = 0; i < nodes.Count; i++) roots.Add(i);

            var result = new List<VisualNode>();
            var visited = new HashSet<int>();
            var stack = new Stack<(int node, double[] parent, int depth)>();
            for (int i = roots.Count - 1; i >= 0; i--) stack.Push((roots[i], Mat.Identity(), 0));
            while (stack.Count > 0)
            {
                var (ni, parent, depth) = stack.Pop();
                if (depth > Limits.MaxNodeDepth || !visited.Add(ni))
                    throw new MbmapException("glb: invalid node hierarchy (cycle, shared child or too deep)");
                var node = nodes[ni];
                if (node.TryGetProperty("skin", out _) || node.TryGetProperty("weights", out _)) throw new MbmapException("glb: skins and morph weights are not allowed");
                double[] m = Mat.Mul(parent, Mat.Local(node));
                var vn = new VisualNode { Name = node.TryGetProperty("name", out var nm) ? Json.AsString(nm, "glb: node name") : $"node{ni}" };
                if (node.TryGetProperty("mesh", out var me))
                {
                    int mi = Json.AsIndex(me, meshes.Count, "glb: node mesh");
                    bool flip = Mat.Det3(m) < 0; // glTF: negative determinant means clockwise front faces
                    foreach (var t in MeshTriangles(mi))
                    {
                        Vec3 a = Mat.Apply(m, t.A), b = Mat.Apply(m, t.B), c = Mat.Apply(m, t.C);
                        vn.TrianglesGltf.Add(flip ? new Triangle(a, c, b) : new Triangle(a, b, c));
                    }
                }
                result.Add(vn);
                var children = Json.OptArray(node, "children");
                for (int i = children.Count - 1; i >= 0; i--) stack.Push((Json.AsIndex(children[i], nodes.Count, "glb: node child"), m, depth + 1));
            }
            return result;
        }

        /// <summary>A validated accessor: absolute byte offset into the GLB, element count, stride, component type.</summary>
        struct AccessorView
        {
            public long Start, Count, Stride, ComponentType;
        }
    }

    /// <summary>Row-major 4x4 affine matrices (column vectors), as in glb.py.</summary>
    static class Mat
    {
        public static double[] Identity() => new double[] { 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1 };

        public static double[] Mul(double[] a, double[] b)
        {
            var r = new double[16];
            for (int i = 0; i < 4; i++)
                for (int j = 0; j < 4; j++)
                {
                    double s = 0;
                    for (int k = 0; k < 4; k++) s += a[4 * i + k] * b[4 * k + j];
                    r[4 * i + j] = s;
                }
            return r;
        }

        public static Vec3 Apply(double[] m, Vec3 p) => new Vec3(
            m[0] * p.X + m[1] * p.Y + m[2] * p.Z + m[3],
            m[4] * p.X + m[5] * p.Y + m[6] * p.Z + m[7],
            m[8] * p.X + m[9] * p.Y + m[10] * p.Z + m[11]);

        public static double Det3(double[] m) =>
            m[0] * (m[5] * m[10] - m[6] * m[9]) - m[1] * (m[4] * m[10] - m[6] * m[8]) + m[2] * (m[4] * m[9] - m[5] * m[8]);

        public static double[] Local(JsonElement node)
        {
            bool trs = node.TryGetProperty("translation", out _) || node.TryGetProperty("rotation", out _) || node.TryGetProperty("scale", out _);
            if (node.TryGetProperty("matrix", out _))
            {
                if (trs) throw new MbmapException("glb: node has both matrix and TRS");
                var c = Json.NumArray(node, "matrix", 16, "glb: node");
                if (c[3] != 0 || c[7] != 0 || c[11] != 0 || c[15] != 1) throw new MbmapException("glb: node matrix is not affine");
                var r = new double[16];
                for (int row = 0; row < 4; row++) for (int col = 0; col < 4; col++) r[4 * row + col] = c[4 * col + row]; // column-major
                return r;
            }
            var t = node.TryGetProperty("translation", out _) ? Json.NumArray(node, "translation", 3, "glb: node") : new double[3];
            var q = node.TryGetProperty("rotation", out _) ? Json.NumArray(node, "rotation", 4, "glb: node") : new double[] { 0, 0, 0, 1 };
            var s = node.TryGetProperty("scale", out _) ? Json.NumArray(node, "scale", 3, "glb: node") : new double[] { 1, 1, 1 };
            double x = q[0], y = q[1], z = q[2], w = q[3];
            if (Math.Abs(Math.Sqrt(x * x + y * y + z * z + w * w) - 1.0) > 1e-3) throw new MbmapException("glb: rotation quaternion is not unit length");
            return new double[]
            {
                (1 - 2 * (y * y + z * z)) * s[0], 2 * (x * y - z * w) * s[1], 2 * (x * z + y * w) * s[2], t[0],
                2 * (x * y + z * w) * s[0], (1 - 2 * (x * x + z * z)) * s[1], 2 * (y * z - x * w) * s[2], t[1],
                2 * (x * z - y * w) * s[0], 2 * (y * z + x * w) * s[1], (1 - 2 * (x * x + y * y)) * s[2], t[2],
                0, 0, 0, 1,
            };
        }
    }

    public sealed class OrientationProbe
    {
        public string Node;
        public Vec3 PointMap, PointGltf, PointUnity, NormalMap, NormalUnity;
        public Triangle TriangleMap;

        public OrientationProbe Clone() => (OrientationProbe)MemberwiseClone();
    }

    /// <summary>Orientation-probe checks (docs/PACKAGE_FORMAT.md "Orientation probes").</summary>
    public static class ProbeCheck
    {
        /// <summary>Self-consistency every check relies on: unit normals (|len - 1| &lt;= 1e-4, as package.py)
        /// with a usable horizontal component, point_map off both axes and a vertex of triangle_map. Without
        /// these a scaled normal or a stray point could satisfy the dot-product tests.</summary>
        public static string Intrinsic(OrientationProbe p)
        {
            if (Math.Abs(p.NormalMap.Length - 1) > Limits.ProbeUnitTol || Math.Abs(p.NormalUnity.Length - 1) > Limits.ProbeUnitTol)
                return "normal_map/normal_unity_x_negated must be unit vectors";
            if (Math.Abs(p.NormalMap.X) < Limits.ProbeMinNormalXZ && Math.Abs(p.NormalMap.Z) < Limits.ProbeMinNormalXZ)
                return "normal_map must have |nx| >= 0.05 or |nz| >= 0.05";
            if (Math.Abs(p.PointMap.X) < Limits.ProbeMinAbsXYM || Math.Abs(p.PointMap.Y) < Limits.ProbeMinAbsXYM)
                return "point_map must have |x| >= 1 m and |y| >= 1 m";
            double tol = Limits.ProbeVertexTolM;
            var t = p.TriangleMap;
            if (Vec3.Distance(p.PointMap, t.A) > tol && Vec3.Distance(p.PointMap, t.B) > tol && Vec3.Distance(p.PointMap, t.C) > tol)
                return "triangle_map does not contain point_map";
            return null;
        }

        /// <summary>Producer fields agree with this reader's axis mapping, and triangle_map is a collision
        /// triangle of the node in CCW cyclic order whose Unity-mapped front face (with the winding flip)
        /// matches normal_unity_x_negated, and no vertex of the node lies near the X-mirror of point_map.
        /// Returns null on success, else the reason.</summary>
        public static string AgainstCollision(OrientationProbe p, CollisionMesh col, CollisionObject obj)
        {
            string why = Intrinsic(p);
            if (why != null) return why;
            if (Vec3.Distance(Axes.MapToGltf(p.PointMap), p.PointGltf) > 1e-6 || Vec3.Distance(Axes.MapToUnity(p.PointMap), p.PointUnity) > 1e-6
                || Vec3.Distance(Axes.MapToUnity(p.NormalMap), p.NormalUnity) > 1e-6)
                return "point_gltf/point_unity_x_negated/normal_unity_x_negated disagree with this reader's axis mapping";
            bool found = false;
            for (int t = obj.TriStart; t < obj.TriStart + obj.TriCount && !found; t++)
            {
                var ct = col.GetTriangle(t);
                for (int s = 0; s < 3 && !found; s++)
                    found = Vec3.Distance(p.TriangleMap.A, ct[s]) <= 1e-6 && Vec3.Distance(p.TriangleMap.B, ct[(s + 1) % 3]) <= 1e-6
                         && Vec3.Distance(p.TriangleMap.C, ct[(s + 2) % 3]) <= 1e-6;
            }
            if (!found) return "triangle_map is not a collision triangle of the node (in CCW order)";
            var n = Vec3.FaceNormal(p.TriangleMap.A, p.TriangleMap.B, p.TriangleMap.C);
            if (n == null || Vec3.Dot(n.Value, p.NormalMap) <= Limits.ProbeMinDot) return "normal_map is not the CCW front-face normal of triangle_map";
            var u = Axes.MapTriangleToUnity(p.TriangleMap);
            var nu = Vec3.FaceNormal(u.A, u.B, u.C);
            if (nu == null || Vec3.Dot(nu.Value, p.NormalUnity) <= Limits.ProbeMinDot) return "Unity-mapped collision triangle faces the wrong way";
            var mirror = new Vec3(-p.PointMap.X, p.PointMap.Y, p.PointMap.Z);
            for (int t = obj.TriStart; t < obj.TriStart + obj.TriCount; t++)
            {
                var ct = col.GetTriangle(t);
                for (int s = 0; s < 3; s++)
                    if (Vec3.Distance(ct[s], mirror) <= Limits.ProbeMirrorClearanceM)
                        return "the node has a vertex within 0.5 m of the X-mirror of point_map";
            }
            return null;
        }

        /// <summary>The consumer check after import: unityTriangles are the node's imported triangles in Unity
        /// world space and imported index order (e.g. read back from the Mesh glTFast created).</summary>
        public static string InUnity(OrientationProbe p, IReadOnlyList<Triangle> unityTriangles)
        {
            string why = Intrinsic(p);
            if (why != null) return why;
            var t0 = Axes.MapTriangleToUnity(p.TriangleMap);
            double vt = Limits.ProbeVertexTolM;
            if (Vec3.Distance(p.PointUnity, t0.A) > vt && Vec3.Distance(p.PointUnity, t0.B) > vt && Vec3.Distance(p.PointUnity, t0.C) > vt)
                return "point_unity_x_negated is not a vertex of triangle_map mapped to Unity";
            double tol = Limits.ProbeMatchM;
            bool point = false;
            foreach (var t in unityTriangles)
                if (Vec3.Distance(t.A, p.PointUnity) <= tol || Vec3.Distance(t.B, p.PointUnity) <= tol || Vec3.Distance(t.C, p.PointUnity) <= tol) { point = true; break; }
            if (!point) return "no vertex of the node within 5 cm of point_unity_x_negated";
            var want = new[] { Axes.MapToUnity(p.TriangleMap.A), Axes.MapToUnity(p.TriangleMap.B), Axes.MapToUnity(p.TriangleMap.C) };
            int[][] perms = { new[] { 0, 1, 2 }, new[] { 1, 2, 0 }, new[] { 2, 0, 1 }, new[] { 0, 2, 1 }, new[] { 2, 1, 0 }, new[] { 1, 0, 2 } };
            bool matched = false;
            foreach (var t in unityTriangles)
            {
                bool any = false;
                foreach (var perm in perms)
                    if (Vec3.Distance(want[0], t[perm[0]]) <= tol && Vec3.Distance(want[1], t[perm[1]]) <= tol && Vec3.Distance(want[2], t[perm[2]]) <= tol) { any = true; break; }
                if (!any) continue;
                matched = true;
                var n = Vec3.FaceNormal(t.A, t.B, t.C); // Unity: Vector3.Cross(b - a, c - a), imported index order
                if (n != null && Vec3.Dot(n.Value, p.NormalUnity) > Limits.ProbeMinDot) return null;
            }
            return matched ? "imported triangle front face does not match normal_unity_x_negated (winding or handedness wrong)"
                           : "no imported triangle matches triangle_map within 5 cm";
        }
    }

    /// <summary>A manifest passage probe: a capsule (polyline path_map, radius_m) that must stay free of collision.</summary>
    public sealed class PassageProbe
    {
        public static readonly string[] Kinds = { "bridge", "tunnel", "elevated" };
        public string Id, Kind, Feature;
        public List<Vec3> PathMap = new List<Vec3>();
        public double RadiusM;
    }

    /// <summary>Capsule-vs-collision check for passage probes; triangles are two-sided. Mirrors
    /// map_builder/core/query.py capsule_hits exactly: the same degenerate-triangle and nearly parallel segment
    /// handling, the same whole-path skip, triangle grid and plane prefilter, and the same work counting
    /// (docs/PACKAGE_FORMAT.md, "Work accounting").</summary>
    public static class CapsuleCheck
    {
        /// <summary>Object/triangle visits shared by all passage probes of one package (package.py PASSAGE_QUERY_BUDGET).</summary>
        public const long PassageQueryBudget = 2_000_000;
        /// <summary>query.py DEGENERATE_SIN: |(b - a) x (c - a)| &lt;= this x longest squared edge = degenerate.</summary>
        public const double DegenerateSin = 1e-9;
        /// <summary>query.py CONTACT_TOL_M: a triangle within radius + this is a hit (exact contact survives rounding).</summary>
        public const double ContactTolM = 1e-9;

        static Vec3 Add(Vec3 a, Vec3 d, double t) => new Vec3(a.X + d.X * t, a.Y + d.Y * t, a.Z + d.Z * t);
        static double Clamp01(double x) => x < 0 ? 0 : x > 1 ? 1 : x;
        static double Dist2(Vec3 a, Vec3 b) { var d = a - b; return Vec3.Dot(d, d); }

        static double SegmentParam(Vec3 p, Vec3 a, Vec3 ab, double den) => den == 0 ? 0 : Clamp01(Vec3.Dot(p - a, ab) / den);

        static Vec3 ClosestOnSegment(Vec3 p, Vec3 a, Vec3 b)
        {
            var ab = b - a;
            return Add(a, ab, SegmentParam(p, a, ab, Vec3.Dot(ab, ab)));
        }

        /// <summary>Collapsed (two or three equal vertices) or (nearly) collinear triangle (query.py triangle_is_degenerate).</summary>
        public static bool IsDegenerate(Vec3 a, Vec3 b, Vec3 c)
        {
            Vec3 ab = b - a, ac = c - a, bc = c - b;
            double longest = Math.Max(Vec3.Dot(ab, ab), Math.Max(Vec3.Dot(ac, ac), Vec3.Dot(bc, bc)));
            var n = Vec3.Cross(ab, ac);
            return Math.Sqrt(Vec3.Dot(n, n)) <= DegenerateSin * longest;
        }

        static Vec3 ClosestOnEdges(Vec3 p, Vec3 a, Vec3 b, Vec3 c)
        {
            Vec3 best = ClosestOnSegment(p, a, b), q = ClosestOnSegment(p, b, c), r = ClosestOnSegment(p, c, a);
            if (Dist2(p, q) < Dist2(p, best)) best = q;
            if (Dist2(p, r) < Dist2(p, best)) best = r;
            return best;
        }

        /// <summary>Closest point on triangle abc (query.py closest_point_triangle): degenerate triangles through
        /// their edges; otherwise the projection onto the plane if it lies inside, else the nearest edge point.</summary>
        public static Vec3 ClosestOnTriangle(Vec3 p, Vec3 a, Vec3 b, Vec3 c)
        {
            if (IsDegenerate(a, b, c)) return ClosestOnEdges(p, a, b, c);
            Vec3 ab = b - a, ac = c - a, ap = p - a, n = Vec3.Cross(ab, ac);
            double h = Vec3.Dot(ap, n) / Vec3.Dot(n, n);
            var q = new Vec3(ap.X - n.X * h, ap.Y - n.Y * h, ap.Z - n.Z * h);   // projection, relative to a
            if (Vec3.Dot(Vec3.Cross(ab, q), n) >= 0 && Vec3.Dot(Vec3.Cross(c - b, q - ab), n) >= 0
                && Vec3.Dot(Vec3.Cross(a - c, q - ac), n) >= 0)
                return new Vec3(a.X + q.X, a.Y + q.Y, a.Z + q.Z);
            return ClosestOnEdges(p, a, b, c);
        }

        /// <summary>Closest distance between segments p1q1 and p2q2 (query.py segment_segment_distance): the
        /// smaller of the four endpoint-to-segment distances and, whenever d1 x d2 is nonzero, the interior critical
        /// point solved with Lagrange's identity, clamped and refined by re-projection. Only exactly parallel
        /// segments or a non-finite solution fall back to the endpoint distances alone.</summary>
        public static double SegmentSegment(Vec3 p1, Vec3 q1, Vec3 p2, Vec3 q2)
        {
            Vec3 d1 = q1 - p1, d2 = q2 - p2;
            double a = Vec3.Dot(d1, d1), e = Vec3.Dot(d2, d2);
            double best = Math.Min(Math.Min(Dist2(p1, ClosestOnSegment(p1, p2, q2)), Dist2(q1, ClosestOnSegment(q1, p2, q2))),
                                   Math.Min(Dist2(p2, ClosestOnSegment(p2, p1, q1)), Dist2(q2, ClosestOnSegment(q2, p1, q1))));
            if (a > 0 && e > 0)
            {
                var n = Vec3.Cross(d1, d2);
                double den = Vec3.Dot(n, n);
                double s = den > 0 ? Vec3.Dot(n, Vec3.Cross(d2, p1 - p2)) / den : double.NaN;
                if (double.IsFinite(s))
                {
                    s = Clamp01(s);
                    double t = SegmentParam(Add(p1, d1, s), p2, d2, e);
                    s = SegmentParam(Add(p2, d2, t), p1, d1, a);
                    t = SegmentParam(Add(p1, d1, s), p2, d2, e);
                    best = Math.Min(best, Dist2(Add(p1, d1, s), Add(p2, d2, t)));
                }
            }
            return Math.Sqrt(best);
        }

        /// <summary>Two-sided segment/triangle intersection parameter along p + t (q - p), or NaN. Numerators are
        /// divided by the determinant directly (1/det overflows for a subnormal det); non-finite u, v, t miss.</summary>
        static double SegmentHit(Vec3 o, Vec3 d, Vec3 a, Vec3 b, Vec3 c)
        {
            Vec3 e1 = b - a, e2 = c - a, pv = Vec3.Cross(d, e2);
            double det = Vec3.Dot(e1, pv);
            if (det == 0) return double.NaN;
            var tv = o - a;
            double u = Vec3.Dot(tv, pv) / det;
            if (!(u >= 0 && u <= 1)) return double.NaN;
            var qv = Vec3.Cross(tv, e1);
            double v = Vec3.Dot(d, qv) / det;
            if (!(v >= 0 && u + v <= 1)) return double.NaN;
            double t = Vec3.Dot(e2, qv) / det;
            return double.IsFinite(t) ? t : double.NaN;
        }

        public static double SegmentTriangleDistance(Vec3 p, Vec3 q, Triangle tri)
        {
            double best = double.PositiveInfinity;
            if (!IsDegenerate(tri.A, tri.B, tri.C))
            {
                double t = SegmentHit(p, q - p, tri.A, tri.B, tri.C);
                if (t >= 0 && t <= 1) return 0;
                best = Math.Sqrt(Math.Min(Dist2(p, ClosestOnTriangle(p, tri.A, tri.B, tri.C)), Dist2(q, ClosestOnTriangle(q, tri.A, tri.B, tri.C))));
            }
            best = Math.Min(best, SegmentSegment(p, q, tri.A, tri.B));
            best = Math.Min(best, SegmentSegment(p, q, tri.B, tri.C));
            return Math.Min(best, SegmentSegment(p, q, tri.C, tri.A));
        }

        static bool Overlap(Vec3 lo, Vec3 hi, double x0, double y0, double z0, double x1, double y1, double z1, double pad) =>
            x0 - pad <= hi.X && lo.X <= x1 + pad && y0 - pad <= hi.Y && lo.Y <= y1 + pad && z0 - pad <= hi.Z && lo.Z <= z1 + pad;

        /// <summary>Indices of the collision objects with a triangle within radius_m of the probe path (empty = clear),
        /// without a work limit.</summary>
        public static List<int> Hits(CollisionMesh col, PassageProbe probe)
        {
            long unlimited = long.MaxValue;
            return Hits(col, probe, ref unlimited);
        }

        /// <summary>As <see cref="Hits(CollisionMesh, PassageProbe)"/>, spending one unit of <paramref name="budget"/> per
        /// object per path segment and one per triangle tested, exactly as query.py capsule_hits counts work. Returns
        /// null when the budget runs out (the probe is then unchecked); share one budget, starting at
        /// <see cref="PassageQueryBudget"/>, across all probes of a package.</summary>
        public static List<int> Hits(CollisionMesh col, PassageProbe probe, ref long budget)
        {
            var hits = new List<int>();
            double r = probe.RadiusM + ContactTolM, pad = r + Limits.AabbTableTolM;
            int np = probe.PathMap.Count, segments = Math.Max(1, np - 1);
            var sp = new Vec3[segments]; var sq = new Vec3[segments];
            var slo = new Vec3[segments]; var shi = new Vec3[segments];
            Vec3 wlo = new Vec3(double.PositiveInfinity, double.PositiveInfinity, double.PositiveInfinity);
            Vec3 whi = new Vec3(double.NegativeInfinity, double.NegativeInfinity, double.NegativeInfinity);
            for (int s = 0; s < segments; s++)
            {
                Vec3 p = probe.PathMap[s], q = probe.PathMap[Math.Min(s + 1, np - 1)];
                sp[s] = p; sq[s] = q;
                slo[s] = new Vec3(Math.Min(p.X, q.X), Math.Min(p.Y, q.Y), Math.Min(p.Z, q.Z));
                shi[s] = new Vec3(Math.Max(p.X, q.X), Math.Max(p.Y, q.Y), Math.Max(p.Z, q.Z));
                wlo = new Vec3(Math.Min(wlo.X, slo[s].X), Math.Min(wlo.Y, slo[s].Y), Math.Min(wlo.Z, slo[s].Z));
                whi = new Vec3(Math.Max(whi.X, shi[s].X), Math.Max(whi.Y, shi[s].Y), Math.Max(whi.Z, shi[s].Z));
            }
            foreach (var obj in col.Objects)
            {
                var box = obj.Aabb;
                if (segments > 1 && !Overlap(wlo, whi, box[0], box[1], box[2], box[3], box[4], box[5], pad))
                {
                    if (--budget < 0) return null;   // the whole path misses the object: one unit
                    continue;
                }
                bool hit = false;
                var grid = obj.TriCount > GridMinTris ? GridFor(col, obj) : null;
                for (int s = 0; s < segments && !hit; s++)
                {
                    if (--budget < 0) return null;
                    Vec3 p = sp[s], q = sq[s], lo = slo[s], hi = shi[s];
                    if (!Overlap(lo, hi, box[0], box[1], box[2], box[3], box[4], box[5], pad)) continue;
                    var cand = grid != null ? grid.Candidates(lo, hi, r) : null;
                    bool scan = cand == null;
                    if (!scan)
                    {
                        budget -= cand.Count;
                        if (budget < 0) return null;
                    }
                    int count = scan ? obj.TriCount : cand.Count;
                    for (int i = 0; i < count && !hit; i++)
                    {
                        int t = scan ? obj.TriStart + i : cand[i];
                        if (scan && --budget < 0) return null;
                        var tri = col.GetTriangle(t);
                        Vec3 a = tri.A, b = tri.B, c = tri.C;
                        if (!Overlap(lo, hi, Math.Min(a.X, Math.Min(b.X, c.X)), Math.Min(a.Y, Math.Min(b.Y, c.Y)), Math.Min(a.Z, Math.Min(b.Z, c.Z)),
                                     Math.Max(a.X, Math.Max(b.X, c.X)), Math.Max(a.Y, Math.Max(b.Y, c.Y)), Math.Max(a.Z, Math.Max(b.Z, c.Z)), r)) continue;
                        if (PlaneClear(p, q, a, b, c, r)) continue;
                        hit = SegmentTriangleDistance(p, q, tri) <= r;
                    }
                }
                if (hit) hits.Add(obj.Index);
            }
            return hits;
        }

        /// <summary>query.py _plane_clear: both segment ends farther than reach from the triangle's plane on the same side.</summary>
        static bool PlaneClear(Vec3 p, Vec3 q, Vec3 a, Vec3 b, Vec3 c, double reach)
        {
            double ux = b.X - a.X, uy = b.Y - a.Y, uz = b.Z - a.Z, vx = c.X - a.X, vy = c.Y - a.Y, vz = c.Z - a.Z;
            double nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
            double nn = Math.Sqrt(nx * nx + ny * ny + nz * nz);
            if (nn < 1e-12) return false;
            double dp = nx * (p.X - a.X) + ny * (p.Y - a.Y) + nz * (p.Z - a.Z);
            double dq = nx * (q.X - a.X) + ny * (q.Y - a.Y) + nz * (q.Z - a.Z);
            double lim = (reach + 1e-6) * nn;
            return (dp > lim && dq > lim) || (dp < -lim && dq < -lim);
        }

        /// <summary>query.py _GRID_MIN_TRIS: objects with more triangles than this get a triangle grid.</summary>
        public const int GridMinTris = 256;
        public const double GridCellM = 8.0;
        public const int GridMaxTriCells = 64;
        public const int GridMaxQueryCells = 1024;

        sealed class TriGrid
        {
            public readonly Dictionary<(long, long), List<int>> Cells = new Dictionary<(long, long), List<int>>();
            public readonly List<int> Big = new List<int>();

            /// <summary>query.py _grid_candidates: sorted triangle ids near the box, or null when it spans too many cells.</summary>
            public List<int> Candidates(Vec3 lo, Vec3 hi, double reach)
            {
                double i0 = Math.Floor((lo.X - reach) / GridCellM), i1 = Math.Floor((hi.X + reach) / GridCellM);
                double j0 = Math.Floor((lo.Y - reach) / GridCellM), j1 = Math.Floor((hi.Y + reach) / GridCellM);
                if ((i1 - i0 + 1) * (j1 - j0 + 1) > GridMaxQueryCells) return null;
                var set = new SortedSet<int>(Big);
                for (long i = (long)i0; i <= (long)i1; i++)
                    for (long j = (long)j0; j <= (long)j1; j++)
                        if (Cells.TryGetValue((i, j), out var l)) set.UnionWith(l);
                return new List<int>(set);
            }
        }

        static readonly System.Runtime.CompilerServices.ConditionalWeakTable<CollisionMesh, Dictionary<int, TriGrid>> Grids =
            new System.Runtime.CompilerServices.ConditionalWeakTable<CollisionMesh, Dictionary<int, TriGrid>>();

        static TriGrid GridFor(CollisionMesh col, CollisionObject obj)
        {
            var perMesh = Grids.GetOrCreateValue(col);
            lock (perMesh)
            {
                if (perMesh.TryGetValue(obj.Index, out var g)) return g;
                g = new TriGrid();
                for (int t = obj.TriStart; t < obj.TriStart + obj.TriCount; t++)
                {
                    var tri = col.GetTriangle(t);
                    Vec3 a = tri.A, b = tri.B, c = tri.C;
                    double i0 = Math.Floor(Math.Min(a.X, Math.Min(b.X, c.X)) / GridCellM), i1 = Math.Floor(Math.Max(a.X, Math.Max(b.X, c.X)) / GridCellM);
                    double j0 = Math.Floor(Math.Min(a.Y, Math.Min(b.Y, c.Y)) / GridCellM), j1 = Math.Floor(Math.Max(a.Y, Math.Max(b.Y, c.Y)) / GridCellM);
                    if ((i1 - i0 + 1) * (j1 - j0 + 1) > GridMaxTriCells) { g.Big.Add(t); continue; }
                    for (long i = (long)i0; i <= (long)i1; i++)
                        for (long j = (long)j0; j <= (long)j1; j++)
                        {
                            if (!g.Cells.TryGetValue((i, j), out var l)) g.Cells[(i, j)] = l = new List<int>();
                            l.Add(t);
                        }
                }
                return perMesh[obj.Index] = g;
            }
        }

        /// <summary>A collision mesh built in code from (class, vertices, triangle indices) objects, for controls.</summary>
        public static CollisionMesh Synthetic(params (CollisionClass cls, Vec3[] vertices, int[] indices)[] objects)
        {
            var verts = new List<float>();
            var idx = new List<uint>();
            var triObj = new List<uint>();
            var triCls = new List<byte>();
            var objs = new CollisionObject[objects.Length];
            for (int k = 0; k < objects.Length; k++)
            {
                var (cls, vs, ix) = objects[k];
                uint baseV = (uint)(verts.Count / 3);
                var box = new[] { double.MaxValue, double.MaxValue, double.MaxValue, double.MinValue, double.MinValue, double.MinValue };
                foreach (var v in vs)
                {
                    verts.Add((float)v.X); verts.Add((float)v.Y); verts.Add((float)v.Z);
                    box[0] = Math.Min(box[0], (float)v.X); box[1] = Math.Min(box[1], (float)v.Y); box[2] = Math.Min(box[2], (float)v.Z);
                    box[3] = Math.Max(box[3], (float)v.X); box[4] = Math.Max(box[4], (float)v.Y); box[5] = Math.Max(box[5], (float)v.Z);
                }
                objs[k] = new CollisionObject { Index = k, Name = $"control{k}", MbId = $"control:{k}", Class = CollisionMesh.ClassNames[(int)cls],
                                                TriStart = triObj.Count, TriCount = ix.Length / 3, Aabb = box };
                foreach (var i in ix) idx.Add(baseV + (uint)i);
                for (int t = 0; t < ix.Length / 3; t++) { triObj.Add((uint)k); triCls.Add((byte)cls); }
            }
            return new CollisionMesh { Version = 2, Vertices = verts.ToArray(), Indices = idx.ToArray(), TriangleObject = triObj.ToArray(),
                                       TriangleClass = triCls.ToArray(), Objects = objs };
        }

        static PassageProbe Capsule(double radius, params Vec3[] path)
        {
            var p = new PassageProbe { Id = "control", Kind = "bridge", Feature = "control:0", RadiusM = radius };
            p.PathMap.AddRange(path);
            return p;
        }

        /// <summary>Controls of the capsule check on fixed geometry built in code (independent of any package):
        /// a box hit through its middle and missed above and beside it (grazing at radius +/- 1 mm), a collapsed
        /// (a == b) triangle measured through its edges, a nearly parallel 100 km segment that must keep 0.1 mm
        /// precision (Python test_query regression case), a shallow crossing of a collapsed 200 km edge, a grazing
        /// segment with a subnormal determinant, and budget exhaustion. Returns the failed checks.</summary>
        public static List<string> SelfTest()
        {
            var failed = new List<string>();
            var bv = new List<Vec3>();
            foreach (var z in new[] { 0.0, 10.0 })
                foreach (var (x, y) in new[] { (10.0, -5.0), (20.0, -5.0), (20.0, 5.0), (10.0, 5.0) }) bv.Add(new Vec3(x, y, z));
            var quads = new[] { (0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7) };
            var bi = new List<int>();
            foreach (var (a, b, c, d) in quads) bi.AddRange(new[] { a, b, c, a, c, d });
            var box = Synthetic((CollisionClass.Building, bv.ToArray(), bi.ToArray()));
            void Expect(string what, CollisionMesh col, PassageProbe probe, bool hit)
            {
                var h = Hits(col, probe);
                if ((h.Count > 0) != hit) failed.Add($"{what}: expected {(hit ? "BLOCKED" : "PASS")}");
            }
            const double r = 1.5, eps = 1e-3;
            Expect("through the box", box, Capsule(1.0, new Vec3(0, 0, 5), new Vec3(25, 0, 5)), true);
            Expect("above the box", box, Capsule(2.0, new Vec3(0, 0, 13), new Vec3(25, 0, 13)), false);
            Expect("beside the box at r + 1 mm", box, Capsule(r, new Vec3(0, -5 - r - eps, 5), new Vec3(25, -5 - r - eps, 5)), false);
            Expect("beside the box at r - 1 mm", box, Capsule(r, new Vec3(0, -5 - r + eps, 5), new Vec3(25, -5 - r + eps, 5)), true);
            var sliver = Synthetic((CollisionClass.Prop, new[] { new Vec3(0, 0, 0), new Vec3(0, 0, 0), new Vec3(0, 4, 0) }, new[] { 0, 1, 2 }));
            Expect("collapsed triangle within r", sliver, Capsule(1.2, new Vec3(1, 2, 0.5), new Vec3(1, 3, 0.5)), true);
            Expect("collapsed triangle beyond r", sliver, Capsule(1.1, new Vec3(1, 2, 0.5), new Vec3(1, 3, 0.5)), false);
            var deck = Synthetic((CollisionClass.Bridge, new[] { new Vec3(0, 0, 0), new Vec3(100000, 0, 0), new Vec3(50000, -1, 0) }, new[] { 0, 1, 2 }));
            Vec3 p0 = new Vec3(0, 0.0001, -0.001), p1 = new Vec3(100000, 0.0001, 0.001);
            Expect("nearly parallel path 0.1 mm from an edge, r 0.15 mm", deck, Capsule(0.00015, p0, p1), true);
            Expect("nearly parallel path 0.1 mm from an edge, r 0.05 mm", deck, Capsule(0.00005, p0, p1), false);
            double dist = SegmentTriangleDistance(p0, p1, deck.GetTriangle(0));
            if (!(Math.Abs(dist - 0.0001) <= 1e-9)) failed.Add($"nearly parallel distance {dist} m, expected 0.0001 m");
            // Shallow crossing (review round 2): sin^2 = 2.5e-25 is below the old parallel cutoff; the path crosses
            // the collapsed triangle's edge exactly at its midpoint.
            var edge = Synthetic((CollisionClass.Prop, new[] { new Vec3(0, 0, 0), new Vec3(200000, 0, 0), new Vec3(200000, 0, 0) }, new[] { 0, 1, 2 }));
            Vec3 s0 = new Vec3(0, -5e-8, 0), s1 = new Vec3(200000, 5e-8, 0);
            Expect("shallow crossing of a collapsed 200 km edge, r 1e-8 m", edge, Capsule(1e-8, s0, s1), true);
            double cross = SegmentSegment(s0, s1, new Vec3(0, 0, 0), new Vec3(200000, 0, 0));
            if (cross != 0) failed.Add($"shallow crossing distance {cross} m, expected 0");
            // Grazing segment (review round 2): det = 1e-310, so 1/det overflowed and u = 0 * inf was NaN.
            double g = SegmentHit(new Vec3(0, 0, 0), new Vec3(1, 0, -1e-310), new Vec3(0, 0, 0), new Vec3(1, 0, 0), new Vec3(0, 1, 0));
            if (g != 0) failed.Add($"grazing segment hit parameter {g}, expected 0");
            long budget = 3;
            if (Hits(box, Capsule(1.0, new Vec3(0, 0, 5), new Vec3(25, 0, 5)), ref budget) != null) failed.Add("work budget of 3 was not exhausted");
            return failed;
        }
    }

    public sealed class FileEntry
    {
        public string Path, Role, MediaType, Sha256;
        public long Bytes;
    }

    public sealed class SourceInfo
    {
        public string Kind, Provider, Product, Attribution; // Product may be null
    }

    /// <summary>The manifest fields a consumer displays, validated (presence and JSON kind) as package.py does.</summary>
    public sealed class ManifestSummary
    {
        public string Name, SchemaVersion, CreatedUtc, VerticalDatum;
        public double OriginLatDeg, OriginLonDeg, ZOffsetM, WidthM, HeightM;
        public List<SourceInfo> Sources = new List<SourceInfo>();
        public List<AssetNotice> AssetNotices = new List<AssetNotice>();

        internal static ManifestSummary Read(JsonElement m)
        {
            var s = new ManifestSummary
            {
                Name = Json.NonEmptyStr(m, "name", "manifest"),
                SchemaVersion = Json.Str(m, "schema_version", "manifest"),
                CreatedUtc = Json.Str(m, "created_utc", "manifest"),
            };
            if (!MbmapPackage.IsUtc(s.CreatedUtc)) throw new MbmapException("manifest.created_utc must be an ISO-8601 UTC timestamp (YYYY-MM-DDTHH:MM:SSZ)");
            var geo = Json.Obj(m, "georeference", "manifest");
            var origin = Json.Obj(geo, "origin", "manifest.georeference");
            s.OriginLatDeg = Json.Num(origin, "lat_deg", "manifest.georeference.origin");
            s.OriginLonDeg = Json.Num(origin, "lon_deg", "manifest.georeference.origin");
            if (s.OriginLatDeg < -84 || s.OriginLatDeg > 84 || s.OriginLonDeg < -180 || s.OriginLonDeg > 180)
                throw new MbmapException("manifest.georeference.origin is out of range");
            if (Json.Str(geo, "horizontal_datum", "manifest.georeference") != MbmapPackage.HorizontalDatum)
                throw new MbmapException($"manifest.georeference.horizontal_datum must be '{MbmapPackage.HorizontalDatum}'");
            Json.NonEmptyStr(geo, "projection", "manifest.georeference");
            s.VerticalDatum = Json.NonEmptyStr(geo, "vertical_datum", "manifest.georeference");
            s.ZOffsetM = Json.Num(geo, "z_offset_m", "manifest.georeference");
            if (Json.Str(geo, "height_formula", "manifest.georeference") != MbmapPackage.HeightFormula)
                throw new MbmapException($"manifest.georeference.height_formula must be '{MbmapPackage.HeightFormula}'");
            if (Json.Str(geo, "units", "manifest.georeference") != "metre") throw new MbmapException("manifest.georeference.units must be 'metre'");
            var area = Json.Obj(m, "area", "manifest");
            s.WidthM = Json.Num(area, "width_m", "manifest.area");
            s.HeightM = Json.Num(area, "height_m", "manifest.area");
            if (!(s.WidthM > 0) || !(s.HeightM > 0)) throw new MbmapException("manifest.area.width_m/height_m must be positive");
            var sources = Json.Array(m, "sources", "manifest");
            if (sources.Count == 0) throw new MbmapException("manifest.sources must be a non-empty array");
            bool elevation = false;
            for (int i = 0; i < sources.Count; i++)
            {
                string tag = $"manifest.sources[{i}]";
                var e = sources[i];
                if (e.ValueKind != JsonValueKind.Object) throw new MbmapException($"{tag} must be an object");
                var src = new SourceInfo
                {
                    Kind = Json.Str(e, "kind", tag), Provider = Json.NonEmptyStr(e, "provider", tag),
                    Attribution = Json.Str(e, "attribution", tag), Product = Json.OptStrOrNull(e, "product", tag),
                };
                if (src.Kind != "elevation" && src.Kind != "features") throw new MbmapException($"{tag}.kind must be 'elevation' or 'features'");
                var lic = Json.Obj(e, "license", tag);
                if (!lic.EnumerateObject().MoveNext()) throw new MbmapException($"{tag}.license must not be empty");
                elevation |= src.Kind == "elevation";
                s.Sources.Add(src);
            }
            if (!elevation) throw new MbmapException("manifest: no elevation source (vertical datum provenance missing)");
            if (m.TryGetProperty("asset_notices", out var an))
            {
                if (an.ValueKind != JsonValueKind.Array) throw new MbmapException("manifest: asset_notices must be an array");
                int k = 0;
                foreach (var e in an.EnumerateArray())
                {
                    string tag = $"manifest.asset_notices[{k++}]";
                    if (e.ValueKind != JsonValueKind.Object) throw new MbmapException($"{tag} must be an object");
                    var n = new AssetNotice { Name = Json.NonEmptyStr(e, "name", tag), Attribution = Json.NonEmptyStr(e, "attribution", tag) };
                    var lic = Json.Obj(e, "license", tag);
                    bool declares = false;
                    foreach (var key in new[] { "id", "name", "text", "url" })
                        if (lic.TryGetProperty(key, out var lv))
                        {
                            if (lv.ValueKind != JsonValueKind.String) throw new MbmapException($"{tag}.license.{key} must be a string");
                            if (lv.GetString().Length > 0) n.LicenseValues.Add((key, lv.GetString()));
                            declares |= key != "url" && lv.GetString().Length > 0;
                        }
                    if (!declares) throw new MbmapException($"{tag}.license must declare a licence identifier, name or text");
                    var hashes = Json.Array(e, "sha256", tag);
                    if (hashes.Count == 0) throw new MbmapException($"{tag}.sha256 must be a non-empty array of 64 lowercase hex digits");
                    foreach (var h in hashes)
                    {
                        string hs = h.ValueKind == JsonValueKind.String ? h.GetString() : null;
                        if (hs == null || !Regex.IsMatch(hs, "^[0-9a-f]{64}\\z")) throw new MbmapException($"{tag}.sha256 must be a non-empty array of 64 lowercase hex digits");
                        n.Sha256.Add(hs);
                    }
                    s.AssetNotices.Add(n);
                }
            }
            return s;
        }
    }

    /// <summary>One schema-2.1 asset_notices[] entry: provenance of the textures whose image SHA-256 it lists.</summary>
    public sealed class AssetNotice
    {
        public string Name, Attribution;
        public List<(string Key, string Value)> LicenseValues = new List<(string, string)>();
        public List<string> Sha256 = new List<string>();
    }

    public sealed class MbmapPackage : IDisposable
    {
        public const string Schema = "map-builder.package";
        public const int SupportedMajor = 2;
        public const string VisualPath = "visual/map.glb", CollisionPath = "collision/map.mbcol", NoticesPath = "NOTICES.txt",
                            ReportPath = "report.json", HeightfieldPath = "collision/terrain.mbhf";
        public const string HorizontalDatum = "WGS84 (EPSG:4326)", HeightFormula = "H = z + z_offset_m";
        static readonly Regex SemVer = new Regex(@"^([0-9]+)\.([0-9]+)\.([0-9]+)\z");
        static readonly Regex Utc = new Regex(@"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?Z\z");
        // canonical path -> role (package.py MEMBERS); the mapping is enforced in both directions
        static readonly Dictionary<string, string> KnownRoles = new Dictionary<string, string>(StringComparer.Ordinal)
        {
            { VisualPath, "visual" }, { CollisionPath, "collision" }, { NoticesPath, "notices" },
            { ReportPath, "report" }, { HeightfieldPath, "heightfield" },
        };
        static readonly string[] RequiredRoles = { "visual", "collision", "notices" };
        static readonly Dictionary<string, string> MediaTypes = new Dictionary<string, string>(StringComparer.Ordinal)
        {
            { VisualPath, "model/gltf-binary" }, { CollisionPath, "application/vnd.map-builder.mbcol" },
            { NoticesPath, "text/plain; charset=utf-8" }, { ReportPath, "application/json" },
            { HeightfieldPath, "application/vnd.map-builder.mbhf" },
        };

        static string CanonicalPath(string role)
        {
            foreach (var kv in KnownRoles) if (kv.Value == role) return kv.Key;
            return null;
        }

        /// <summary>"sha256:" + hex SHA-256 of the raw manifest.json bytes; set only after every member verified.</summary>
        public string PackageId;
        public JsonDocument ManifestDocument;
        public JsonElement Manifest => ManifestDocument.RootElement;
        public List<FileEntry> Files = new List<FileEntry>();
        public Dictionary<string, byte[]> Members = new Dictionary<string, byte[]>(StringComparer.Ordinal);
        public CollisionMesh Collision;
        public HeightField Heightfield;   // null if the package has none
        public List<OrientationProbe> Probes = new List<OrientationProbe>();
        public List<PassageProbe> PassageProbes = new List<PassageProbe>();
        public ManifestSummary Info;      // typed, validated manifest fields a consumer displays
        public List<VisualNode> VisualNodes; // world-space triangles of the visual GLB, parsed during Load

        public void Dispose() => ManifestDocument?.Dispose();

        /// <summary>Open, verify (container bounds, files[] one-to-one, sizes, SHA-256) and parse a package.
        /// Throws MbmapException (or InvalidDataException for a corrupt zip) if anything is wrong.</summary>
        public static MbmapPackage Load(string path)
        {
            using (var fs = File.OpenRead(path))
            using (var zip = new ZipArchive(fs, ZipArchiveMode.Read))
                return Load(zip);
        }

        public static MbmapPackage Load(ZipArchive zip)
        {
            // 1. Container rules, before reading any member.
            if (zip.Entries.Count > Limits.MaxEntries) throw new MbmapException($"too many entries ({zip.Entries.Count} > {Limits.MaxEntries})");
            var entries = new Dictionary<string, ZipArchiveEntry>(StringComparer.Ordinal);
            var lowered = new HashSet<string>(StringComparer.Ordinal);
            long total = 0;
            int idx = 0;
            foreach (var en in zip.Entries)
            {
                string tag = $"entry #{idx++}"; // never echo names taken from the archive
                if (!SafeName(en.FullName)) throw new MbmapException($"unsafe entry name ({tag})");
                if (!lowered.Add(en.FullName.ToLowerInvariant())) throw new MbmapException($"duplicate entry ({tag}; names differ at most in case)");
                int mode = (en.ExternalAttributes >> 16) & 0xF000;
                if (mode != 0 && mode != 0x8000) throw new MbmapException($"{tag} is not a regular file (directory or symlink)");
                if (en.Length > 0 && (en.CompressedLength == 0 || en.Length > Limits.MaxRatio * en.CompressedLength))
                    throw new MbmapException($"{tag} compression ratio exceeds {Limits.MaxRatio}");
                total += en.Length;
                entries[en.FullName] = en;
            }
            if (total > Limits.MaxTotalUncompressed) throw new MbmapException("uncompressed size exceeds 1.5 GiB");
            if (!entries.TryGetValue("manifest.json", out var me)) throw new MbmapException("manifest.json missing");
            if (me.Length > Limits.MaxManifestBytes) throw new MbmapException("manifest.json exceeds 32 MiB");

            // 2. Manifest: raw bytes kept for the identity; parsed strictly.
            var pkg = new MbmapPackage();
            try
            {
                byte[] manifestBytes = ReadAll(me, "manifest.json");
                pkg.ManifestDocument = StrictJson.Parse(manifestBytes, "manifest.json");
                var m = pkg.Manifest;
                if (m.ValueKind != JsonValueKind.Object) throw new MbmapException("manifest.json must be a JSON object");
                if (Json.Str(m, "schema", "manifest") != Schema) throw new MbmapException($"manifest: schema must be '{Schema}'");
                var sv = SemVer.Match(Json.Str(m, "schema_version", "manifest"));
                if (!sv.Success) throw new MbmapException("manifest: schema_version must be MAJOR.MINOR.PATCH");
                if (sv.Groups[1].Value != SupportedMajor.ToString()) throw new MbmapException($"manifest: unsupported schema major version {sv.Groups[1].Value}");

                // 3. files[] <-> members one-to-one, and canonical path <-> role in both directions (package.py
                //    MEMBERS): a canonical path must carry its role, a canonical role must use its path, and any
                //    other member is "unknown" (a reference-validator warning; warnings are errors).
                int k = 0;
                var listed = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
                var roles = new HashSet<string>(StringComparer.Ordinal);
                foreach (var f in Json.Array(m, "files", "manifest"))
                {
                    string tag = $"manifest: files[{k++}]";
                    if (f.ValueKind != JsonValueKind.Object) throw new MbmapException($"{tag} must be an object");
                    var fe = new FileEntry
                    {
                        Path = Json.Str(f, "path", tag), Role = Json.Str(f, "role", tag), MediaType = Json.Str(f, "media_type", tag),
                        Sha256 = Json.Str(f, "sha256", tag), Bytes = Json.Long(f, "bytes", tag),
                    };
                    if (fe.Path == "manifest.json" || !SafeName(fe.Path)) throw new MbmapException($"{tag}.path must be a safe relative member path other than manifest.json");
                    if (!listed.Add(fe.Path)) throw new MbmapException($"{tag}.path lists a member path twice");
                    if (KnownRoles.TryGetValue(fe.Path, out var role))
                    {
                        if (fe.Role != role) throw new MbmapException($"{tag} ({fe.Path}) must have role '{role}'");
                        if (fe.MediaType != MediaTypes[fe.Path]) throw new MbmapException($"{tag} ({fe.Path}): media_type must be '{MediaTypes[fe.Path]}'");
                        if (!roles.Add(role)) throw new MbmapException($"manifest: role '{role}' listed twice");
                    }
                    else
                    {
                        string canonical = CanonicalPath(fe.Role);
                        if (canonical != null) throw new MbmapException($"{tag}: role '{fe.Role}' must use path '{canonical}'");
                        throw new MbmapException($"{tag}: unknown package member (warnings are errors)");
                    }
                    pkg.Files.Add(fe);
                }
                foreach (var req in RequiredRoles)
                    if (!roles.Contains(req)) throw new MbmapException($"manifest: required member {CanonicalPath(req)} (role '{req}') not listed");
                foreach (var name in entries.Keys)
                    if (name != "manifest.json" && !listed.Contains(name)) throw new MbmapException("unlisted file in package");
                foreach (var fe in pkg.Files)
                {
                    if (!entries.TryGetValue(fe.Path, out var en)) throw new MbmapException($"listed file missing from package: {Label(fe.Path)}");
                    if (en.Length != fe.Bytes) throw new MbmapException($"{Label(fe.Path)}: size {en.Length} != manifest bytes {fe.Bytes}");
                    byte[] data = ReadAll(en, Label(fe.Path));
                    if (!string.Equals(Hex(Sha256(data)), fe.Sha256, StringComparison.Ordinal)) throw new MbmapException($"{Label(fe.Path)}: SHA-256 mismatch");
                    pkg.Members[fe.Path] = data;
                }

                // Manifest fields that name members must name the canonical ones.
                if (Json.Str(Json.Obj(m, "visual", "manifest"), "path", "manifest.visual") != VisualPath)
                    throw new MbmapException($"manifest: visual.path must be '{VisualPath}'");
                var colInfo = Json.Obj(m, "collision", "manifest");
                if (Json.Str(colInfo, "path", "manifest.collision") != CollisionPath)
                    throw new MbmapException($"manifest: collision.path must be '{CollisionPath}'");
                if (Json.Str(colInfo, "format", "manifest.collision") != "mbcol" || Json.Long(colInfo, "version", "manifest.collision") != 2
                    || Json.Str(colInfo, "frame", "manifest.collision") != "map" || Json.Str(colInfo, "winding", "manifest.collision") != "ccw_outward")
                    throw new MbmapException("manifest: collision must be {format: 'mbcol', version: 2, frame: 'map', winding: 'ccw_outward'}");
                bool hasHf = m.TryGetProperty("heightfield", out var hfInfo) && hfInfo.ValueKind != JsonValueKind.Null;
                if (hasHf)
                {
                    if (hfInfo.ValueKind != JsonValueKind.Object) throw new MbmapException("manifest: heightfield must be an object or null");
                    if (Json.Str(hfInfo, "path", "manifest.heightfield") != HeightfieldPath)
                        throw new MbmapException($"manifest: heightfield.path must be '{HeightfieldPath}'");
                }
                if (hasHf != roles.Contains("heightfield"))
                    throw new MbmapException("manifest: heightfield must be non-null exactly when the heightfield member is listed");
                if (Json.Str(m, "notices", "manifest") != NoticesPath) throw new MbmapException($"manifest: notices must be '{NoticesPath}'");
                if (Json.OptStrOrNull(m, "report", "manifest") != (roles.Contains("report") ? ReportPath : null))
                    throw new MbmapException($"manifest: report must be '{ReportPath}' when {ReportPath} is listed, otherwise null");
                pkg.Info = ManifestSummary.Read(m);

                // Visual payload and schema-2.1 asset provenance (every embedded image must be listed in
                // asset_notices[].sha256, and each notice must appear verbatim in NOTICES.txt).
                pkg.VisualNodes = Glb.Read(pkg.Member(VisualPath, "visual"), out var imageHashes);
                var listedHashes = new HashSet<string>(StringComparer.Ordinal);
                foreach (var an in pkg.Info.AssetNotices) listedHashes.UnionWith(an.Sha256);
                for (int ii = 0; ii < imageHashes.Count; ii++)
                    if (!listedHashes.Contains(imageHashes[ii]))
                        throw new MbmapException($"glb: texture without provenance: image #{ii} (SHA-256 {imageHashes[ii]}) is not listed in any asset_notices[].sha256");
                var presentHashes = new HashSet<string>(imageHashes, StringComparer.Ordinal);
                for (int ai = 0; ai < pkg.Info.AssetNotices.Count; ai++)
                    foreach (var h in pkg.Info.AssetNotices[ai].Sha256)
                        if (!presentHashes.Contains(h)) throw new MbmapException($"asset_notices[{ai}] lists SHA-256 {h}, which is not an image in visual/map.glb (warnings are errors)");
                if (pkg.Info.AssetNotices.Count > 0)
                {
                    string notices;
                    try { notices = new UTF8Encoding(false, true).GetString(pkg.Member(NoticesPath, "notices")); }
                    catch (ArgumentException) { throw new MbmapException("NOTICES.txt is not UTF-8"); }
                    for (int ai = 0; ai < pkg.Info.AssetNotices.Count; ai++)
                    {
                        var an = pkg.Info.AssetNotices[ai];
                        if (!notices.Contains(an.Attribution)) throw new MbmapException($"NOTICES.txt lacks the attribution of asset_notices[{ai}]");
                        foreach (var (key, value) in an.LicenseValues)
                            if (!notices.Contains(value)) throw new MbmapException($"NOTICES.txt lacks the licence {key} of asset_notices[{ai}]");
                    }
                }

                // 4. Payloads.
                pkg.Collision = CollisionMesh.Read(pkg.Member(CollisionPath, "collision"));
                if (Json.Long(colInfo, "triangle_count", "manifest.collision") != pkg.Collision.TriangleCount
                    || Json.Long(colInfo, "vertex_count", "manifest.collision") != pkg.Collision.VertexCount)
                    throw new MbmapException("manifest.collision counts differ from the .mbcol header");
                if (hasHf)
                {
                    var h = HeightField.Read(pkg.Member(HeightfieldPath, "heightfield"));
                    if (Json.Long(hfInfo, "nx", "manifest.heightfield") != h.Nx || Json.Long(hfInfo, "ny", "manifest.heightfield") != h.Ny
                        || Math.Abs(Json.Num(hfInfo, "x0", "manifest.heightfield") - h.X0) > 1e-9 || Math.Abs(Json.Num(hfInfo, "y0", "manifest.heightfield") - h.Y0) > 1e-9
                        || Math.Abs(Json.Num(hfInfo, "spacing_m", "manifest.heightfield") - h.Spacing) > 1e-9)
                        throw new MbmapException("manifest.heightfield nx/ny/x0/y0/spacing_m differ from the .mbhf file");
                    pkg.Heightfield = h;
                }

                var probes = Json.Array(m, "orientation_probes", "manifest");
                if (probes.Count > Limits.ProbeMax) throw new MbmapException($"manifest: orientation_probes must be an array of at most {Limits.ProbeMax}");
                var probeNodes = new HashSet<string>(StringComparer.Ordinal);
                int pi = 0;
                foreach (var p in probes)
                {
                    string tag = $"orientation probe {pi++}";
                    if (p.ValueKind != JsonValueKind.Object) throw new MbmapException($"{tag} must be an object");
                    var tri = Json.Array(p, "triangle_map", tag);
                    if (tri.Count != 3) throw new MbmapException($"{tag}: triangle_map needs 3 points");
                    var probe = new OrientationProbe
                    {
                        Node = Json.Str(p, "node", tag),
                        PointMap = Json.V3(p, "point_map", tag), PointGltf = Json.V3(p, "point_gltf", tag),
                        PointUnity = Json.V3(p, "point_unity_x_negated", tag),
                        NormalMap = Json.V3(p, "normal_map", tag), NormalUnity = Json.V3(p, "normal_unity_x_negated", tag),
                        TriangleMap = new Triangle(Json.AsV3(tri[0], $"{tag}.triangle_map"), Json.AsV3(tri[1], $"{tag}.triangle_map"), Json.AsV3(tri[2], $"{tag}.triangle_map")),
                    };
                    if (!probeNodes.Add(probe.Node)) throw new MbmapException($"{tag}: more than one probe for the node");
                    string why = ProbeCheck.Intrinsic(probe);
                    if (why != null) throw new MbmapException($"{tag}: {why}");
                    pkg.Probes.Add(probe);
                }

                // Passage probes (docs/PACKAGE_FORMAT.md "Passage probes"): required array, each capsule's
                // feature must name a manifest object. Whether a capsule is clear is reported by the caller
                // (a blocked probe is a warning in the reference validator, not an invalid package).
                var mbIds = new HashSet<string>(StringComparer.Ordinal);
                int oi = 0;
                foreach (var o in Json.Array(m, "objects", "manifest"))
                    mbIds.Add(Json.Str(o, "mb_id", $"manifest: objects[{oi++}]"));
                var passage = Json.Array(m, "passage_probes", "manifest");
                if (passage.Count > Limits.PassageProbeMax) throw new MbmapException($"manifest: passage_probes must be an array of at most {Limits.PassageProbeMax}");
                var passageIds = new HashSet<string>(StringComparer.Ordinal);
                for (int i = 0; i < passage.Count; i++)
                {
                    var p = passage[i];
                    string tag = $"manifest: passage_probes[{i}]";
                    if (p.ValueKind != JsonValueKind.Object) throw new MbmapException($"{tag} must be an object");
                    var pp = new PassageProbe
                    {
                        Id = Json.NonEmptyStr(p, "id", tag), Kind = Json.Str(p, "kind", tag),
                        Feature = Json.NonEmptyStr(p, "feature", tag), RadiusM = Json.Num(p, "radius_m", tag),
                    };
                    if (!passageIds.Add(pp.Id)) throw new MbmapException($"{tag}.id repeats an earlier probe id");
                    if (Array.IndexOf(PassageProbe.Kinds, pp.Kind) < 0) throw new MbmapException($"{tag}.kind must be one of bridge, tunnel, elevated");
                    if (!mbIds.Contains(pp.Feature)) throw new MbmapException($"{tag}.feature does not match any manifest object mb_id");
                    if (!(pp.RadiusM > 0 && pp.RadiusM <= Limits.PassageRadiusMaxM)) throw new MbmapException($"{tag}.radius_m must be in (0, {Limits.PassageRadiusMaxM}]");
                    var path = Json.Array(p, "path_map", tag);
                    if (path.Count < Limits.PassagePathMin || path.Count > Limits.PassagePathMax)
                        throw new MbmapException($"{tag}.path_map must have {Limits.PassagePathMin}..{Limits.PassagePathMax} points");
                    foreach (var q in path)
                    {
                        var v = Json.AsV3(q, $"{tag}.path_map");
                        if (Math.Abs(v.X) > Limits.MaxAbsCoordM || Math.Abs(v.Y) > Limits.MaxAbsCoordM || Math.Abs(v.Z) > Limits.MaxAbsCoordM)
                            throw new MbmapException($"{tag}.path_map coordinates must be within {Limits.MaxAbsCoordM} m");
                        pp.PathMap.Add(v);
                    }
                    pkg.PassageProbes.Add(pp);
                }

                // 5. Only now does package_id bind the verified payload.
                pkg.PackageId = "sha256:" + Hex(Sha256(manifestBytes));
                return pkg;
            }
            catch
            {
                pkg.Dispose();
                throw;
            }
        }

        public byte[] Member(string path, string role)
        {
            var fe = Files.Find(f => f.Path == path);
            if (fe == null || fe.Role != role || !Members.TryGetValue(path, out var data)) throw new MbmapException($"manifest names a {role} member that is not in files[] with that role");
            return data;
        }

        static string Label(string path) => KnownRoles.ContainsKey(path) ? path : "(unlisted path)";

        internal static bool IsUtc(string s) => Utc.IsMatch(s) && DateTime.TryParseExact(s.Substring(0, 19), "yyyy-MM-dd'T'HH:mm:ss",
            System.Globalization.CultureInfo.InvariantCulture, System.Globalization.DateTimeStyles.None, out _);

        static bool SafeName(string n)
        {
            if (string.IsNullOrEmpty(n) || n.Length > Limits.MaxNameLength || n.StartsWith("/") || n.Contains('\\') || n.Contains(':')) return false;
            foreach (char ch in n) if (ch < 0x20 || ch == 0x7F) return false;
            foreach (var part in n.Split('/')) if (part.Length == 0 || part == "." || part == "..") return false;
            return true;
        }

        static byte[] ReadAll(ZipArchiveEntry e, string label)
        {
            if (e.Length > int.MaxValue) throw new MbmapException($"{label}: member too large for this reader");
            var buf = new byte[e.Length];
            using (var s = e.Open())
            {
                int got = 0, n;
                while (got < buf.Length && (n = s.Read(buf, got, buf.Length - got)) > 0) got += n;
                if (got != buf.Length || s.ReadByte() != -1) throw new MbmapException($"{label}: uncompressed size differs from its zip header");
            }
            return buf;
        }

        static byte[] Sha256(byte[] d) { using (var h = SHA256.Create()) return h.ComputeHash(d); }

        static string Hex(byte[] b)
        {
            var sb = new StringBuilder(b.Length * 2);
            foreach (var x in b) sb.Append(x.ToString("x2"));
            return sb.ToString();
        }
    }

    /// <summary>Little-endian reads (independent of host endianness).</summary>
    static class Bin
    {
        public static uint U32(byte[] d, int o) => BinaryPrimitives.ReadUInt32LittleEndian(new ReadOnlySpan<byte>(d, o, 4));
        public static float F32(byte[] d, int o) => BitConverter.Int32BitsToSingle(BinaryPrimitives.ReadInt32LittleEndian(new ReadOnlySpan<byte>(d, o, 4)));
        public static double F64(byte[] d, int o) => BitConverter.Int64BitsToDouble(BinaryPrimitives.ReadInt64LittleEndian(new ReadOnlySpan<byte>(d, o, 8)));
    }

    /// <summary>Strict JSON as the reference implementation reads it: UTF-8, no comments or trailing commas,
    /// no NaN/Infinity (System.Text.Json rejects them), no duplicate keys.</summary>
    static class StrictJson
    {
        public static JsonDocument Parse(ReadOnlyMemory<byte> utf8, string what)
        {
            JsonDocument doc;
            try { doc = JsonDocument.Parse(utf8, new JsonDocumentOptions { AllowTrailingCommas = false, CommentHandling = JsonCommentHandling.Disallow, MaxDepth = 64 }); }
            catch (JsonException) { throw new MbmapException($"{what} is not valid strict UTF-8 JSON"); }
            try { NoDuplicates(doc.RootElement, what); }
            catch { doc.Dispose(); throw; }
            return doc;
        }

        static void NoDuplicates(JsonElement root, string what)
        {
            var stack = new Stack<JsonElement>();
            stack.Push(root);
            while (stack.Count > 0)
            {
                var e = stack.Pop();
                if (e.ValueKind == JsonValueKind.Object)
                {
                    var keys = new HashSet<string>(StringComparer.Ordinal);
                    foreach (var p in e.EnumerateObject())
                    {
                        if (!keys.Add(p.Name)) throw new MbmapException($"{what}: duplicate key in an object");
                        stack.Push(p.Value);
                    }
                }
                else if (e.ValueKind == JsonValueKind.Array) foreach (var x in e.EnumerateArray()) stack.Push(x);
            }
        }
    }

    /// <summary>Typed JSON accessors that throw MbmapException (naming the field, never echoing values).</summary>
    static class Json
    {
        static JsonElement Get(JsonElement e, string key, string tag)
        {
            if (e.ValueKind != JsonValueKind.Object || !e.TryGetProperty(key, out var v)) throw new MbmapException($"{tag}: missing '{key}'");
            return v;
        }
        public static string AsString(JsonElement v, string tag) => v.ValueKind == JsonValueKind.String ? v.GetString() : throw new MbmapException($"{tag} must be a string");
        public static long AsLong(JsonElement v, string tag) => v.ValueKind == JsonValueKind.Number && v.TryGetInt64(out var x) ? x : throw new MbmapException($"{tag} must be an integer");
        public static double AsNum(JsonElement v, string tag) => v.ValueKind == JsonValueKind.Number && v.TryGetDouble(out var x) && double.IsFinite(x) ? x : throw new MbmapException($"{tag} must be a finite number");
        public static Vec3 AsV3(JsonElement v, string tag)
        {
            if (v.ValueKind != JsonValueKind.Array || v.GetArrayLength() != 3) throw new MbmapException($"{tag}: expected a 3-vector");
            return new Vec3(AsNum(v[0], tag), AsNum(v[1], tag), AsNum(v[2], tag));
        }
        public static bool AsBool(JsonElement v, string tag) =>
            v.ValueKind == JsonValueKind.True ? true : v.ValueKind == JsonValueKind.False ? false : throw new MbmapException($"{tag} must be a boolean");
        /// <summary>An integer in [0, limit), validated as a long before narrowing to int.</summary>
        public static int AsIndex(JsonElement v, int limit, string tag)
        {
            long x = AsLong(v, tag);
            if (x < 0 || x >= limit) throw new MbmapException($"{tag} is out of range");
            return (int)x;
        }
        public static int Index(JsonElement e, string key, int limit, string tag) => AsIndex(Get(e, key, tag), limit, $"{tag}.{key}");
        public static string Str(JsonElement e, string key, string tag) => AsString(Get(e, key, tag), $"{tag}.{key}");
        public static string NonEmptyStr(JsonElement e, string key, string tag)
        {
            string s = Str(e, key, tag);
            return s.Length > 0 ? s : throw new MbmapException($"{tag}.{key} must be a non-empty string");
        }
        /// <summary>Optional key: absent or null gives null, otherwise it must be a string.</summary>
        public static string OptStrOrNull(JsonElement e, string key, string tag) =>
            !e.TryGetProperty(key, out var v) || v.ValueKind == JsonValueKind.Null ? null : AsString(v, $"{tag}.{key}");
        public static long Long(JsonElement e, string key, string tag) => AsLong(Get(e, key, tag), $"{tag}.{key}");
        public static int Int(JsonElement e, string key, string tag)
        {
            long v = Long(e, key, tag);
            if (v < int.MinValue || v > int.MaxValue) throw new MbmapException($"{tag}.{key} is out of range");
            return (int)v;
        }
        public static double Num(JsonElement e, string key, string tag) => AsNum(Get(e, key, tag), $"{tag}.{key}");
        public static Vec3 V3(JsonElement e, string key, string tag) => AsV3(Get(e, key, tag), $"{tag}.{key}");
        public static JsonElement Obj(JsonElement e, string key, string tag)
        {
            var v = Get(e, key, tag);
            return v.ValueKind == JsonValueKind.Object ? v : throw new MbmapException($"{tag}.{key} must be an object");
        }
        public static List<JsonElement> Array(JsonElement e, string key, string tag)
        {
            var v = Get(e, key, tag);
            if (v.ValueKind != JsonValueKind.Array) throw new MbmapException($"{tag}.{key} must be an array");
            return new List<JsonElement>(v.EnumerateArray());
        }
        public static List<JsonElement> OptArray(JsonElement e, string key) =>
            e.ValueKind == JsonValueKind.Object && e.TryGetProperty(key, out var v)
                ? (v.ValueKind == JsonValueKind.Array ? new List<JsonElement>(v.EnumerateArray()) : throw new MbmapException($"'{key}' must be an array"))
                : new List<JsonElement>();
        /// <summary>Optional array whose elements must all be objects (count checked before materialising).</summary>
        public static List<JsonElement> OptObjects(JsonElement e, string key, string tag, int maxCount = int.MaxValue)
        {
            if (e.ValueKind != JsonValueKind.Object || !e.TryGetProperty(key, out var v)) return new List<JsonElement>();
            if (v.ValueKind != JsonValueKind.Array) throw new MbmapException($"{tag}: '{key}' must be an array");
            if (v.GetArrayLength() > maxCount) throw new MbmapException($"{tag}: too many '{key}'");
            var r = new List<JsonElement>(v.GetArrayLength());
            foreach (var x in v.EnumerateArray())
            {
                if (x.ValueKind != JsonValueKind.Object) throw new MbmapException($"{tag}: {key}[{r.Count}] must be an object");
                r.Add(x);
            }
            return r;
        }
        public static double[] NumArray(JsonElement e, string key, int n, string tag)
        {
            var v = Get(e, key, tag);
            if (v.ValueKind != JsonValueKind.Array || v.GetArrayLength() != n) throw new MbmapException($"{tag}.{key} must be {n} finite numbers");
            var r = new double[n];
            int i = 0;
            foreach (var x in v.EnumerateArray()) r[i++] = AsNum(x, $"{tag}.{key}");
            return r;
        }
    }
}
