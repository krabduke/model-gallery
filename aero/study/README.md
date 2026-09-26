# Aero study

The models' aerodynamics, checked with an outside solver. The VX-1's
downforce and drag were written into its spec as targets, and the Nyx's
come from our own vortex-lattice solve and a textbook drag polar; this runs
each through OpenFOAM (v2606, `simpleFoam`, steady RANS, k-omega SST) on
the built geometry and compares.

    tools/export_stl.py   the vehicle's outside, from its build, as STLs
    tools/caps_nyx.py     seals the Nyx's intakes and nozzles (powered off)
    tools/make_case.py    writes the OpenFOAM case from cases/<case>/case.json
    tools/post_forces.py  averaged forces and their convergence
    tools/cp_glb.py       surface pressure and flow slices as a web model

Runs go in `runs/` (not kept; tens of GB). Results in `results/`, the page
in the model gallery.

## Run one

    blender -b ../aero-hypercar/build/car.blend -P tools/export_stl.py -- \
        cases/vx1/geometry.json runs/vx1/constant/triSurface
    python3 tools/make_case.py cases/vx1/case.json runs/vx1
    openfoam -c runs/vx1/Allrun
    python3 tools/post_forces.py runs/vx1 2 > results/vx1.json
