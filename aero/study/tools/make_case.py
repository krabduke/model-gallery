"""Write an OpenFOAM case (simpleFoam, k-omega SST) from a case's case.json.

    python3 tools/make_case.py cases/<case>/case.json runs/<case>

case.json:
    {"U": 50.0, "aoa_deg": 0.0,                 free stream, and its angle
                                                 up from +x in the x-z plane
     "domain": [[x0, y0, z0], [x1, y1, z1]],     the box; y0 = 0 is the
                                                 symmetry plane
     "cell": 0.2,                                background cell, m
     "ground": true,                             zmin a moving road
     "surfaces": {"body": {"level": [5, 6]},
                  "wheel_front": {"level": [5, 6], "omega": -149.3,
                                  "origin": [0.9, 0, 0.335]}},
     "boxes": [{"min": [...], "max": [...], "level": 3}],
     "inside": [x, y, z],                        a point in the fluid
     "cofr": [x, y, z], "lref": 3.15, "aref": 1.0,
     "iterations": 1500, "procs": 8}

The surfaces' STLs must already be in <run>/constant/triSurface (see
export_stl.py). Forces are reported for all the surfaces together, as
coefficients on `aref` -- with aref 1 m2 they are the force areas CL.A
and CD.A of the half model -- and a pitching moment about `cofr` on
`lref`, which with lref the wheelbase and cofr midway splits the lift
front and rear.
"""
import json
import math
import os
import sys

cfg = json.load(open(sys.argv[1]))
run = sys.argv[2]
U = cfg["U"]
a = math.radians(cfg.get("aoa_deg", 0.0))
Uvec = (U * math.cos(a), 0.0, U * math.sin(a))
lift_dir = (-math.sin(a), 0.0, math.cos(a))
drag_dir = (math.cos(a), 0.0, math.sin(a))
(x0, y0, z0), (x1, y1, z1) = cfg["domain"]
cell = cfg["cell"]
ground = cfg.get("ground", False)
surf = cfg["surfaces"]
procs = cfg.get("procs", 8)
v3 = lambda v: "(" + " ".join(f"{c:.6g}" for c in v) + ")"

HEAD = """FoamFile
{{
    version     2.0;
    format      ascii;
    class       {cls};
    object      {obj};
}}
"""


