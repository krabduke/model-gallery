"""The CFD's surface pressure and flow slices, as a web model.

    blender -b -P tools/cp_glb.py -- <run> <U> <out.glb> [faces]

Reads what the run's `surfaces` function object wrote at the end --
`walls` (pressure on the vehicle), and every other surface there (the
symmetry plane, cutting planes) with velocity -- and writes one GLB:

    vehicle    the walls, mirrored to the whole vehicle, coloured by the
               pressure coefficient Cp = p / (U^2 / 2) (p kinematic)
    <slice>    each slice coloured by |U| / U

Colours go in the vertex colours, so the page needs no field data, and the
vehicle is decimated to about `faces` faces (default 400,000) to keep the
file small. Both the VTK formats OpenFOAM writes are read: legacy .vtk and
XML .vtp, ASCII.
"""
import math
import os
import re
import sys

import bpy
import bmesh

args = sys.argv[sys.argv.index("--") + 1:]
run, U, out = args[0], float(args[1]), args[2]
target = int(args[3]) if len(args) > 3 else 400000
q = 0.5 * U * U


def read_vtk(path):
    """(points, faces, {field: values}, where) -- values per point or per
    face, `where` says which."""
    txt = open(path).read()
    if path.endswith(".vtp") or txt.lstrip().startswith("<"):
        def arr(tag_re, block):
            m = re.search(tag_re + r"[^>]*>(.*?)</DataArray>", block, re.S)
            return m.group(1).split() if m else []
        pts = [float(v) for v in arr(r'<Points>\s*<DataArray', txt)]
        polys = re.search(r"<Polys>(.*?)</Polys>", txt, re.S).group(1)
        conn = [int(v) for v in arr(r'<DataArray[^>]*Name=["\x27]connectivity["\x27]', polys)]
        offs = [int(v) for v in arr(r'<DataArray[^>]*Name=["\x27]offsets["\x27]', polys)]
        faces, s0 = [], 0
        for o in offs:
            faces.append(conn[s0:o])
            s0 = o
        fields, where = {}, None
        for sect, w in (("PointData", "point"), ("CellData", "cell")):
            m = re.search(rf"<{sect}[^>]*>(.*?)</{sect}>", txt, re.S)
            if not m:
                continue
            for dm in re.finditer(r'<DataArray[^>]*Name=["\x27]([^"\x27]+)["\x27][^>]*>(.*?)</DataArray>',
                                  m.group(1), re.S):
                fields[dm.group(1)] = [float(v) for v in dm.group(2).split()]
                where = w
        P = [tuple(pts[i:i + 3]) for i in range(0, len(pts), 3)]
        return P, faces, fields, where
    tok = txt.split()
    i = tok.index("POINTS")
    n = int(tok[i + 1])
    P = [tuple(float(c) for c in tok[i + 3 + 3 * k:i + 6 + 3 * k]) for k in range(n)]
    i = tok.index("POLYGONS")
    nf = int(tok[i + 1])
    j, faces = i + 3, []
    for _ in range(nf):
        m = int(tok[j])
        faces.append([int(c) for c in tok[j + 1:j + 1 + m]])
        j += 1 + m
    fields, where = {}, None
    for w, key in (("point", "POINT_DATA"), ("cell", "CELL_DATA")):
        if key not in tok:
            continue
        k = tok.index(key)
        cnt = int(tok[k + 1])
        rest = tok[k + 2:]
        # FIELD attributes n / name ncomp ntuples type / values
        if rest and rest[0] == "FIELD":
            nfld = int(rest[2])
            r = 3
            for _ in range(nfld):
                name, nc, nt = rest[r], int(rest[r + 1]), int(rest[r + 2])
                vals = [float(v) for v in rest[r + 4:r + 4 + nc * nt]]
                fields[name] = vals
                r += 4 + nc * nt
            where = w
        elif rest and rest[0] in ("SCALARS", "VECTORS"):
            name = rest[1]
            nc = 3 if rest[0] == "VECTORS" else 1
            off = 3 if rest[0] == "VECTORS" else 5
            fields[name] = [float(v) for v in rest[off:off + nc * cnt]]
            where = w
    return P, faces, fields, where


