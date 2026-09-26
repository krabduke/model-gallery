"""The outside of a model, as the surfaces a CFD mesher wraps.

    blender -b model.blend -P tools/export_stl.py -- cases/<case>/geometry.json <out dir>

geometry.json:
    {"regions": {"body": {"groups": ["01 Bodywork", ...], "parts": [...],
                          "skip": ["hose_clips", ...]},
                 "wheel_front": {"parts": ["tyre_f", "rim_f", ...]}},
     "order": ["wheel_front", "wheel_rear", "body"]}

`groups` are collections, `parts` and `skip` name prefixes. A part goes
to the first region in `order` that claims it, so the wheels can be taken
out of the body before the body takes everything else in its groups.
Each region is written as a binary STL in metres, which is what the
models are built in, and its bounding box is printed so the case can be
sized round it.
"""
import json
import os
import struct
import sys

import bpy

args = sys.argv[sys.argv.index("--") + 1:]
cfg = json.load(open(args[0]))
out = args[1]
os.makedirs(out, exist_ok=True)

regions = cfg["regions"]
order = cfg.get("order", list(regions))
dg = bpy.context.evaluated_depsgraph_get()


def claims(spec, o):
    name = o.name
    if any(name.startswith(p) for p in spec.get("skip", [])):
        return False
    if any(name.startswith(p) for p in spec.get("parts", [])):
        return True
    g = o.users_collection[0].name if o.users_collection else ""
    return g in spec.get("groups", [])


tris = {r: [] for r in order}
for o in bpy.data.objects:
    if o.type != "MESH" or o.name.startswith(("__", "cut:")) or o.hide_render:
        continue
    for r in order:
        if claims(regions[r], o):
            ev = o.evaluated_get(dg)
            me = ev.to_mesh()
            me.calc_loop_triangles()
            mw = o.matrix_world
            vs = [mw @ v.co for v in me.vertices]
            for t in me.loop_triangles:
                tris[r].append(tuple(tuple(vs[i]) for i in t.vertices))
            ev.to_mesh_clear()
            break

for r, ts in tris.items():
    path = os.path.join(out, f"{r}.stl")
    with open(path, "wb") as fh:
        fh.write(r.encode().ljust(80, b" "))
        fh.write(struct.pack("<I", len(ts)))
        for a, b, c in ts:
            fh.write(struct.pack("<3f", 0.0, 0.0, 0.0))
            for p in (a, b, c):
                fh.write(struct.pack("<3f", *p))
            fh.write(b"\0\0")
    if ts:
        lo = [min(p[k] for t in ts for p in t) for k in range(3)]
        hi = [max(p[k] for t in ts for p in t) for k in range(3)]
        print(f"STL {r}: {len(ts):,} triangles, box {[round(c, 3) for c in lo]} "
              f"to {[round(c, 3) for c in hi]}")
    else:
        print(f"STL {r}: empty")
