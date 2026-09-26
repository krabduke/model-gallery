"""Turn a finished free-stream run to a new angle of attack and restart it.

    python3 tools/next_alpha.py runs/<run> <old alpha> <new alpha> <more iterations>

Keeps the finished angle's forces and surfaces (postProcessing is moved to
postProcessing_a<old>, and its forces written to results/<run>_a<old>_forces.json),
turns the free stream in every processor's latest fields, turns lift and
drag with it in the force output, and sets the run to go on for `more`
iterations from where it stopped -- the flow at the last angle is a far
better start than the free stream. The fields are binary, but a uniform
free-stream value is written as text inside them, so it is replaced as
bytes.
"""
import json
import math
import os
import re
import shutil
import subprocess
import sys

run, a0, a1, more = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), int(sys.argv[4])
here = os.path.dirname(os.path.abspath(__file__))
name = os.path.basename(os.path.normpath(run))
res = os.path.join(os.path.dirname(here), "results")

# the finished angle
out = subprocess.run([sys.executable, os.path.join(here, "post_forces.py"), run, "1", "200"],
                     capture_output=True, text=True, check=True).stdout
d = json.loads(out)
d["alpha"] = a0
json.dump(d, open(os.path.join(res, f"{name}_a{a0:g}_forces.json"), "w"), indent=1)
keep = os.path.join(run, f"postProcessing_a{a0:g}")
if os.path.exists(keep):
    shutil.rmtree(keep)
shutil.move(os.path.join(run, "postProcessing"), keep)

# the new free stream
cd = open(os.path.join(run, "system", "controlDict")).read()
U = float(re.search(r"magUInf\s+([0-9.eE+-]+);", cd).group(1))
r0, r1 = math.radians(a0), math.radians(a1)
v = lambda a: f"({U * math.cos(a):.6g} 0 {U * math.sin(a):.6g})"
old_u, new_u = v(r0).encode(), v(r1).encode()
procs = sorted(p for p in os.listdir(run) if p.startswith("processor"))
last = max((t for t in os.listdir(os.path.join(run, procs[0])) if re.fullmatch(r"[0-9.]+", t)), key=float)
n = 0
for p in procs:
    f = os.path.join(run, p, last, "U")
    b = open(f, "rb").read()
    k = b.count(b"freestreamValue uniform " + old_u)
    b = b.replace(b"freestreamValue uniform " + old_u, b"freestreamValue uniform " + new_u)
    open(f, "wb").write(b)
    n += k
if n == 0:
    raise SystemExit(f"no free-stream value {old_u.decode()} found in {procs[0]}/{last}/U")

# lift and drag turned with it; on for `more` iterations
lift = f"({-math.sin(r1):.6g} 0 {math.cos(r1):.6g})"
drag = f"({math.cos(r1):.6g} 0 {math.sin(r1):.6g})"
cd = re.sub(r"liftDir\s+\([^)]*\);", f"liftDir         {lift};", cd)
cd = re.sub(r"dragDir\s+\([^)]*\);", f"dragDir         {drag};", cd)
end = int(float(last)) + more
cd = re.sub(r"endTime\s+[0-9.]+;", f"endTime         {end};", cd)
cd = re.sub(r"writeInterval\s+[0-9.]+;", f"writeInterval   {end};", cd)
open(os.path.join(run, "system", "controlDict"), "w").write(cd)
print(f"ALPHA {a0:g} -> {a1:g}: {n} free-stream entries turned in {len(procs)} processors at "
      f"time {last}; running to {end}")
