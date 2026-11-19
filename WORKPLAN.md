# E8-200 work plan

Requirements: [requirements/requirements.yaml](requirements/requirements.yaml).

## Work packages and folders

| WP | Scope | Writes to | Main outputs |
|---|---|---|---|
| R | Literature and reference sources | `resources/` | `resources/README.md` (every source: link, what it is, what we used it for), `resources/sources.json` |
| M | Equations, benchmark aircraft data, independent design checks | `methods/` | `methods/EQUATIONS.md`, `methods/benchmarks/*.csv`, `methods/check_design.py` |
| P | Parts, materials, bill of materials, manufacturing | `bom/`, `manufacturing/` | `bom/catalog.json` (COTS options), `bom/BOM.csv`, `manufacturing/MANUFACTURING.md` |
| D | Sizing and optimisation | `sizing/`, `design/` | `design/selected_design.json`, `design/geometry.json`, `sizing/*` |
| C | CFD | `cfd/` | `cfd/results/*.json`, `cfd/README.md` |
| F | Structures (FEA) | `fea/` | `fea/results/*.json`, `fea/README.md` |
| G | 3-D model and assembly | `cad/` | `cad/parts/<ID>/<ID>.step/.stl`, `cad/assembly/*.step`, `docs/models/*.glb`, `cad/parts.json` |
| V | Independent verification and validation | `validation/README.md` and `validation/independent/` | V&V matrix with pass/fail and open items |

Every WP also puts its own verification and validation evidence (code-vs-reference comparisons, mesh/grid studies,
unit tests) under `validation/<wp-name>/` (`validation/cfd/`, `validation/fea/`, `validation/sizing/`, ...), so that one folder
holds all V&V.

## Interfaces

- `design/selected_design.json` – frozen design: masses, rotors, wing, battery, mission results.
- `design/geometry.json` – coordinates (m, x aft from the nose, y right, z up) of every major item: wing (root/tip chord, span,
  sweep, dihedral, incidence, airfoil, spar locations), booms, rotor hubs and diameters, fuselage stations, tail, pusher,
  landing gear, battery packs, seats. CFD, FEA and CAD all build from this file.
- `bom/catalog.json` – COTS component options with mass, rating, price and source link.

## Tools

- `~/tools/envs/cfd` (micromamba): OpenFOAM v2412 (`source ~/tools/foamenv.sh`), CalculiX 2.23, gmsh.
- `~/tools/cadenv/bin/python`: build123d, trimesh, aerosandbox, neuralfoil, numpy/scipy/matplotlib.
- Machine: 20 cores, 30 GB RAM; CFD may use up to 12 cores, FEA up to 6.

The tooling of the subscale build (`../E8-eVTOL-Build/tools/`) may be reused: CFD O-grid and full-aircraft OpenFOAM set-up,
frame FEM with inertia relief, CalculiX part analysis, build123d part library, GLB export and three.js viewer.
