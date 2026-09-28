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
    "opened onto the track, two millimetres from it, and the road shut them. Moved into the tunnel "
    "roofs, they worked, and showed the open floor could not: above 195 km/h an F1 car gripped "
    "harder. So the floor was sealed all round and held at a set suction, the wings retrimmed "
    "to suit, and the finished car was run at 180, 250 and 340 km/h.</p>")
vx1["caption"] = ("The finished car at 340 km/h, floor sealed. The deep blue under it is the plenum "
                  "the fans hold at 7 kPa; the orange on the nose and the wings' leading edges is "
                  "where the air stops against them.")
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
# the open floor as first finished: fans running at two speeds
u50, u70 = load("vx1_bal2_forces.json"), load("vx1_bal2_u70_forces.json")
qq = lambda u: 0.5 * RHO * u * u
if u50 and u70:
    vx1["open"] = {"kg50": round(-u50["Cl"]["mean"] * qq(50) / G),
                   "kg70": round(-u70["Cl"]["mean"] * qq(70) / G), "crossover": 195}
# the finished car: the floor sealed and held at 7 kPa, run at three speeds;
# a least-squares line through downforce against q splits it into what the
# plenum holds and what grows with speed
runs = [(u, load(f"vx1_seal2_u{u}_forces.json")) for u in (50, 70, 95)]
if all(d for _, d in runs):
    xs = [qq(u) for u, _ in runs]
    D = [-d["Cl"]["mean"] * qq(u) for u, d in runs]
    X = [d["Cd"]["mean"] * qq(u) for u, d in runs]
    n = len(xs); mx = sum(xs) / n
    fit = lambda ys: (sum((x - mx) * (y - sum(ys) / n) for x, y in zip(xs, ys))
                      / sum((x - mx) ** 2 for x in xs))
    a = fit(D); c0 = sum(D) / n - a * mx
    cda0 = fit(X)
    sys.path.insert(0, os.path.join(HERE, "..", "aero-hypercar", "aero"))
    import laptime
    ours, f1 = laptime.build_cars()
    segs = laptime.circuit(laptime.calibrate(f1))
    lap = [{"k": k, "ours": round(laptime.simulate(ours, segs, k)["time"], 2),
            "f1": round(laptime.simulate(f1, segs, k)["time"], 2)} for k in laptime.K_BAND]
    x_over = next((v for v in range(40, 450)
                   if ours.lat_capability(v / 3.6, 0.18) < f1.lat_capability(v / 3.6, 0.18)), None)
    kerb = next((v for v in range(40, 450)
                 if ours.lat_capability(v / 3.6, 0.18, 0.7) < f1.lat_capability(v / 3.6, 0.18)), None)
    front = lambda d: round(100 * d["Cl(f)"]["mean"] / d["Cl"]["mean"], 1)
    vx1["final"] = {
        "kg50": round(D[0] / G), "kg70": round(D[1] / G), "kg95": round(D[2] / G),
        "cla_v2": round(a, 3), "fan_kg": round(c0 / G), "cda": round(cda0, 3), "jet_n": 0,
        "front50": front(runs[0][1]), "front70": front(runs[1][1]), "front95": front(runs[2][1]),
        "lap": lap, "crossover": x_over, "kerb_crossover": kerb, "suction_kpa": 7.0,
        # what the spec had claimed, before: passive 4.55 m2 plus 650 kg of fan
        "said50": round(4.55 * qq(50) / G + 650), "said70": round(4.55 * qq(70) / G + 650),
        "said95": round(4.55 * qq(95) / G + 650),
        "said_lap": 10.7}
# the retrim for balance, step by step, fans running
steps = []
for name, what in (("vx1_fans_forces.json", "Open floor: intakes fixed, wings as designed"),
                   ("vx1_bal_forces.json", "Rear wing 17 to 4 degrees, front wing up 3 to 4"),
                   ("vx1_bal2_forces.json", "Rear wing flat, front wing 8 % larger and up 2 more"),
                   ("vx1_seal_u50_forces.json", "Floor sealed at 5.5 kPa, rear wing back to 17"),
                   ("vx1_seal2_u50_forces.json", "7 kPa, front wing 12 % larger and up 3 more")):
    d = load(name)
    if d:
        steps.append({"what": what, "front": round(100 * d["Cl(f)"]["mean"] / d["Cl"]["mean"], 1),
                      "cla": round(-d["Cl"]["mean"], 2), "cda": round(d["Cd"]["mean"], 2),
                      "kg": round(-d["Cl"]["mean"] * q / G, 0)})
vx1["steps"] = steps
F = vx1.get("final")
if F:
    vx1["notes"] = [
        ["The open floor could not work",
         "As first built the floor was open at the front: a venturi tunnel each side with a fan in "
         "its roof. Stopped, the fans left it full of rammed air and it lifted. Running, the air the "
         "car drove into the tunnels swamped them, and the 771 kg they appeared to hold came from "
         "forcing 4 m³/s through an intake choked to −31 kPa: about 380 kW of fan work from fans "
         "rated 38. Above 195 km/h an F1 car gripped harder."],
        ["So it was sealed",
         f"Skirts all round now, across the front and the back as well as down the sides, like the "
         f"Chaparral 2J's and the Brabham BT46B's. The fans hold each side at {F['suction_kpa']:.0f} kPa "
         f"and only have to move what leaks in under the skirts: 42 kW for the pair. Measured at "
         f"three speeds it holds {F['fan_kg']} kg at any speed, and the wings add to it."],
        ["Faster than F1 everywhere it goes",
         f"It out-grips an F1 car up to {F['crossover']} km/h, past F1's top speed, and laps "
         f"{lap[-1]['f1'] - lap[-1]['ours']:.1f} s quicker at the harsh end of the tyre model. The "
         f"limits, stated: riding a kerb with 30 % of the suction lost it holds to {F['kerb_crossover']} "
         f"km/h, and its top speed, 337 km/h, is level with F1's."]]
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
