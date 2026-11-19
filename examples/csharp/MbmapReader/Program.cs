using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;
using MapBuilder.Reference;

// Usage: dotnet run -c Release -- <package.mbmap>
// Verifies the package (container rules, files[] one-to-one, sizes, SHA-256), computes package_id,
// parses .mbcol/.mbhf/GLB, checks the visual/collision name binding, runs the orientation probes against
// the GLB through a simulated X-negating importer (plus two negative controls), and cross-checks the
// heightfield against vertical ray queries on the authoritative terrain triangles.
// Exit codes: 0 OK, 1 invalid package or failed self-test, 2 usage.
static class Program
{
    static int Main(string[] args)
    {
        if (args.Length != 1) { Console.Error.WriteLine("usage: MbmapReader <package.mbmap>"); return 2; }
        try
        {
            using (var p = MbmapPackage.Load(args[0]))
                return Report(p);
        }
        catch (Exception e) when (e is MbmapException || e is InvalidDataException || e is IOException || e is UnauthorizedAccessException)
        {
            Console.WriteLine($"INVALID: {e.Message}");
            return 1;
        }
        catch (Exception e) when (!(e is OutOfMemoryException || e is AccessViolationException))
        {
            // Backstop: the reader validates every field it touches, so this indicates a reader bug; the package
            // is still refused rather than crashing the consumer. The message is not echoed (it may quote input).
            Console.WriteLine($"INVALID: unexpected {e.GetType().Name} while reading the package");
            return 1;
        }
    }

