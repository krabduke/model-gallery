"""The VX-1's fans as a CFD sees them: each rotor taken out and replaced by
two slabs across its shroud, one either side of where the rotor was. The
air leaves the domain through the face ahead (fan_suck) and comes back
through the face behind (fan_blow) at the fan's volume flow -- the usual
way to put a fan into a steady external-aero run without the rotor's
blades. The pressure on the two faces is the rotor's thrust, so they are
counted in the car's forces.

    python3 tools/fan_slabs.py ../aero-hypercar <out dir>

Writes fan_suck.stl and fan_blow.stl, in metres.
"""
import math
import os
import struct
import sys

repo = os.path.abspath(sys.argv[1])
sys.path.insert(0, os.path.join(repo, "car"))
import spec   # noqa: E402

F = spec.FAN
R = F["duct_r"] + 6.0          # into the shroud's wall
MM = 0.001


def slab(cx, cy, cz, x0, x1, n=64):
    tris = []
    ring = [(cy + R * math.cos(2 * math.pi * k / n), cz + R * math.sin(2 * math.pi * k / n))
            for k in range(n)]
    for k in range(n):
        a, b = ring[k], ring[(k + 1) % n]
        tris.append(((x0, cy, cz), (x0, b[0], b[1]), (x0, a[0], a[1])))
        tris.append(((x1, cy, cz), (x1, a[0], a[1]), (x1, b[0], b[1])))
        tris.append(((x0, a[0], a[1]), (x0, b[0], b[1]), (x1, b[0], b[1])))
        tris.append(((x0, a[0], a[1]), (x1, b[0], b[1]), (x1, a[0], a[1])))
    return tris


def write(path, name, tris):
    with open(path, "wb") as fh:
        fh.write(name.encode().ljust(80, b" "))
        fh.write(struct.pack("<I", len(tris)))
        for t in tris:
            fh.write(struct.pack("<3f", 0.0, 0.0, 0.0))
            for p in t:
                fh.write(struct.pack("<3f", *(c * MM for c in p)))
            fh.write(b"\0\0")


x = F["x"]
suck, blow = [], []
for sy in (-1.0, 1.0):
    suck += slab(x, sy * F["y"], F["z"], x - 30.0, x - 22.0)
    blow += slab(x, sy * F["y"], F["z"], x + 22.0, x + 30.0)
out = sys.argv[2]
write(os.path.join(out, "fan_suck.stl"), "fan_suck", suck)
write(os.path.join(out, "fan_blow.stl"), "fan_blow", blow)
print(f"FANS at x {x:.0f} mm, y +-{F['y']:.0f}, z {F['z']:.0f}, bore {2 * F['duct_r']:.0f} mm: "
      f"suck at x {x - 26:.0f}, blow at x {x + 26:.0f}")
