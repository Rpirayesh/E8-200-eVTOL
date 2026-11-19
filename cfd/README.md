# CFD (work package C)

OpenFOAM v2412 (`simpleFoam`, incompressible steady RANS, k-omega SST) tool chain for the E8-200, adapted from the
E8-S subscale project and validated at full-scale Reynolds numbers (3-6 million on the wing chord). The validation
evidence (cases, plots, grid-convergence numbers, the uncertainty bands applied to design results) is in
[`validation/cfd/README.md`](../validation/cfd/README.md).

## Layout

| Path | Content |
|---|---|
| `tools/ogrid.py` | Structured 2-D O-grid (normal marching, nested coarsening for grid studies), vectorised polyMesh writer |
| `tools/airfoil2d.py` | 2-D section polars: NACA 0012 grid study, wall-function study, GA(W)-1 validation, any design section (`section`) |
| `tools/gci.py` | Richardson extrapolation and grid convergence index (Celik et al. 2008) |
| `tools/actuator.py` | Rotor actuator disks: topoSet cell zones and momentum sources (uniform or radius-weighted loading) |
| `tools/mesh3d.py` | Generic 3-D set-up: blockMesh + snappyHexMesh with prism layers, SST with wall functions, force functions |
| `tools/oml.py` | Parametric outer mould line from `design/geometry.json` -> one STL per force-breakdown region |
| `tools/aircraft3d.py` | Full-aircraft half model: cruise alpha sweeps, hover with actuator disks, post-processing |
| `tools/rotor_disk.py` | Actuator-disk validation (momentum theory, Felker & Light rotor-over-wing download) |
| `tools/wing3d.py` | Finite-wing validation (lift slope, induced drag, mesh sensitivity) |
| `tools/report.py` | Builds the validation plots and tables from `validation/cfd/data/*.json` |
| `tools/watchdog.py` | Stops steady cases once the force coefficients stop changing (runs with `runTimeModifiable`) |
| `tools/mission_check.py` | Re-flies the frozen design's mission (sizing model energy terms) with the CFD CD0, Oswald factor and download |
| `examples/geometry_example.json` | Example input used only to exercise the pipeline before the design is frozen |
| `results/` | Design results (JSON, PNG) - phase 2 |
| `.cache/` | Scratch OpenFOAM cases (git-ignored, can be deleted) |

Environment: `source ~/tools/foamenv.sh` (OpenFOAM, MPICH), Python `~/tools/cadenv/bin/python` (numpy, scipy, trimesh,
aerosandbox, neuralfoil). At most 12 cores are used.

## Running the design analysis (phase 2)

```bash
P=~/tools/cadenv/bin/python
G="--geometry design/geometry_cfd.json"
$P cfd/tools/aircraft3d.py geometry $G                    # STLs of the cruise (stopped blades) and hover (hubs only) sets
$P cfd/tools/aircraft3d.py mesh --mode cruise --lev 1 $G  # production: lifting surfaces at c/128 (validated level); --lev 0 for tests
$P cfd/tools/aircraft3d.py cruise --lev 1 --alphas -4 0 3 6 9 12 $G
$P cfd/tools/aircraft3d.py mesh --mode hover $G
$P cfd/tools/aircraft3d.py hover --loading linear $G      # lift rotors as actuator disks at hover thrust
$P cfd/tools/aircraft3d.py transition --speed 38.4 --alphas 0 --lift-frac 0.5 --pusher-thrust 800 $G
$P cfd/tools/aircraft3d.py post $G                        # -> cfd/results/cruise.json, hover_*.json, transition_*.json, plots
$P cfd/tools/mission_check.py --cd0 <CFD> --e <CFD> --download <CFD/1.46>   # mission closure of the frozen design
$P cfd/tools/airfoil2d.py section --coords <file.dat> --re 4e6 --tag wing   # 2-D polar of the selected section
```

## What the CFD needs in `design/geometry.json`

Axes: **x aft from the nose, y to the right (starboard), z up, metres, degrees.** The aircraft must be symmetric about
y = 0 (the CFD is a half model); rotors are given for both sides (the port ones are ignored by the mesher and replaced
by the mirror image). Items marked *optional* have defaults.