def write(path, cls, obj, body):
    full = os.path.join(run, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w") as fh:
        fh.write(HEAD.format(cls=cls, obj=obj) + body)


# ---------------------------------------------------------------- mesh
nx = max(1, round((x1 - x0) / cell))
ny = max(1, round((y1 - y0) / cell))
nz = max(1, round((z1 - z0) / cell))
write("system/blockMeshDict", "dictionary", "blockMeshDict", f"""
scale 1;
vertices
(
    ({x0} {y0} {z0}) ({x1} {y0} {z0}) ({x1} {y1} {z0}) ({x0} {y1} {z0})
    ({x0} {y0} {z1}) ({x1} {y0} {z1}) ({x1} {y1} {z1}) ({x0} {y1} {z1})
);
blocks ( hex (0 1 2 3 4 5 6 7) ({nx} {ny} {nz}) simpleGrading (1 1 1) );
boundary
(
    inlet     {{ type patch; faces ((0 4 7 3)); }}
    outlet    {{ type patch; faces ((1 2 6 5)); }}
    symmetry  {{ type symmetryPlane; faces ((0 1 5 4)); }}
    side      {{ type patch; faces ((3 7 6 2)); }}
    lower     {{ type {'wall' if ground else 'patch'}; faces ((0 3 2 1)); }}
    upper     {{ type patch; faces ((4 5 6 7)); }}
);
""")

geo = "\n".join(f'    {n}.stl {{ type triSurfaceMesh; name {n}; }}' for n in surf)
boxes = cfg.get("boxes", [])
geo += "\n" + "\n".join(f'    box{i} {{ type searchableBox; min {v3(b["min"])}; max {v3(b["max"])}; }}'
                        for i, b in enumerate(boxes))
feats = "\n".join(f'        {{ file "{n}.eMesh"; level {s["level"][1]}; }}' for n, s in surf.items())
refs = "\n".join(f'        {n} {{ level ({s["level"][0]} {s["level"][1]}); '
                 f'patchInfo {{ type {"patch" if "flow" in s else "wall"}; }} }}'
                 for n, s in surf.items())
regs = "\n".join(f'        box{i} {{ mode inside; levels ((1e15 {b["level"]})); }}'
                 for i, b in enumerate(boxes))
layers = "\n".join(f'        {n} {{ nSurfaceLayers {cfg.get("layers", 0)}; }}' for n in surf)
write("system/snappyHexMeshDict", "dictionary", "snappyHexMeshDict", f"""
castellatedMesh true;
snap            true;
addLayers       {'true' if cfg.get('layers', 0) else 'false'};
geometry
{{
{geo}
}}
castellatedMeshControls
{{
    maxLocalCells 4000000;
    maxGlobalCells {cfg.get('max_cells', 8000000)};
    minRefinementCells 10;
    maxLoadUnbalance 0.10;
    nCellsBetweenLevels 3;
    features
    (
{feats}
    );
    refinementSurfaces
    {{
{refs}
    }}
    resolveFeatureAngle {cfg.get('resolve_angle', 30)};
    refinementRegions
    {{
{regs}
    }}
    locationInMesh {v3(cfg["inside"])};
    allowFreeStandingZoneFaces true;
}}
snapControls
{{
    nSmoothPatch 3;
    tolerance 2.0;
    nSolveIter 50;
    nRelaxIter 5;
    nFeatureSnapIter 10;
    implicitFeatureSnap false;
    explicitFeatureSnap true;
    multiRegionFeatureSnap false;
}}
addLayersControls
{{
    relativeSizes true;
    layers
    {{
{layers}
    }}
    expansionRatio 1.25;
    finalLayerThickness 0.4;
    minThickness 0.1;
    nGrow 0;
    featureAngle 130;
    slipFeatureAngle 30;
    nRelaxIter 3;
    nSmoothSurfaceNormals 1;
    nSmoothNormals 3;
    nSmoothThickness 10;
    maxFaceThicknessRatio 0.5;
    maxThicknessToMedialRatio 0.3;
    minMedialAxisAngle 90;
    nBufferCellsNoExtrude 0;
    nLayerIter 50;
}}
meshQualityControls
{{
    #include "meshQualityDict"
}}
mergeTolerance 1e-6;
""")
write("system/meshQualityDict", "dictionary", "meshQualityDict", """
#includeEtc "caseDicts/mesh/generation/meshQualityDict.cfg"
""")
write("system/surfaceFeatureExtractDict", "dictionary", "surfaceFeatureExtractDict",
      "\n".join(f"""
{n}.stl
{{
    extractionMethod extractFromSurface;
    includedAngle 150;
    subsetFeatures {{ nonManifoldEdges no; openEdges yes; }}
    writeObj no;
}}""" for n in surf))
write("system/decomposeParDict", "dictionary", "decomposeParDict",
      f"\nnumberOfSubdomains {procs};\nmethod scotch;\n")

# ---------------------------------------------------------------- solver
iters = cfg.get("iterations", 1500)
# flow slices to sample at the end: the car's under its floor, a wing's across its span
sl = cfg.get("slices", [{"name": "under", "point": [0, 0, cfg.get("under_z", 0.05)],
                         "normal": [0, 0, 1]}] if ground else [])
slices = "\n".join(f"            {c['name']} {{ type cuttingPlane; point {v3(c['point'])}; "
                   f"normal {v3(c['normal'])}; interpolate true; }}" for c in sl)
walls = " ".join(surf)
cofr = cfg.get("cofr", [0, 0, 0])
write("system/controlDict", "dictionary", "controlDict", f"""
application     simpleFoam;
startFrom       latestTime;
startTime       0;
stopAt          endTime;
endTime         {iters};
deltaT          1;
writeControl    timeStep;
writeInterval   {iters};
purgeWrite      1;
writeFormat     binary;
writePrecision  8;
writeCompression off;
timeFormat      general;
timePrecision   6;
runTimeModifiable true;
functions
{{
    forceCoeffs
    {{
        type            forceCoeffs;
        libs            (forces);
        writeControl    timeStep;
        writeInterval   1;
        patches         ({walls});
        rho             rhoInf;
        rhoInf          1.225;
        CofR            {v3(cofr)};
        liftDir         {v3(lift_dir)};
        dragDir         {v3(drag_dir)};
        pitchAxis       (0 1 0);
        magUInf         {U};
        lRef            {cfg.get('lref', 1.0)};
        Aref            {cfg.get('aref', 1.0)};
    }}
    forces
    {{
        type            forces;
        libs            (forces);
        writeControl    timeStep;
        writeInterval   10;
        patches         ({walls});
        rho             rhoInf;
        rhoInf          1.225;
        CofR            {v3(cofr)};
    }}
    surfaces
    {{
        type            surfaces;
        libs            (sampling);
        writeControl    onEnd;
        surfaceFormat   vtk;
        formatOptions   {{ vtk {{ format ascii; }} }};
        fields          (p U);
        interpolationScheme cellPoint;
        surfaces
        {{
            walls {{ type patch; patches ({walls}); interpolate false; }}
            centre {{ type patch; patches (symmetry); interpolate true; }}
{slices}
        }}
    }}
    yPlus
    {{
        type            yPlus;
        libs            (fieldFunctionObjects);
        writeControl    onEnd;
    }}
}}
""")
write("system/fvSchemes", "dictionary", "fvSchemes", """
ddtSchemes { default steadyState; }
gradSchemes
{
    default         Gauss linear;
    grad(U)         cellLimited Gauss linear 1;
    grad(k)         cellLimited Gauss linear 1;
    grad(omega)     cellLimited Gauss linear 1;
}
divSchemes
{
    default         none;
    div(phi,U)      bounded Gauss linearUpwind grad(U);
    div(phi,k)      bounded Gauss upwind;
    div(phi,omega)  bounded Gauss upwind;
    div((nuEff*dev2(T(grad(U))))) Gauss linear;
}
laplacianSchemes { default Gauss linear limited corrected 0.33; }
interpolationSchemes { default linear; }
snGradSchemes { default limited corrected 0.33; }
wallDist { method meshWave; }
""")
write("system/fvSolution", "dictionary", "fvSolution", """
solvers
{
    p
    {
        solver          GAMG;
        smoother        GaussSeidel;
        tolerance       1e-7;
        relTol          0.1;
    }
    Phi
    {
        solver          GAMG;
        smoother        GaussSeidel;
        tolerance       1e-6;
        relTol          0.01;
    }
    "(U|k|omega)"
    {
        solver          smoothSolver;
        smoother        symGaussSeidel;
        tolerance       1e-8;
        relTol          0.1;
    }
}
SIMPLE
{
    consistent      yes;
    nNonOrthogonalCorrectors 0;
    residualControl { p 1e-5; U 1e-6; "(k|omega)" 1e-6; }
}
potentialFlow { nNonOrthogonalCorrectors 5; }
relaxationFactors
{
    equations { U 0.7; ".*" 0.5; }
    fields { p 1.0; }
}
""")

# ---------------------------------------------------------------- fields
k = 1.5 * (U * 0.005) ** 2
omega = math.sqrt(k) / (0.09 ** 0.25 * 0.1)
write("constant/transportProperties", "dictionary", "transportProperties",
      "\ntransportModel Newtonian;\nnu 1.5e-05;\n")
write("constant/turbulenceProperties", "dictionary", "turbulenceProperties",
      "\nsimulationType RAS;\nRAS { RASModel kOmegaSST; turbulence on; printCoeffs on; }\n")


def wall_U(n, s):
    # a fan's faces: the air leaves the domain through the one ahead of the
    # rotor and comes back through the one behind it, at the fan's flow
    if s.get("flow_dir") == "out":
        return (f"    {n} {{ type flowRateOutletVelocity; volumetricFlowRate {s['flow']}; "
                f"value uniform (0 0 0); }}")
    if s.get("flow_dir") == "in":
        return (f"    {n} {{ type flowRateInletVelocity; volumetricFlowRate {s['flow']}; "
                f"extrapolateProfile no; value uniform (0 0 0); }}")
    if "omega" in s:
        return (f"    {n} {{ type rotatingWallVelocity; origin {v3(s['origin'])}; "
                f"axis (0 1 0); omega {s['omega']}; }}")
    return f"    {n} {{ type noSlip; }}"


FAR = cfg.get("farfield", False)
OUTER = ("inlet", "outlet", "side", "upper", "lower")
Ub = [f"    inlet {{ type fixedValue; value uniform {v3(Uvec)}; }}",
      f"    outlet {{ type inletOutlet; inletValue uniform (0 0 0); value uniform {v3(Uvec)}; }}",
      "    symmetry { type symmetryPlane; }",
      "    side { type slip; }", "    upper { type slip; }",
      (f"    lower {{ type movingWallVelocity; value uniform {v3(Uvec)}; }}" if ground
       else "    lower { type slip; }")]
if FAR:
    # free stream on every outer face: the flow comes in or goes out
    # wherever it wants, so the angle of attack is just U's direction
    Ub = [f"    {n} {{ type freestreamVelocity; freestreamValue uniform {v3(Uvec)}; "
          f"value uniform {v3(Uvec)}; }}" for n in OUTER] + ["    symmetry { type symmetryPlane; }"]
Ub += [wall_U(n, s) for n, s in surf.items()]
write("0/U", "volVectorField", "U", f"""
dimensions [0 1 -1 0 0 0 0];
internalField uniform {v3(Uvec)};
boundaryField
{{
    #includeEtc "caseDicts/setConstraintTypes"
{chr(10).join(Ub)}
}}
""")
pb = ["    inlet { type zeroGradient; }", "    outlet { type fixedValue; value uniform 0; }",
      "    symmetry { type symmetryPlane; }", "    side { type slip; }",
      "    upper { type slip; }", "    lower { type zeroGradient; }"]
if FAR:
    pb = [f"    {n} {{ type freestreamPressure; freestreamValue uniform 0; value uniform 0; }}"
          for n in OUTER] + ["    symmetry { type symmetryPlane; }"]
pb += [f"    {n} {{ type zeroGradient; }}" for n in surf]
write("0/p", "volScalarField", "p", f"""
dimensions [0 2 -2 0 0 0 0];
internalField uniform 0;
boundaryField
{{
    #includeEtc "caseDicts/setConstraintTypes"
{chr(10).join(pb)}
}}
""")


def turb(name, val, wall):
    if FAR:
        kind = ("type calculated; value uniform 0;" if name == "nut" else
                f"type inletOutlet; inletValue uniform {val}; value uniform {val};")
        b = [f"    {n} {{ {kind} }}" for n in OUTER] + ["    symmetry { type symmetryPlane; }"]
        b += [f"    {n} {{ {flowbc(name, s, val) or wall} value uniform {val}; }}"
              for n, s in surf.items()]
        return "\n".join(b)
    b = [f"    inlet {{ type fixedValue; value uniform {val}; }}",
         f"    outlet {{ type inletOutlet; inletValue uniform {val}; value uniform {val}; }}",
         "    symmetry { type symmetryPlane; }", "    side { type slip; }",
         "    upper { type slip; }",
         (f"    lower {{ {wall} value uniform {val}; }}" if ground else "    lower { type slip; }")]
    b += [f"    {n} {{ {flowbc(name, s, val) or wall} value uniform {val}; }}"
          for n, s in surf.items()]
    return "\n".join(b)


def flowbc(name, s, val):
    """k, omega and nut on a fan's faces: out of the domain, zero gradient;
    back in, a fan's jet -- 5 % turbulence on a 20 mm mixing length."""
    if "flow" not in s:
        return None
    if name == "nut":
        return "type calculated;"
    if s["flow_dir"] == "out":
        return "type zeroGradient;"
    if name == "k":
        return "type turbulentIntensityKineticEnergyInlet; intensity 0.05;"
    return "type turbulentMixingLengthFrequencyInlet; mixingLength 0.02;"


write("0/k", "volScalarField", "k", f"""
dimensions [0 2 -2 0 0 0 0];
internalField uniform {k:.6g};
boundaryField
{{
    #includeEtc "caseDicts/setConstraintTypes"
{turb('k', f'{k:.6g}', 'type kqRWallFunction;')}
}}
""")
write("0/omega", "volScalarField", "omega", f"""
dimensions [0 0 -1 0 0 0 0];
internalField uniform {omega:.6g};
boundaryField
{{
    #includeEtc "caseDicts/setConstraintTypes"
{turb('omega', f'{omega:.6g}', 'type omegaWallFunction;')}
}}
""")
write("0/nut", "volScalarField", "nut", f"""
dimensions [0 2 -1 0 0 0 0];
internalField uniform 0;
boundaryField
{{
    #includeEtc "caseDicts/setConstraintTypes"
{turb('nut', '0', 'type nutkWallFunction;').replace('type fixedValue; value uniform 0;', 'type calculated; value uniform 0;').replace('type inletOutlet; inletValue uniform 0; value uniform 0;', 'type calculated; value uniform 0;')}
}}
""")

# ---------------------------------------------------------------- run script
with open(os.path.join(run, "Allrun"), "w") as fh:
    fh.write(f"""#!/bin/sh
# run inside `openfoam`: meshes in parallel, initialises with potentialFoam, solves
cd "$(dirname "$0")"
set -e
rm -rf 0.orig; cp -r 0 0.orig
surfaceFeatureExtract > log.features 2>&1
blockMesh > log.blockMesh 2>&1
decomposePar -force > log.decompose 2>&1
mpirun -np {procs} snappyHexMesh -parallel -overwrite > log.snappy 2>&1
mpirun -np {procs} checkMesh -parallel > log.checkMesh 2>&1 || true
# snappy leaves the fields as they were on the background mesh: put the
# uniform starting fields back in every processor's 0
# (restore0Dir -processor leaves decomposePar's files in place; copy)
for d in processor*; do rm -rf $d/0; cp -r 0.orig $d/0; done
mpirun -np {procs} potentialFoam -parallel -initialiseUBCs > log.potential 2>&1 || true
mpirun -np {procs} simpleFoam -parallel > log.simpleFoam 2>&1
echo DONE
""")
os.chmod(os.path.join(run, "Allrun"), 0o755)
print(f"CASE {run}: background {nx}x{ny}x{nz}, {len(surf)} surfaces, {iters} iterations")
