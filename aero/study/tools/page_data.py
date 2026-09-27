"""The study page's data: each vehicle's claims, straight from its spec,
beside what the runs measured.

    python3 tools/page_data.py ../model-gallery/aero/data

Reads results/*.json (written by post_forces.py and post_regions.py) and
writes vx1.json and nyx.json for the page. A run that has not finished is
simply left out, and the page says so.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = sys.argv[1]
RES = os.path.join(HERE, "results")
load = lambda n: json.load(open(os.path.join(RES, n))) if os.path.exists(os.path.join(RES, n)) else None

# ------------------------------------------------------------------ VX-1
sys.path.insert(0, os.path.join(HERE, "..", "aero-hypercar", "car"))
import spec as car   # noqa: E402

U, RHO, G = 50.0, 1.225, 9.81
q = 0.5 * RHO * U * U
# fans off: the car as first built; fans on: the finished car, at 180 km/h
off, on = load("vx1_forces.json"), load("vx1_bal2_forces.json")
reg_off, reg_on = load("vx1_regions.json"), load("vx1_bal2_regions.json")
# What we had published, before the study: fixed here, because the specs
# now carry what the study measured.
PUBLISHED_VX1 = {"cla": 4.55, "wings": 1.20, "floor": 3.35, "cda": 1.28, "balance": 44.5,
                 "fan_kg": 650.0}
vx1 = {
    "U": U,
    "claims": {
        **PUBLISHED_VX1,
        "cla_src": "spec target: wings 1.20 + floor 3.35, never computed",
        "cda_src": "spec target, never computed",
        "bal_src": "spec target",
        "fan_src": "spec: 1.2 kPa of plenum suction over the sealed floor",
    },
}
if off:
    vx1["results"] = off
    if reg_off:
        vx1["regions_off"] = reg_off
if on:
    vx1["fans"] = on
    if reg_on:
        vx1["regions_on"] = reg_on
    # what the fans add, in kilograms at this speed
    vx1["fan_kg"] = round(-(on["Cl"]["mean"] - (off["Cl"]["mean"] if off else 0)) * q / G, 0)
vx1["intro"] = (
    "<p>The car as built, at 180 km/h over a moving road with its wheels turning: once with the "
    "fans stopped, once with them drawing 8 m³/s out of the sealed floor as the spec says they do. "
    "The first attempt at the second run found the fans could not breathe at all: their intakes "
    "opened onto the track, two millimetres from it, and the road shut them. They were moved into "
    "the tunnel roofs, the wings were retrimmed for balance, and the finished car was run again "
    "at 180 and at 250 km/h.</p>")
vx1["caption"] = ("The finished car, fans running. The deep blue under the floor is the plenum they "
                  "hold under suction; the orange on the nose and the wings' leading edges is where "
                  "the air stops against them.")
if reg_off:
    w_off = -(reg_off["front wing"]["CL.A"] + reg_off["rear wing"]["CL.A"])
    f_off = -reg_off["floor and diffuser"]["CL.A"]
    vx1["notes"] = [
        ["The fans are the car",
         f"Stopped, they leave the sealed floor full of air rammed in at the nose, and it lifts: "
         f"{-f_off:+.1f} m². Running, they hold the car down with a force that hardly changes with "
         f"speed, as a fan car's should: 771 kg at 180 km/h, 732 at 250."],
        ["The wings do better than claimed",
         f"Front and rear together made {w_off:.2f} m² with the fans off, against the "
         f"1.20 the spec gave them. After the retrim the rear "
         f"wing is flat and the front wing carries the balance."],
        ["Fast corners are Formula 1's",
         "An F1 car's downforce grows with the square of its speed and the VX-1's hardly does, so "
         "below 195 km/h the fan car grips harder and above it the F1 car does. Over a lap it is "
         "still quicker, by 1.5 s, not the 10.7 we had claimed."]]
# the finished car: fans running at two speeds, and what they split into
u50, u70 = load("vx1_bal2_forces.json"), load("vx1_bal2_u70_forces.json")
if u50 and u70:
    qq = lambda u: 0.5 * RHO * u * u
    D50, D70 = -u50["Cl"]["mean"] * qq(50), -u70["Cl"]["mean"] * qq(70)
    a = (D70 - D50) / (qq(70) - qq(50))
    X50, X70 = u50["Cd"]["mean"] * qq(50), u70["Cd"]["mean"] * qq(70)
    cda0 = (X70 - X50) / (qq(70) - qq(50))
    # the car's own lap simulation, on the spec that now carries these
    sys.path.insert(0, os.path.join(HERE, "..", "aero-hypercar", "aero"))
    import laptime
    ours, f1 = laptime.build_cars()
    segs = laptime.circuit(laptime.calibrate(f1))
    lap = [{"k": k, "ours": round(laptime.simulate(ours, segs, k)["time"], 2),
            "f1": round(laptime.simulate(f1, segs, k)["time"], 2)} for k in laptime.K_BAND]
    vx1["final"] = {
        "kg50": round(D50 / G), "kg70": round(D70 / G), "cla_v2": round(a, 3),
        "fan_kg": round((D50 - a * qq(50)) / G), "cda": round(cda0, 3),
        "jet_n": round((cda0 - u50["Cd"]["mean"]) * qq(50)),
        "front50": round(100 * u50["Cl(f)"]["mean"] / u50["Cl"]["mean"], 1),
        "front70": round(100 * u70["Cl(f)"]["mean"] / u70["Cl"]["mean"], 1),
        "lap": lap,
        # what the spec had claimed, before: passive 4.55 m2 plus 650 kg of fan
        "said50": round(4.55 * qq(50) / G + 650), "said70": round(4.55 * qq(70) / G + 650),
        "said_lap": 10.7}
# the retrim for balance, step by step, fans running
steps = []
for name, what in (("vx1_fans_forces.json", "Intakes fixed, wings as designed"),
                   ("vx1_bal_forces.json", "Rear wing 17 to 4 degrees, front wing up 3 to 4"),
                   ("vx1_bal2_forces.json", "Rear wing flat, front wing 8 % larger and up 2 more")):
    d = load(name)
    if d:
        steps.append({"what": what, "front": round(100 * d["Cl(f)"]["mean"] / d["Cl"]["mean"], 1),
                      "cla": round(-d["Cl"]["mean"], 2), "cda": round(d["Cd"]["mean"], 2),
                      "kg": round(-d["Cl"]["mean"] * q / G, 0)})
vx1["steps"] = steps
json.dump(vx1, open(os.path.join(OUT, "vx1.json"), "w"), indent=1)

# ------------------------------------------------------------------ Nyx
nyx_runs = sorted((json.load(open(os.path.join(RES, f))) for f in os.listdir(RES)
                   if f.startswith("nyx_a") and f.endswith("_forces.json")),
                  key=lambda d: d["alpha"])
sys.modules.pop("spec", None)      # the car's has the same name
sys.path.insert(0, os.path.join(HERE, "..", "nyx-jet", "nyx"))
sys.path.insert(0, os.path.join(HERE, "..", "nyx-jet", "aero"))
try:
    import vlm, agility   # noqa: E402
    _, cla = vlm.neutral_point()     # the lattice itself is unchanged
    # published before the study; the aero modules now carry what it measured
    nyx_claims = {"cla": float(cla), "sm": -4.8, "cd0": 0.018,
                  "cla_src": "our vortex-lattice solve, canards and wing",
                  "sm_src": "the same solve's neutral point against the combat CG",
                  "cd0_src": "assumed: a clean stealth fighter, 0.016 to 0.022"}
except Exception as e:     # the page still builds without the Nyx's code
    print("nyx claims:", e)
    nyx_claims = {}
nyx = {"claims": nyx_claims}
if nyx_runs:
    import math
    nyx["alpha"] = [d["alpha"] for d in nyx_runs]
    nyx["CL"] = [d["Cl"]["mean"] for d in nyx_runs]
    nyx["CD"] = [d["Cd"]["mean"] for d in nyx_runs]
    nyx["Cm"] = [d["CmPitch"]["mean"] for d in nyx_runs]
    if len(nyx_runs) >= 2:
        a0, a1 = (math.radians(d["alpha"]) for d in nyx_runs[:2])
        dCL = nyx["CL"][1] - nyx["CL"][0]
        dCm = nyx["Cm"][1] - nyx["Cm"][0]
        K = (nyx["CD"][1] - nyx["CD"][0]) / (nyx["CL"][1] ** 2 - nyx["CL"][0] ** 2)
        nyx["derived"] = {"cla": dCL / (a1 - a0), "sm": -100 * dCm / dCL,
                          "cd0": nyx["CD"][0], "K": K}
        # what the measured polar does to the published sustained turn
        j = agility.Jet(cd0=nyx["CD"][0]); j.K = K
        s_cfd = j.best_sustained(0.0)
        s_ours = (25.5, None, 5.29)          # as published, on CD0 0.018 and e 0.72
        class _J: K = 0.1731
        j0 = _J()
        nyx["claims"]["K"] = j0.K
        nyx["claims"]["K_src"] = "assumed: an Oswald factor of 0.72 on aspect ratio 2.55"
        nyx["turn"] = {"ours": round(s_ours[0], 1), "ours_g": round(s_ours[2], 2),
                       "cfd": round(s_cfd[0], 1), "cfd_g": round(s_cfd[2], 2)}
        d = nyx["derived"]
        nyx["intro"] = (
            "<p>Two runs of the aircraft as built, gear up and doors shut, at 100 m/s (Mach 0.29): "
            "at no angle of attack, and at 8 degrees, started from the first. Two angles are enough "
            "for what decides how it flies: how fast lift grows with angle, whether the nose-up "
            "moment grows with it (which is what unstable means), and the drag.</p>")
        nyx["caption"] = ("At 8 degrees. The canards' and the wing's leading edges carry the deepest "
                          "suction; the capped intakes and nozzles are the orange faces.")
        nyx["cd0_note"] = "part of it is the blunt base of the capped nozzles, as on any powered-off model"
        nyx["notes"] = [
            ["Unstable, and a little more so",
             f"The pitching moment rises with lift: a static margin of {d['sm']:.1f} % of the chord, "
             f"against the {nyx_claims['sm']:.1f} % our vortex-lattice code gave. That code sees only "
             f"the lifting surfaces; the fuselage ahead of the CG adds its own nose-up moment, the usual "
             f"difference. More instability asks more of the flight control computers."],
            ["The lift holds",
             f"Lift grows at {d['cla']:.2f} per radian, {100 * (d['cla'] / nyx_claims['cla'] - 1):.0f} % "
             f"above the vortex-lattice figure: the canard and wing were modelled right, and the "
             f"instantaneous turn rate, which lift sets, stands."],
            ["Less sustained turn",
             f"Drag is higher on both counts: {d['cd0']:.4f} at zero lift, and "
             f"{100 * (K / j0.K - 1):.0f} % more drag due to lift than the assumed Oswald factor gives. "
             f"Through the same energy-manoeuvrability sums the best sustained turn at sea level falls "
             f"from {s_ours[0]:.1f} to {s_cfd[0]:.1f} degrees a second."]]
json.dump(nyx, open(os.path.join(OUT, "nyx.json"), "w"), indent=1)
print(f"PAGE vx1: {'off' if off else '-'} {'on' if on else '-'}; nyx: {len(nyx_runs)} angles")
