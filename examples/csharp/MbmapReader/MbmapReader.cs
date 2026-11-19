// Reference reader for .mbmap packages (map-builder.package 1.x). The contract is docs/PACKAGE_FORMAT.md;
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
        public const int MaxNodes = 1_000_000, MaxNodeDepth = 64;
        // orientation probes (package.py)
        public const double ProbeMatchM = 0.05, ProbeMinDot = 0.99;
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

    public enum CollisionClass : byte { User = 0, Terrain = 1, Building = 2, Road = 3, Vegetation = 4, Water = 5, Prop = 6 }

    public sealed class CollisionObject
    {
        public int Index;
        public string Name, MbId, Class;
        public int TriStart, TriCount;
        public double[] Aabb; // min xyz, max xyz (map frame)
    }

    /// <summary>collision/map.mbcol v1: authoritative static collision in the map frame.</summary>
    public sealed class CollisionMesh
    {
        public const string Magic = "MBCOL\0\0\0";
        public const int HeaderSize = 64;
        public const uint FlagCcwOutward = 1;
        public static readonly string[] ClassNames = { "user", "terrain", "building", "road", "vegetation", "water", "prop" };

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
            if (c.Version != 1) throw new MbmapException($"collision: unsupported version {c.Version}");
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

        public static List<VisualNode> Read(byte[] data)
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
                return ReadNodes(doc.RootElement, data, binOff, binLen, hasBin);
        }

        static List<VisualNode> ReadNodes(JsonElement gl, byte[] data, int binOff, int binLen, bool hasBin)
        {
            if (gl.ValueKind != JsonValueKind.Object || !gl.TryGetProperty("asset", out var asset) || asset.ValueKind != JsonValueKind.Object
                || !asset.TryGetProperty("version", out var ver) || ver.ValueKind != JsonValueKind.String || ver.GetString() != "2.0")
                throw new MbmapException("glb: asset.version must be 2.0");
            if (gl.TryGetProperty("extensionsRequired", out var req) && !(req.ValueKind == JsonValueKind.Array && req.GetArrayLength() == 0))
                throw new MbmapException("glb: required extensions are not allowed");
            var buffers = Json.OptArray(gl, "buffers");
            if (buffers.Count > 1) throw new MbmapException("glb: at most one (GLB-stored) buffer is allowed");
            long blen = 0;
            if (buffers.Count == 1)
            {
                if (!hasBin) throw new MbmapException("glb: buffer declared without a BIN chunk");
                if (buffers[0].TryGetProperty("uri", out _)) throw new MbmapException("glb: external or data-URI buffers are not allowed");
                blen = Json.Long(buffers[0], "byteLength", "glb: buffer");
                if (blen < 0 || blen > binLen || binLen - blen > 3) throw new MbmapException("glb: buffer byteLength does not match the BIN chunk");
            }
            foreach (var im in Json.OptArray(gl, "images"))
                if (im.TryGetProperty("uri", out _)) throw new MbmapException("glb: external image URIs are not allowed");
            var views = Json.OptArray(gl, "bufferViews");
            var accessors = Json.OptArray(gl, "accessors");
            var meshes = Json.OptArray(gl, "meshes");
            var nodes = Json.OptArray(gl, "nodes");
            if (nodes.Count > Limits.MaxNodes) throw new MbmapException("glb: too many nodes");

            long triBudget = 0;
            var meshCache = new Dictionary<int, List<Triangle>>();

            List<Triangle> MeshTriangles(int mi)
            {
                if (meshCache.TryGetValue(mi, out var cached))
                {
                    triBudget += cached.Count;
                    if (triBudget > Limits.MaxVisualTriangles) throw new MbmapException("glb: too many visual triangles");
                    return cached;
                }
                var mesh = meshes[mi];
                var outList = new List<Triangle>();
                foreach (var p in Json.Array(mesh, "primitives", "glb: mesh"))
                {
                    long mode = p.TryGetProperty("mode", out var md) ? Json.AsLong(md, "glb: primitive mode") : 4;
                    if (mode == 5 || mode == 6) throw new MbmapException("glb: triangle strips/fans are not supported");
                    if (mode < 0 || mode > 6) throw new MbmapException("glb: invalid primitive mode");
                    if (p.TryGetProperty("targets", out var tg) && tg.ValueKind == JsonValueKind.Array && tg.GetArrayLength() > 0)
                        throw new MbmapException("glb: morph targets are not allowed");
                    if (mode != 4) continue;
                    var attrs = Json.Obj(p, "attributes", "glb: primitive");
                    double[] pos = ReadAccessor(Json.Int(attrs, "POSITION", "glb: attributes"), true);
                    int nverts = pos.Length / 3;
                    long[] idx;
                    if (p.TryGetProperty("indices", out var ie))
                    {
                        double[] raw = ReadAccessor((int)Json.AsLong(ie, "glb: indices"), false);
                        idx = new long[raw.Length];
                        for (int i = 0; i < raw.Length; i++) idx[i] = (long)raw[i];
                    }
                    else
                    {
                        idx = new long[nverts];
                        for (int i = 0; i < nverts; i++) idx[i] = i;
                    }
                    if (idx.Length % 3 != 0) throw new MbmapException("glb: triangle index count is not a multiple of 3");
                    triBudget += idx.Length / 3;
                    if (triBudget > Limits.MaxVisualTriangles) throw new MbmapException("glb: too many visual triangles");
                    Vec3 P(long i)
                    {
                        if (i < 0 || i >= nverts) throw new MbmapException("glb: index out of range");
                        return new Vec3(pos[3 * i], pos[3 * i + 1], pos[3 * i + 2]);
                    }
                    for (int k = 0; k < idx.Length; k += 3) outList.Add(new Triangle(P(idx[k]), P(idx[k + 1]), P(idx[k + 2])));
                }
                meshCache[mi] = outList;
                return outList;
            }

            // Returns components as doubles; position: float32 VEC3; otherwise unsigned integer scalars.
            double[] ReadAccessor(int ai, bool position)
            {
                if (ai < 0 || ai >= accessors.Count) throw new MbmapException("glb: bad accessor index");
                var a = accessors[ai];
                if (a.TryGetProperty("sparse", out _)) throw new MbmapException("glb: sparse accessors are not supported");
                long ct = Json.Long(a, "componentType", "glb: accessor");
                string type = Json.Str(a, "type", "glb: accessor");
                int size = ct == 5126 || ct == 5125 ? 4 : ct == 5123 || ct == 5122 ? 2 : ct == 5121 || ct == 5120 ? 1 : 0;
                int nc = type == "SCALAR" ? 1 : type == "VEC3" ? 3 : 0;
                if (position && (ct != 5126 || nc != 3 || (a.TryGetProperty("normalized", out var nz) && nz.ValueKind == JsonValueKind.True)))
                    throw new MbmapException("glb: POSITION must be float32 VEC3");
                if (!position && (nc != 1 || !(ct == 5121 || ct == 5123 || ct == 5125)))
                    throw new MbmapException("glb: indices must be unsigned integer scalars");
                long count = Json.Long(a, "count", "glb: accessor");
                int vi = Json.Int(a, "bufferView", "glb: accessor");
                if (count < 1 || count > blen || vi < 0 || vi >= views.Count) throw new MbmapException("glb: invalid accessor count or bufferView");
                var v = views[vi];
                if ((v.TryGetProperty("buffer", out var bi) ? Json.AsLong(bi, "glb: bufferView buffer") : 0) != 0 || blen == 0)
                    throw new MbmapException("glb: only buffer 0 (the BIN chunk) is supported");
                long voff = v.TryGetProperty("byteOffset", out var vo) ? Json.AsLong(vo, "glb: byteOffset") : 0;
                long vlen = Json.Long(v, "byteLength", "glb: bufferView");
                long aoff = a.TryGetProperty("byteOffset", out var ao) ? Json.AsLong(ao, "glb: byteOffset") : 0;
                if (voff < 0 || vlen < 0 || voff + vlen > blen || aoff < 0 || aoff > vlen || aoff % size != 0)
                    throw new MbmapException("glb: bufferView/accessor range is outside the buffer");
                int elem = size * nc;
                long stride = elem;
                if (v.TryGetProperty("byteStride", out var st))
                {
                    stride = Json.AsLong(st, "glb: byteStride");
                    if (stride < elem || stride > 252 || stride % 4 != 0) throw new MbmapException("glb: invalid byteStride");
                }
                if (aoff + stride * (count - 1) + elem > vlen) throw new MbmapException("glb: accessor overruns its bufferView");
                var vals = new double[count * nc];
                long start = binOff + voff + aoff;
                for (long k = 0; k < count; k++)
                    for (int c = 0; c < nc; c++)
                    {
                        int o = (int)(start + k * stride + c * size);
                        vals[k * nc + c] = ct == 5126 ? Bin.F32(data, o) : ct == 5125 ? Bin.U32(data, o)
                                         : ct == 5123 ? BinaryPrimitives.ReadUInt16LittleEndian(new ReadOnlySpan<byte>(data, o, 2)) : data[o];
                    }
                if (position) foreach (var x in vals) if (!double.IsFinite(x)) throw new MbmapException("glb: non-finite POSITION");
                return vals;
            }

            List<int> roots = new List<int>();
            var scenes = Json.OptArray(gl, "scenes");
            if (scenes.Count > 0)
            {
                int si = gl.TryGetProperty("scene", out var se) ? (int)Json.AsLong(se, "glb: scene") : 0;
                if (si < 0 || si >= scenes.Count) throw new MbmapException("glb: bad default scene index");
                foreach (var r in Json.OptArray(scenes[si], "nodes")) roots.Add((int)Json.AsLong(r, "glb: scene node"));
            }
            else for (int i = 0; i < nodes.Count; i++) roots.Add(i);

            var result = new List<VisualNode>();
            var visited = new HashSet<int>();
            var stack = new Stack<(int node, double[] parent, int depth)>();
            for (int i = roots.Count - 1; i >= 0; i--) stack.Push((roots[i], Mat.Identity(), 0));
            while (stack.Count > 0)
            {
                var (ni, parent, depth) = stack.Pop();
                if (depth > Limits.MaxNodeDepth || ni < 0 || ni >= nodes.Count || !visited.Add(ni))
                    throw new MbmapException("glb: invalid node hierarchy (bad index, cycle, shared child or too deep)");
                var node = nodes[ni];
                if (node.ValueKind != JsonValueKind.Object) throw new MbmapException("glb: node must be an object");
                if (node.TryGetProperty("skin", out _) || node.TryGetProperty("weights", out _)) throw new MbmapException("glb: skins and morph weights are not allowed");
                double[] m = Mat.Mul(parent, Mat.Local(node));
                var vn = new VisualNode { Name = node.TryGetProperty("name", out var nm) ? Json.AsString(nm, "glb: node name") : $"node{ni}" };
                if (node.TryGetProperty("mesh", out var me))
                {
                    int mi = (int)Json.AsLong(me, "glb: node mesh");
                    if (mi < 0 || mi >= meshes.Count) throw new MbmapException("glb: bad mesh index");
                    bool flip = Mat.Det3(m) < 0; // glTF: negative determinant means clockwise front faces
                    foreach (var t in MeshTriangles(mi))
                    {
                        Vec3 a = Mat.Apply(m, t.A), b = Mat.Apply(m, t.B), c = Mat.Apply(m, t.C);
                        vn.TrianglesGltf.Add(flip ? new Triangle(a, c, b) : new Triangle(a, b, c));
                    }
                }
                result.Add(vn);
                var children = Json.OptArray(node, "children");
                for (int i = children.Count - 1; i >= 0; i--) stack.Push(((int)Json.AsLong(children[i], "glb: child"), m, depth + 1));
            }
            return result;
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
    }

    /// <summary>Orientation-probe checks (docs/PACKAGE_FORMAT.md "Orientation probes").</summary>
    public static class ProbeCheck
    {
        /// <summary>Producer fields agree with this reader's axis mapping, and triangle_map is a collision
        /// triangle of the node in CCW cyclic order whose Unity-mapped front face (with the winding flip)
        /// matches normal_unity_x_negated. Returns null on success, else the reason.</summary>
        public static string AgainstCollision(OrientationProbe p, CollisionMesh col, CollisionObject obj)
        {
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
            return null;
        }

        /// <summary>The consumer check after import: unityTriangles are the node's imported triangles in Unity
        /// world space and imported index order (e.g. read back from the Mesh glTFast created).</summary>
        public static string InUnity(OrientationProbe p, IReadOnlyList<Triangle> unityTriangles)
        {
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

    public sealed class FileEntry
    {
        public string Path, Role, MediaType, Sha256;
        public long Bytes;
    }

    public sealed class MbmapPackage : IDisposable
    {
        public const string Schema = "map-builder.package";
        public const int SupportedMajor = 1;
        static readonly Regex SemVer = new Regex(@"^([0-9]+)\.([0-9]+)\.([0-9]+)\z");
        static readonly Dictionary<string, string> KnownRoles = new Dictionary<string, string>(StringComparer.Ordinal)
        {
            { "visual/map.glb", "visual" }, { "collision/map.mbcol", "collision" }, { "NOTICES.txt", "notices" },
            { "report.json", "report" }, { "collision/terrain.mbhf", "heightfield" },
        };

        /// <summary>"sha256:" + hex SHA-256 of the raw manifest.json bytes; set only after every member verified.</summary>
        public string PackageId;
        public JsonDocument ManifestDocument;
        public JsonElement Manifest => ManifestDocument.RootElement;
        public List<FileEntry> Files = new List<FileEntry>();
        public Dictionary<string, byte[]> Members = new Dictionary<string, byte[]>(StringComparer.Ordinal);
        public CollisionMesh Collision;
        public HeightField Heightfield;   // null if the package has none
        public List<OrientationProbe> Probes = new List<OrientationProbe>();

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

                // 3. files[] <-> members one-to-one, then sizes and hashes.
                int k = 0;
                var listed = new HashSet<string>(StringComparer.Ordinal);
                foreach (var f in Json.Array(m, "files", "manifest"))
                {
                    string tag = $"files[{k++}]";
                    var fe = new FileEntry
                    {
                        Path = Json.Str(f, "path", tag), Role = Json.Str(f, "role", tag), MediaType = Json.Str(f, "media_type", tag),
                        Sha256 = Json.Str(f, "sha256", tag), Bytes = Json.Long(f, "bytes", tag),
                    };
                    if (fe.Path == "manifest.json" || !SafeName(fe.Path) || !listed.Add(fe.Path)) throw new MbmapException($"{tag}: bad or duplicate path");
                    if (KnownRoles.TryGetValue(fe.Path, out var role) && role != fe.Role) throw new MbmapException($"{tag}: role does not match its path");
                    pkg.Files.Add(fe);
                }
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
                foreach (var req in new[] { "visual", "collision", "notices" })
                    if (!pkg.Files.Exists(f => f.Role == req)) throw new MbmapException($"required member with role '{req}' missing");

                // 4. Payloads.
                var colInfo = Json.Obj(m, "collision", "manifest");
                pkg.Collision = CollisionMesh.Read(pkg.Member(Json.Str(colInfo, "path", "manifest.collision"), "collision"));
                if (Json.Long(colInfo, "triangle_count", "manifest.collision") != pkg.Collision.TriangleCount
                    || Json.Long(colInfo, "vertex_count", "manifest.collision") != pkg.Collision.VertexCount)
                    throw new MbmapException("manifest.collision counts differ from the .mbcol header");
                if (m.TryGetProperty("heightfield", out var hfInfo) && hfInfo.ValueKind == JsonValueKind.Object)
                {
                    var h = HeightField.Read(pkg.Member(Json.Str(hfInfo, "path", "manifest.heightfield"), "heightfield"));
                    if (Json.Long(hfInfo, "nx", "manifest.heightfield") != h.Nx || Json.Long(hfInfo, "ny", "manifest.heightfield") != h.Ny
                        || Math.Abs(Json.Num(hfInfo, "x0", "manifest.heightfield") - h.X0) > 1e-9 || Math.Abs(Json.Num(hfInfo, "y0", "manifest.heightfield") - h.Y0) > 1e-9
                        || Math.Abs(Json.Num(hfInfo, "spacing_m", "manifest.heightfield") - h.Spacing) > 1e-9)
                        throw new MbmapException("manifest.heightfield nx/ny/x0/y0/spacing_m differ from the .mbhf file");
                    pkg.Heightfield = h;
                }
                else if (pkg.Files.Exists(f => f.Role == "heightfield")) throw new MbmapException("heightfield member present but manifest.heightfield is null");

                int pi = 0;
                foreach (var p in Json.Array(m, "orientation_probes", "manifest"))
                {
                    string tag = $"orientation probe {pi++}";
                    var tri = Json.Array(p, "triangle_map", tag);
                    if (tri.Count != 3) throw new MbmapException($"{tag}: triangle_map needs 3 points");
                    pkg.Probes.Add(new OrientationProbe
                    {
                        Node = Json.Str(p, "node", tag),
                        PointMap = Json.V3(p, "point_map", tag), PointGltf = Json.V3(p, "point_gltf", tag),
                        PointUnity = Json.V3(p, "point_unity_x_negated", tag),
                        NormalMap = Json.V3(p, "normal_map", tag), NormalUnity = Json.V3(p, "normal_unity_x_negated", tag),
                        TriangleMap = new Triangle(Json.AsV3(tri[0], tag), Json.AsV3(tri[1], tag), Json.AsV3(tri[2], tag)),
                    });
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
        public static string Str(JsonElement e, string key, string tag) => AsString(Get(e, key, tag), $"{tag}.{key}");
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
