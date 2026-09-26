"""Forces from a finished run: the mean over the last iterations, how much
they still wander, and the history for the page's convergence chart.

    python3 tools/post_forces.py runs/<run> <scale> [window] > results/<run>.json

`scale` turns the half model's coefficients into the whole vehicle's: 2
for the car (Aref 1 m2 on half a car gives half its CL.A), 1 for the jet
(Aref is half the wing, so the half model's coefficients are already the
aircraft's). The window (default 400 iterations) is averaged; its spread
-- the standard deviation of the coefficient over it -- is reported beside
the mean, so a run that has not settled says so.
"""
import json
import math
import os
import sys

run, scale = sys.argv[1], float(sys.argv[2])
window = int(sys.argv[3]) if len(sys.argv) > 3 else 400
base = os.path.join(run, "postProcessing", "forceCoeffs")
starts = sorted(os.listdir(base), key=float)
rows, head = [], None
for st in starts:
    for line in open(os.path.join(base, st, "coefficient.dat")):
        if line.startswith("#"):
            if "Time" in line:
                head = line[1:].split()
            continue
        v = line.split()
        if v:
            rows.append([float(c) for c in v])
rows.sort(key=lambda r: r[0])
col = {h: i for i, h in enumerate(head)}
last = rows[-window:]
out = {"iterations": int(rows[-1][0]), "window": len(last), "scale": scale}
for name in ("Cd", "Cl", "Cl(f)", "Cl(r)", "CmPitch", "Cs"):
    if name not in col:
        continue
    xs = [r[col[name]] * scale for r in last]
    m = sum(xs) / len(xs)
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / len(xs))
    out[name] = {"mean": round(m, 5), "sd": round(sd, 5)}
step = max(1, len(rows) // 300)
out["history"] = {"it": [int(r[0]) for r in rows[::step]],
                  "Cd": [round(r[col["Cd"]] * scale, 4) for r in rows[::step]],
                  "Cl": [round(r[col["Cl"]] * scale, 4) for r in rows[::step]]}
json.dump(out, sys.stdout, indent=1)
print()
