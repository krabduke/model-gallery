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
off, on = load("vx1_forces.json"), load("vx1_fans_forces.json")
reg_off, reg_on = load("vx1_regions.json"), load("vx1_fans_regions.json")
vx1 = {
    "U": U,
    "claims": {
        "cla": car.cla(), "cda": car.cda(), "balance": 100 * car.AERO["aero_balance"],
        "wings": car.AERO["cla_wings"], "floor": car.AERO["cla_floor"],
        "fan_kg": car.FAN["downforce_kg"],
        "cla_src": f"spec target: wings {car.AERO['cla_wings']} + floor {car.AERO['cla_floor']}, never computed",
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
    "<p>Two runs of the car as built, at 180 km/h over a moving road with the wheels turning: "
    "once with the fans stopped, once with them drawing 8 m³/s out of the sealed floor, as the "
    "spec says they do. The first attempt at the second run found the fans could not breathe at "
    "all: their intakes opened onto the track, two millimetres from it, and the road shut them. "
    "They now open in the tunnel roofs, and the car was rebuilt before the run below.</p>")
vx1["caption"] = ("Fans running. The deep blue under the floor is the plenum they hold under "
                  "suction; the orange on the nose and the wings' leading edges is where the air "
                  "stops against them.")
if reg_off and reg_on:
    w_off = -(reg_off["front wing"]["CL.A"] + reg_off["rear wing"]["CL.A"])
    w_on = -(reg_on["front wing"]["CL.A"] + reg_on["rear wing"]["CL.A"])
    f_off, f_on = -reg_off["floor and diffuser"]["CL.A"], -reg_on["floor and diffuser"]["CL.A"]
    front_on = 100 * on["Cl(f)"]["mean"] / on["Cl"]["mean"]
    vx1["notes"] = [
        ["The fans are the car",
         f"Stopped, they leave the sealed floor full of air rammed in at the nose, and it lifts: "
         f"{-f_off:+.1f} m². Running, they pull it down to {f_on:.1f} m² of downforce, most of "
         f"the car's total. The spec had it the other way round: the floor's downforce as a "
         f"given, the fans on top."],
        ["The wings do better than claimed",
         f"Front and rear together make {w_off:.2f} m² with the fans off and {w_on:.2f} with them "
         f"on, against the {car.AERO['cla_wings']} the spec gave them. The rear wing is also the "
         f"largest single source of drag."],
        ["The balance is further aft",
         f"With the fans running {front_on:.0f} % of the downforce is on the front axle, not the "
         f"{100 * car.AERO['aero_balance']:.1f} % the spec and the lap simulation assume: the "
         f"fans pull hardest at the back of the floor, where their intakes are."]]
if off and on:
    vx1["total_said_kg"] = round(car.cla() * q / G + car.FAN["downforce_kg"], 0)
    vx1["total_got_kg"] = round(-on["Cl"]["mean"] * q / G, 0)
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
    sm, x_np, x_cg, cla = vlm.static_margin()
    nyx_claims = {"cla": float(cla), "sm": float(100 * sm), "cd0": agility.CD0,
                  "x_np": float(x_np), "x_cg": float(x_cg),
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
        j0 = agility.Jet()
        s_cfd, s_ours = j.best_sustained(0.0), j0.best_sustained(0.0)
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