    static int Report(MbmapPackage p)
    {
        var m = p.Info;
        var c = p.Collision;
        var failures = new List<string>();
        Console.WriteLine($"package    {m.Name}  (schema {m.SchemaVersion}, created {m.CreatedUtc})");
        Console.WriteLine($"package_id {p.PackageId}");
        Console.WriteLine($"members    {p.Files.Count} verified (size + SHA-256): {string.Join(", ", p.Files.ConvertAll(f => f.Path))}");
        Console.WriteLine($"origin     lat {m.OriginLatDeg}, lon {m.OriginLonDeg}; H = z + {m.ZOffsetM} m ({m.VerticalDatum})");
        Console.WriteLine($"area       {m.WidthM} x {m.HeightM} m");

        var perClass = new int[CollisionMesh.ClassNames.Length];
        foreach (var b in c.TriangleClass) perClass[b]++;
        var classes = new List<string>();
        for (int k = 0; k < perClass.Length; k++) if (perClass[k] > 0) classes.Add($"{CollisionMesh.ClassNames[k]}({k}) {perClass[k]}");
        Console.WriteLine($"collision  v{c.Version}: {c.VertexCount} vertices, {c.TriangleCount} triangles, {c.Objects.Length} objects; " +
                          $"bounds ({c.BoundsMin[0]}, {c.BoundsMin[1]}, {c.BoundsMin[2]})..({c.BoundsMax[0]}, {c.BoundsMax[1]}, {c.BoundsMax[2]})");
        Console.WriteLine($"triangles  by class: {string.Join(", ", classes)}");

        // Visual/collision binding: every glTF node with triangles <-> one collision object of the same name.
        var nodes = Glb.Read(p.Member(MbmapPackage.VisualPath, "visual"));
        var visual = new Dictionary<string, VisualNode>(StringComparer.Ordinal);
        foreach (var n in nodes)
            if (n.TrianglesGltf.Count > 0 && !visual.TryAdd(n.Name, n)) failures.Add("two glTF nodes with triangles share a name");
        var byName = new Dictionary<string, CollisionObject>(StringComparer.Ordinal);
        foreach (var o in c.Objects) byName[o.Name] = o;
        int unbound = 0;
        foreach (var o in c.Objects) if (!visual.ContainsKey(o.Name)) unbound++;
        foreach (var n in visual.Keys) if (!byName.ContainsKey(n)) unbound++;
        if (unbound > 0) failures.Add($"{unbound} visual node(s)/collision object(s) without a same-named counterpart");
        Console.WriteLine($"visual     {nodes.Count} glTF nodes, {visual.Count} with triangles; name binding to collision: {(unbound == 0 ? "1:1" : "BROKEN")}");

        // Orientation probes: the self-test of the ENU -> glTF -> Unity mapping and the winding flip.
        if (p.Probes.Count == 0) failures.Add("orientation probes unavailable: importer orientation is UNVERIFIED (refuse the map or verify the importer separately)");
        for (int i = 0; i < p.Probes.Count; i++)
        {
            var probe = p.Probes[i];
            string tag = $"probe {i}";
            if (!byName.TryGetValue(probe.Node, out var obj) || !visual.TryGetValue(probe.Node, out var vn)) { failures.Add($"{tag}: node missing from collision or glTF"); continue; }
            string why = ProbeCheck.AgainstCollision(probe, c, obj);
            if (why != null) { failures.Add($"{tag} vs collision: {why}"); continue; }
            string ok = ProbeCheck.InUnity(probe, Import(vn, negateX: true, reverseWinding: true));
            string noFlip = ProbeCheck.InUnity(probe, Import(vn, negateX: true, reverseWinding: false));
            string noNegate = ProbeCheck.InUnity(probe, Import(vn, negateX: false, reverseWinding: true));
            // Tampered probes must be refused by both checks: a scaled (non-unit) normal, and a point_map moved
            // off triangle_map (with its derived points kept consistent so only the vertex check can catch it).
            var scaled = probe.Clone();
            scaled.NormalMap = Scale(probe.NormalMap, 2);
            scaled.NormalUnity = Scale(probe.NormalUnity, 2);
            var offVertex = probe.Clone();
            var tm = probe.TriangleMap;
            // Above every vertex of the triangle, so it cannot coincide with another vertex.
            offVertex.PointMap = new Vec3(probe.PointMap.X, probe.PointMap.Y, Math.Max(tm.A.Z, Math.Max(tm.B.Z, tm.C.Z)) + 1);
            offVertex.PointGltf = Axes.MapToGltf(offVertex.PointMap);
            offVertex.PointUnity = Axes.MapToUnity(offVertex.PointMap);
            var imported = Import(vn, negateX: true, reverseWinding: true);
            bool scaledRejected = ProbeCheck.AgainstCollision(scaled, c, obj) != null && ProbeCheck.InUnity(scaled, imported) != null;
            bool offRejected = ProbeCheck.AgainstCollision(offVertex, c, obj) != null && ProbeCheck.InUnity(offVertex, imported) != null;
            if (ok != null) failures.Add($"{tag} (X negated + winding reversed): {ok}");
            if (noFlip == null) failures.Add($"{tag}: control without the winding flip was not detected");
            if (noNegate == null) failures.Add($"{tag}: control without the X negation was not detected");
            if (!scaledRejected) failures.Add($"{tag}: control with a non-unit normal was not detected");
            if (!offRejected) failures.Add($"{tag}: control with point_map off triangle_map was not detected");
            Console.WriteLine($"{tag}    {obj.Class} node, unity point {probe.PointUnity}: " +
                              $"{(ok == null ? "PASS" : "FAIL")}; controls rejected: no winding flip={YesNo(noFlip != null)}, no X negation={YesNo(noNegate != null)}, " +
                              $"non-unit normal={YesNo(scaledRejected)}, point off triangle={YesNo(offRejected)}");
        }

        if (p.Heightfield != null)
        {
            var h = p.Heightfield;
            int checks = 0;
            double maxErr = 0;
            int stepI = Math.Max(1, h.Nx / 7), stepJ = Math.Max(1, h.Ny / 7);
            for (int j = 0; j < h.Ny; j += stepJ)
                for (int i = 0; i < h.Nx; i += stepI)
                {
                    double z = c.HighestZ(h.X0 + i * h.Spacing, h.Y0 + j * h.Spacing, (int)CollisionClass.Terrain);
                    float hz = h.At(i, j);
                    checks++;
                    if (double.IsNaN(z) != float.IsNaN(hz)) { failures.Add($"heightfield ({i}, {j}): NaN disagrees with the terrain triangles"); continue; }
                    if (!double.IsNaN(z)) maxErr = Math.Max(maxErr, Math.Abs(z - hz));
                }
            if (maxErr > 1e-3) failures.Add($"heightfield differs from the terrain triangles by {maxErr} m");
            Console.WriteLine($"heightfield {h.Nx}x{h.Ny} @ {h.Spacing} m from ({h.X0}, {h.Y0}): {checks} samples vs terrain triangles, max |dz| = {maxErr:0.######} m");
        }
        else Console.WriteLine("heightfield none");
        Console.WriteLine($"surface    highest z at the map origin: {c.HighestZ(0, 0):0.###} m");

        foreach (var s in m.Sources)
            Console.WriteLine($"source     {s.Kind}: {s.Product ?? "?"}; attribution: {s.Attribution}");
        Console.WriteLine("notices    ship/show NOTICES.txt with the map");

        foreach (var f in failures) Console.WriteLine($"FAIL: {f}");
        Console.WriteLine(failures.Count == 0 ? "OK" : $"FAILED ({failures.Count})");
        return failures.Count == 0 ? 0 : 1;
    }

    // Simulates what a glTF importer does on the way into Unity; a real consumer reads the triangles back
    // from the meshes its importer (e.g. glTFast) created, in world space and imported index order.
    static Vec3 Scale(Vec3 v, double s) => new Vec3(v.X * s, v.Y * s, v.Z * s);
    static string YesNo(bool b) => b ? "yes" : "NO";

    static List<Triangle> Import(VisualNode n, bool negateX, bool reverseWinding) =>
        n.TrianglesGltf.ConvertAll(t => Axes.GltfTriangleToUnity(t, negateX, reverseWinding));
}