```jsonc
{
  "reference": {                 // optional; otherwise computed from the wing trapezoid
    "S_ref": 8.2, "c_ref": 0.96, "b_ref": 8.6,
    "x_ref": 2.55, "z_ref": 1.30           // moment reference point (CG at MTOW)
  },
  "wing": {
    "airfoil": "ls417",          // "nacaXXXX", "naca230XX", "ls417"/"gaw1", or a Selig-format .dat path (repo-relative)
    "span": 8.6,                 // tip to tip
    "root_chord": 1.05, "tip_chord": 0.85,
    "x_le_root": 2.30,           // leading edge of the root (centre-line) section
    "z_root": 1.55,              // chord-line height of the root LE
    "y_root": 0.0,               // optional; if > 0 the root section is carried to the centre line
    "sweep_le_deg": 0.0, "dihedral_deg": 1.5,
    "incidence_deg": 2.0,        // root incidence relative to the fuselage x axis
    "twist_tip_deg": -2.0,       // tip twist relative to the root (negative = washout)
    "sections": [ ... ],         // optional, replaces the trapezoid: [{"y","x_le","z","chord","twist_deg"}], y >= 0
    "spar_x_c": [0.15, 0.6]      // not used by CFD (FEA/CAD)
  },
  "fuselage": {
    "shape_exponent": 2.5,       // super-ellipse cross-sections (2 = ellipse, larger = boxier)
    "stations": [                // nose to tail; width/height 0 at the ends close the body
      {"x": 0.0, "width": 0.0, "height": 0.0, "z_center": 1.0},
      {"x": 1.2, "width": 1.15, "height": 1.3, "z_center": 1.15}, ...
    ]
  },
  "booms": [ {"y": 2.2, "z": 1.45, "x_start": -0.7, "x_end": 7.5, "diameter": 0.14, "mirror": true} ],
  "lift_rotors": [
    {"name": "LR1", "hub": [x, y, z],     // disk centre (rotor plane)
     "axis": [0, 0, 1],                   // thrust direction (tilt allowed)
     "diameter": 2.4, "blades": 2, "blade_chord": 0.14,
     "hub_diameter": 0.25, "hub_height": 0.15,   // motor + hub fairing (kept in hover and cruise)
     "spin": "ccw",                       // seen from above
     "stopped_azimuth_deg": 0.0,          // cruise: blade azimuth from +x (0 = aligned with the flow, lowest drag)
     "blade_pitch_deg": 8.0,              // optional
     "mast_thickness": 0.05, "mast_chord": 0.20,  // optional: faired pylon from the boom to the motor (default 0.05 x 0.20 m,
                                          // the sizing build-up value); built automatically when the hub is above a boom
     "thrust_hover_n": 1766.0}            // optional; default MTOW*g/n_rotors
  ],
  "pusher": {"hub": [5.3, 0.0, 1.42], "axis": [-1, 0, 0], "diameter": 1.5, "blades": 3,
             "spinner_diameter": 0.26, "blades_in_cfd": false},   // pusher modelled as an actuator disk in cruise
  "tail": {
    "horizontal": [ {"airfoil": "naca0012", "span": 4.4, "root_chord": 0.7, "tip_chord": 0.7,
                     "x_le_root": 6.65, "z_root": 2.4, "y_root": 0.0, "incidence_deg": 0.0, "mirror": true} ],
    "vertical":   [ {"airfoil": "naca0012", "x_le_root": 6.55, "y": 2.2, "z_root": 1.45, "height": 0.97,
                     "root_chord": 0.85, "tip_chord": 0.7, "sweep_le_deg": 8.0, "mirror": true} ]
  },
  "landing_gear": {
    "skids":  [ {"y": 0.75, "z": 0.08, "x_start": 0.7, "x_end": 3.7, "diameter": 0.06, "mirror": true} ],
    "struts": [ {"p1": [1.2, 0.75, 0.08], "p2": [1.2, 0.45, 0.75], "diameter": 0.05, "mirror": true} ],
    "cross_tube": {"faired": true},       // optional: struts become streamlined fairings (t/c 0.4) instead of round tubes
    "wheels": [ {"center": [x, y, z], "diameter": 0.35, "width": 0.1, "mirror": true} ]
  },
  "mass": {"mtow_kg": 720, "x_cg": 2.55, "z_cg": 1.25},
  "operating": {"cruise_speed_ms": 45.0,
                "hover_thrust_per_lift_rotor_n": 1766.0,
                "cruise_thrust_pusher_n": 900.0}       // optional; 0 = pusher off (clean polar)
}
```

Notes for the sizing and CAD packages:

* Components may intersect (wing through fuselage, booms through wing); the mesher removes interior parts. Gaps
  smaller than about 5 mm between parts should be closed (merge or separate them by > 2 cm), since they create
  very small cells.
* Battery packs, seats, spar positions and other internal items are not needed by the CFD.
* `operating` is optional; when absent the cruise speed comes from `selected_design.json` (`cruise_speed_ms`) and the
  hover thrust per rotor from MTOW.
* A worked example that meshes and runs is `cfd/examples/geometry_example.json` (an example only, not the design).

## Status

* Phase 1 (validation): complete, [validation/cfd/README.md](../validation/cfd/README.md).
* Phase 2, current frozen design (iteration 3.3, twin boom-tail pushers):
  [results/iteration33/README.md](results/iteration33/README.md) - cruise polar, clean CLmax and the 1.15 Vs check,
  pusher thrust deduction / inflow / shaft power, static margin and trim, hover download, mission check, and a GCI study
  of the cruise-point coefficients on three lifting-surface refinements.
* History: [results/README.md](results/README.md) (iteration 3.1), `results/iteration3/`, `results/pipeline_test_old_geometry/`.
  The iteration-3.2 runs were stopped when 3.3 was frozen and are not reported.
* The OML builds faired pylons from `mast_thickness`/`mast_chord`, faired gear legs when `landing_gear.faired` /
  `cross_tube.faired` is true, and pusher motor cans + spinners for every entry of `pushers` (one actuator disk per
  pusher, thrust shared equally); inverter pods are not modelled (build-up increment).
* Runs are resumable queues started in a memory-capped scope
  (`systemd-run --user --scope -p MemoryMax=20G -p MemorySwapMax=0 setsid nohup <queue>`); every step skips finished
  work and restarts interrupted cases from their last written iteration; `tools/watchdog.py` stops cases at
  force-coefficient convergence. Results pages: `tools/phase2_report.py` + `tools/results_md.py`.

## Modelling choices (justified in validation/cfd/README.md)

* k-omega SST, fully turbulent, steady (SIMPLEC). Points with a lift oscillation (CL_std > 0.01) are reported but
  not used in polar fits; steady RANS at and after stall is not reliable.
* 3-D surfaces use prism layers with a first-cell height for y+ about 30 (0.5 mm at 42 m/s) and Spalding wall
  functions; the 2-D wall-function study shows y+ 60-120 is not acceptable (early separation, drag error).
* Background-mesh faces are offset from the chord planes (castellation is otherwise asymmetric).
* Rotors in hover: actuator disks of the hover thrust, no swirl, radius-weighted loading (`linear`) by default; stopped
  blades are meshed as geometry in cruise.
* Incompressible (Mach < 0.2 in cruise; the 2-D validation is at M 0.15 data).
