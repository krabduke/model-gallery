"""Where a vehicle's lift and drag come from: the pressure on its surface,
integrated over regions picked out by where each face is.

    python3 tools/post_regions.py runs/<run> regions.json U scale

regions.json: [{"name": "front wing", "x": [lo, hi], "y": [lo, hi],
                "z": [lo, hi], "axle": [x, z, r]}, ...] -- boxes in metres
(any bound may be left out), or `axle` for a wheel: every face within r of
the axle's line. A face goes to the first region that takes it; what is
left is "the rest". Pressure only -- skin friction is a few per cent of a
bluff vehicle's drag and nothing of its lift -- so the sum is checked
against the solver's total, which includes friction, and both are printed.

The force on the vehicle is p (kinematic, times rho) over each face's
area vector, which OpenFOAM points out of the fluid, into the solid.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

run, regs, U, scale = sys.argv[1], json.load(open(sys.argv[2])), float(sys.argv[3]), float(sys.argv[4])
q = 0.5 * U * U


def read(path):
    # the same reader the web export uses, without Blender
    import re
    txt = open(path).read()
    if txt.lstrip().startswith("<"):
        def arr(tag_re, block):
            m = re.search(tag_re + r"[^>]*>(.*?)</DataArray>", block, re.S)
            return m.group(1).split() if m else []
        pts = [float(v) for v in arr(r'<Points>\s*<DataArray', txt)]
        polys = re.search(r"<Polys>(.*?)</Polys>", txt, re.S).group(1)
        conn = [int(v) for v in arr(r'<DataArray[^>]*Name=["\x27]connectivity["\x27]', polys)]
        offs = [int(v) for v in arr(r'<DataArray[^>]*Name=["\x27]offsets["\x27]', polys)]
        faces, s0 = [], 0
        for o in offs:
            faces.append(conn[s0:o]); s0 = o
        m = re.search(r"<CellData[^>]*>(.*?)</CellData>", txt, re.S)
        p = [float(v) for v in re.search(r'Name=["\x27]p["\x27][^>]*>(.*?)</DataArray>', m.group(1), re.S).group(1).split()]
        return [tuple(pts[i:i + 3]) for i in range(0, len(pts), 3)], faces, p
    tok = txt.split()
    i = tok.index("POINTS"); n = int(tok[i + 1])
    P = [tuple(float(c) for c in tok[i + 3 + 3 * k:i + 6 + 3 * k]) for k in range(n)]
    i = tok.index("POLYGONS"); nf = int(tok[i + 1]); j = i + 3; faces = []
    for _ in range(nf):
        m = int(tok[j]); faces.append([int(c) for c in tok[j + 1:j + 1 + m]]); j += 1 + m
    k = tok.index("CELL_DATA"); rest = tok[k + 2:]
    r = 3
    for _ in range(int(rest[2])):
        name, nc, nt = rest[r], int(rest[r + 1]), int(rest[r + 2])
        vals = [float(v) for v in rest[r + 4:r + 4 + nc * nt]]
        if name == "p":
            return P, faces, vals
        r += 4 + nc * nt
    raise SystemExit("no p on the walls")


root = os.path.join(run, "postProcessing", "surfaces")
t = sorted(os.listdir(root), key=float)[-1]
f = [x for x in os.listdir(os.path.join(root, t)) if x.startswith("walls.")][0]
P, faces, p = read(os.path.join(root, t, f))


def inside(r, c):
    if "axle" in r:
        ax, az, rr = r["axle"]
        return math.hypot(c[0] - ax, c[2] - az) <= rr and (c[1] >= r.get("y", [-1e9])[0])
    for k, key in enumerate("xyz"):
        if key in r and not (r[key][0] <= c[k] <= r[key][1]):
            return False
    return True


acc = {r["name"]: [0.0, 0.0, 0.0] for r in regs}
acc["the rest"] = [0.0, 0.0, 0.0]
for fi, fc in enumerate(faces):
    pts = [P[i] for i in fc]
    c = [sum(v[k] for v in pts) / len(pts) for k in range(3)]
    # the polygon's area vector
    S = [0.0, 0.0, 0.0]
    for a, b in zip(pts, pts[1:] + pts[:1]):
        S[0] += (a[1] - c[1]) * (b[2] - c[2]) - (a[2] - c[2]) * (b[1] - c[1])
        S[1] += (a[2] - c[2]) * (b[0] - c[0]) - (a[0] - c[0]) * (b[2] - c[2])
        S[2] += (a[0] - c[0]) * (b[1] - c[1]) - (a[1] - c[1]) * (b[0] - c[0])
    S = [v / 2 for v in S]
    name = next((r["name"] for r in regs if inside(r, c)), "the rest")
    for k in range(3):
        acc[name][k] += p[fi] * S[k] / q * scale
out = {k: {"CD.A": round(v[0], 3), "CL.A": round(v[2], 3)} for k, v in acc.items()}
tot = [sum(v[k] for v in acc.values()) for k in range(3)]
out["pressure total"] = {"CD.A": round(tot[0], 3), "CL.A": round(tot[2], 3)}
json.dump(out, sys.stdout, indent=1)
print()
