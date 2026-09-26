"""Rebuild a run's forceCoeffs table from its solver log, for when the
function object printed its coefficients but wrote no file (it happens on a
restart after postProcessing is moved aside).

    python3 tools/forces_from_log.py runs/<run>/log.x runs/<run>/postProcessing/forceCoeffs/<start>
"""
import os
import re
import sys

log, out = sys.argv[1], sys.argv[2]
names = ["Cd", "Cd(f)", "Cd(r)", "Cl", "Cl(f)", "Cl(r)", "CmPitch", "CmRoll", "CmYaw", "Cs", "Cs(f)", "Cs(r)"]
rows, t, cur = [], None, {}
for line in open(log):
    m = re.match(r"^Time = ([0-9.eE+-]+)", line)
    if m:
        t = float(m.group(1))
        continue
    m = re.match(r"^\s+(C[a-zA-Z]+(?:\([fr]\))?):\s+([-0-9.eE+]+)", line)
    if m and t is not None:
        cur[m.group(1)] = float(m.group(2))
        if m.group(1) == "Cs(r)":
            rows.append([t] + [cur.get(n, 0.0) for n in names])
            cur = {}
os.makedirs(out, exist_ok=True)
with open(os.path.join(out, "coefficient.dat"), "w") as fh:
    fh.write("# rebuilt from " + os.path.basename(log) + "\n#\n# Time\t" + "\t".join(names) + "\n")
    for r in rows:
        fh.write("\t".join(f"{v:.8g}" for v in r) + "\n")
print(f"FORCES {len(rows)} rows from {log}")
