"""Run a finished ground-vehicle case again at another speed, on its mesh.

    python3 tools/next_speed.py runs/<run> <old U> <new U> <more iterations>

Keeps the finished speed's forces (results/<run>_u<old>_forces.json) and
postProcessing (moved to postProcessing_u<old>); then in every processor's
latest fields the inlet and the road go to the new speed and each wheel's
spin with them, the force coefficients are referred to the new speed, and
the run is set to go on for `more` iterations from the old flow. The fans'
volume flow stays as it was -- they run at their own speed, not the car's.
"""
import json
import os
import re
import shutil
import subprocess
import sys

run, u0, u1, more = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), int(sys.argv[4])
here = os.path.dirname(os.path.abspath(__file__))
name = os.path.basename(os.path.normpath(run))
res = os.path.join(os.path.dirname(here), "results")

out = subprocess.run([sys.executable, os.path.join(here, "post_forces.py"), run, "2", "300"],
                     capture_output=True, text=True, check=True).stdout
d = json.loads(out)
d["U"] = u0
json.dump(d, open(os.path.join(res, f"{name}_u{u0:g}_forces.json"), "w"), indent=1)
keep = os.path.join(run, f"postProcessing_u{u0:g}")
if os.path.exists(keep):
    shutil.rmtree(keep)
shutil.move(os.path.join(run, "postProcessing"), keep)

k = u1 / u0
old_v, new_v = f"({u0:g} 0 0)".encode(), f"({u1:g} 0 0)".encode()
procs = sorted(p for p in os.listdir(run) if p.startswith("processor"))
last = max((t for t in os.listdir(os.path.join(run, procs[0])) if re.fullmatch(r"[0-9.]+", t)), key=float)
n = 0
for p in procs:
    f = os.path.join(run, p, last, "U")
    b = open(f, "rb").read()
    n += b.count(b"uniform " + old_v)
    b = b.replace(b"uniform " + old_v, b"uniform " + new_v)
    # the wheels spin with the road
    b = re.sub(rb"omega(\s+(?:constant\s+)?)(-?[0-9.eE+]+);",
               lambda m: b"omega" + m.group(1) + f"{float(m.group(2)) * k:.6g}".encode() + b";", b)
    open(f, "wb").write(b)
cd = open(os.path.join(run, "system", "controlDict")).read()
cd = re.sub(r"magUInf\s+[0-9.]+;", f"magUInf         {u1:g};", cd)
end = int(float(last)) + more
cd = re.sub(r"endTime\s+[0-9.]+;", f"endTime         {end};", cd)
cd = re.sub(r"writeInterval\s+[0-9.]+;", f"writeInterval   {end};", cd)
open(os.path.join(run, "system", "controlDict"), "w").write(cd)
print(f"SPEED {u0:g} -> {u1:g} m/s: {n} uniform velocities turned in {len(procs)} processors at "
      f"time {last}; wheels x{k:.3f}; running to {end}")
