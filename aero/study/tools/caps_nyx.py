"""Caps that seal Nyx for a powered-off aero run, as a wind-tunnel model is
sealed: a slab across each intake just inside its lip, and a disc across
each nozzle's exit. Without the engines the ducts and nozzles open into an
empty fuselage, and the mesher would fill it.

    python3 tools/caps_nyx.py ../nyx-jet <out.stl>

Written in metres, the model's own frame, both sides.
"""
import math
import os
import struct
import sys

repo = os.path.abspath(sys.argv[1])
sys.path.insert(0, os.path.join(repo, "nyx"))
import spec              # noqa: E402
from parts import intakes, engines   # noqa: E402

MM = 0.001
tris = []


def slab(ring, x0, x1):
    """A closed prism: the polygon `ring` of (y, z) between x0 and x1."""
    cy = sum(p[0] for p in ring) / len(ring)
    cz = sum(p[1] for p in ring) / len(ring)
    n = len(ring)
    for k in range(n):
        a, b = ring[k], ring[(k + 1) % n]
        # the two ends, fanned from the middle
        tris.append(((x0, cy, cz), (x0, b[0], b[1]), (x0, a[0], a[1])))
        tris.append(((x1, cy, cz), (x1, a[0], a[1]), (x1, b[0], b[1])))
        # the side
        tris.append(((x0, a[0], a[1]), (x0, b[0], b[1]), (x1, b[0], b[1])))
        tris.append(((x0, a[0], a[1]), (x1, b[0], b[1]), (x1, a[0], a[1])))


# the intakes: just aft of the lip's furthest-aft point, grown into the wall
_, x_lip = intakes.lip_range()
xc = x_lip + 40.0
for sy in (1.0, -1.0):
    ring = [(sy * y, z) for (y, z) in intakes._shape(xc, 6.0)]
    slab(ring, xc - 5.0, xc + 5.0)

# the nozzles: a disc just inside each exit, into the flaps' walls
n = engines.info()["nozzle"]
x_exit = spec.ENGINE_FAN_FACE_X + n["x_exit"]
r = n["r_exit"] + 6.0
for sy in (1.0, -1.0):
    ring = [(sy * spec.ENGINE_Y + r * math.cos(2 * math.pi * k / 72),
             spec.ENGINE_Z + r * math.sin(2 * math.pi * k / 72)) for k in range(72)]
    slab(ring, x_exit - 20.0, x_exit - 8.0)

with open(sys.argv[2], "wb") as fh:
    fh.write(b"caps".ljust(80, b" "))
    fh.write(struct.pack("<I", len(tris)))
    for t in tris:
        fh.write(struct.pack("<3f", 0.0, 0.0, 0.0))
        for p in t:
            fh.write(struct.pack("<3f", *(c * MM for c in p)))
        fh.write(b"\0\0")
print(f"CAPS {len(tris)} triangles: intakes at x {xc:.0f} mm, nozzles at x {x_exit - 14:.0f} mm")