def ramp(t):
    """A diverging ramp: blue (suction) -- pale -- orange (pressure)."""
    stops = [(0.0, (0.13, 0.28, 0.62)), (0.35, (0.40, 0.62, 0.86)),
             (0.5, (0.90, 0.91, 0.88)), (0.7, (0.95, 0.62, 0.33)), (1.0, (0.72, 0.18, 0.10))]
    t = min(1.0, max(0.0, t))
    for (a, ca), (b, cb) in zip(stops, stops[1:]):
        if t <= b:
            f = (t - a) / (b - a)
            return tuple(ca[k] + (cb[k] - ca[k]) * f for k in range(3))
    return stops[-1][1]


def speed_ramp(t):
    stops = [(0.0, (0.06, 0.08, 0.16)), (0.5, (0.20, 0.42, 0.68)), (0.85, (0.80, 0.86, 0.88)),
             (1.0, (0.98, 0.84, 0.50)), (1.3, (0.93, 0.47, 0.22))]
    t = min(1.3, max(0.0, t))
    for (a, ca), (b, cb) in zip(stops, stops[1:]):
        if t <= b:
            f = (t - a) / (b - a)
            return tuple(ca[k] + (cb[k] - ca[k]) * f for k in range(3))
    return stops[-1][1]


def build(name, P, faces, colours_per_face=None, colours_per_point=None, mirror=False):
    me = bpy.data.meshes.new(name)
    me.from_pydata(P, [], faces)
    me.update()
    attr = me.color_attributes.new("Col", "FLOAT_COLOR", "CORNER")
    for poly in me.polygons:
        for li in poly.loop_indices:
            vi = me.loops[li].vertex_index
            c = colours_per_point[vi] if colours_per_point else colours_per_face[poly.index]
            attr.data[li].color = (*c, 1.0)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    if mirror:
        mod = ob.modifiers.new("mirror", "MIRROR")
        mod.use_axis = (False, True, False)
    return ob


for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)

root = os.path.join(run, "postProcessing", "surfaces")
t = sorted(os.listdir(root), key=float)[-1]
d = os.path.join(root, t)
files = sorted(os.listdir(d))
made = []
for f in files:
    if not f.endswith((".vtk", ".vtp")):
        continue
    name = f.rsplit(".", 1)[0]
    P, faces, fields, where = read_vtk(os.path.join(d, f))
    if name == "walls":
        p = fields.get("p")
        cp = [v / q for v in p]
        col = [ramp((c + 1.5) / 2.5) for c in cp]      # Cp -1.5 .. +1.0
        ob = build("vehicle", P, faces, col if where == "cell" else None,
                   col if where == "point" else None, mirror=True)
        made.append((ob, True))
        print(f"CP walls: {len(faces):,} faces, Cp {min(cp):.2f} to {max(cp):.2f}")
    else:
        Uv = fields.get("U")
        if not Uv:
            continue
        mag = [math.sqrt(Uv[3 * i] ** 2 + Uv[3 * i + 1] ** 2 + Uv[3 * i + 2] ** 2) / U
               for i in range(len(Uv) // 3)]
        col = [speed_ramp(m) for m in mag]
        ob = build(name, P, faces, col if where == "cell" else None,
                   col if where == "point" else None)
        made.append((ob, False))
        print(f"SLICE {name}: {len(faces):,} faces, |U|/U {min(mag):.2f} to {max(mag):.2f}")

# decimate the big ones, apply the mirror
for ob, is_vehicle in made:
    bpy.context.view_layer.objects.active = ob
    for m in list(ob.modifiers):
        bpy.ops.object.modifier_apply(modifier=m.name)
    n = len(ob.data.polygons)
    goal = target if is_vehicle else target // 4
    if n > goal:
        dec = ob.modifiers.new("dec", "DECIMATE")
        dec.ratio = goal / n
        bpy.ops.object.modifier_apply(modifier="dec")
    print(f"GLB {ob.name}: {len(ob.data.polygons):,} faces")

bpy.ops.export_scene.gltf(filepath=out, export_format="GLB", export_draco_mesh_compression_enable=True,
                          export_draco_mesh_compression_level=7, export_yup=True,
                          export_vertex_color="ACTIVE", export_materials="NONE")
print(f"GLB -> {out}")
