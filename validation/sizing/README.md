# WP D verification and validation (sizing)

**Iteration 3 (current freeze: MTOW 1,043 kg, full 1.2 g flare).** Checker: 48 PASS, 10 WARN, 1 FAIL. The FAIL is again
the empty mass: 491 kg (regressions) vs 633 kg (CAD-calibrated), -22 %. The WARN rows are the same as in iteration 2
for the same reasons; the rows below were written for iteration 2. Own verification: **96 PASS, 0 FAIL**, including the
flare checks (A14) at 1.2 g, which pass in all loading cases (pilot + cargo: 56.3 kW / 249 N m of 60 / 250).
Iteration-2 reports: `sizing/results/iteration2/`.

## Iteration-2 record

| File | Content |
|---|---|
| [check_report_selected.md](check_report_selected.md) / `.json` | WP M's independent checker (`methods/check_design.py`) on the iteration-2 `design/selected_design.json` + `geometry.json` |
| [verify_sizing.py](verify_sizing.py) | our verification: unit tests (V), design audit (A), integration checks with the CAD audit definitions (G), calibration bookkeeping (C), benchmarks (B) |
| [verification_report.md](verification_report.md) / `.json` | its output: **96 PASS, 0 FAIL** |
| [benchmark_comparison.png](benchmark_comparison.png) | design against the benchmark trends of `methods/benchmarks/` |

Iteration-1 reports are archived in `sizing/results/iteration1/`.

```
~/tools/cadenv/bin/python methods/check_design.py --out validation/sizing --tag selected
~/tools/cadenv/bin/python validation/sizing/verify_sizing.py
```

## 1. Independent check (WP M): 48 PASS, 10 WARN, 1 FAIL

**Agreement.** All performance rows are within the PASS band:
- disk loading, figure of merit, hover power (site and ceiling), tip Mach;
- drag area, cruise drag, L/D, propeller efficiency, cruise power, stall speed;
- cell energy, pack mass, mission energy, rotor-out power;
- motor mass vs torque, cost.

All requirement limits pass:
- footprint;
- rotor-out power and torque at 500 m;
- motor continuous ratings, pusher, stall, gust, C-rates, one pack out, packs >= 2.

**Overrides passed to the checker** (unchanged from iteration 1, each with its reason in the file): composite factor
0.85, accessory factor from the catalog build-up, LV system 10 kg.

| Row | M | D | Status | Reasoning |
|---|---|---|---|---|
| **empty mass excl. battery** | 515 kg | 664 kg | **FAIL -22 %** | D's empty mass is calibrated to the iteration-1 CAD bottom-up masses (design/mass_calibration.json): CAD empty was +29 % over the regressions. M sums Raymer/NDARC regressions, which do not contain the 39.5 kg of rotor-station hardware (pylons, P3 plates, isolators, nacelles: breakdown key `rotor_pylons_mounts`, not compared by M), the 6.5 kg parachute installation, the damped gear or the 31.6 kg growth allowance (M has none). Without the growth allowance and the station hardware D's comparable sum is 593 kg (-13 %, WARN band). EQUATIONS.md asks for regressions to be replaced by CAD/catalog masses when available; the CAD masses are kept. |
| MTOW recomputed | 941 kg | 1,090 kg | WARN -14 % | consequence of the row above |
| fuselage | 47.5 | 66.3 | WARN -28 % | CAD calibration x 1.39 (canopy, shells, side panels, clevises) and a taller, boxier section (exponent 4.0) |
| tail | 7.9 | 10.6 | WARN -25 % | CAD calibration x 1.34 (clamps, hinges, spars) |
| parachute | 21.3 | 35.4 | WARN -40 % | sourced GRS 6 990-1190 (28.9 kg, above M's 600-1050 kg line) + 6.5 kg cradle/hard points (CAD) |
| pusher motor | 18.6 | 27.3 | WARN -32 % | catalog REB 90 23.8 kg (regression -23 % on this motor, see EQUATIONS [M8]) + 3.5 kg installation |
| pusher propeller | 1.9 | 3.6 | WARN -49 % | catalog DUC SWIRL 3-blade 1.73 m mass (3.63 kg) vs the helicopter-blade regression |
| seats | 33.9 | 22.7 | WARN +50 % | M uses Raymer's GA furnishings regression (scales with MTOW); D uses the CAD seats (2 crash-rated seats + furnishings) |
| wing, AFDD93 cross-check | 102 | 72.7 | WARN +41 % | helicopter/tilt-rotor wing regression without composite credit; the primary Raymer comparison passes |
| range | 26.5 km | 23.3 km | WARN +14 % | M uses a constant battery efficiency 0.95; D's I2R losses at end of life give 0.88 in hover (D conservative) |
| hover C-rate | 8.44 | 9.67 | WARN -13 % | same reason (D divides by the lower hover efficiency); D's value is the sizing constraint (limit 9.7) |

## 2. Own verification: 96 PASS, 0 FAIL ([verification_report.md](verification_report.md))

- **V1-V8 unit tests:**
  - ISA by hand calculation; momentum theory; disc/strip overlap area (closed form and Monte Carlo).
  - Rotor-out LP: 4/3 for 2 x 4 rotors, no trim for 4, >= 1.5 for 6.
  - Raymer masses, propeller efficiency, Oswald factor, Eastlake cost and gust load factor identical to WP M's code.
- **A1-A14 design audit:**
  - Mass closure and breakdown; the 38 mass items sum to MTOW and reproduce `cg_mtow_m`.
  - The FEA reader sees the same mass (0.006 kg unallocated). Its CG differs by 12 mm because it lumps structure at its
    own stations, while ours are the CAD-calibrated positions.
  - CG on the rotor centroid; footprint 9.00 x 8.6 m; rotor clearances.
  - Battery layout (159s <= 180s, 668 V <= 800 V, pack mass with 0.25 overhead, 3 packs).
  - Energy chain recomputed by hand.
  - Rotor-out LP re-run from geometry.json (53.7 kW, 229 N m).
  - Static margin 9.6-10.3 % and rotor-out within REB 60 limits in all three loading cases.
  - **A14: flare at 1.188 g within REB 60 peak power and torque** in all loading cases (pilot + cargo: 59.7 kW of 60).
  - MTOW below the GRS 6 990-1190 rating; cruise >= 1.3 Vs.
- **G1-G13 integration checks** (`sizing/geometry_checks.py`, the CAD audit's definitions: wing rotated by the incidence
  about the LE, PCHIP super-ellipse OML, P95 occupant with 15 deg recline, P2 pad 84 mm above the boom axis, 530 mm sill,
  40 mm posts, 3.2 mm canopy):

  | Check | Result |
  |---|---|
  | boom crown / saddle pads under the wing lower skin | +21 / +19 / +8 mm |
  | P95 head clearance, pilot / passenger | 107 / 62 mm |
  | passenger door | 0.494 x 0.699 m |
  | seat stroke | 160 mm |
  | packs inside the OML / cross tubes clear of the packs | 13 / 20 mm |
  | pusher strike angle / fin strike angle / pusher ground clearance | 11.5 deg / 16.1 deg / 0.35 m |
  | REB 90 inside the cowl | +24 mm |
  | parachute canister inside the OML | 0.13 m |
  | root fittings inside the OML | +8 mm |
  | exposed tail areas | 1.00 of sized |
  | blade plane over the wing / over the cabin | 0.41 / 0.36 m |
  | rotor-burst fan | 5.4 deg (>= 5.3) |
  | pusher-to-tail, boom and lift-rotor gaps | pass |
  | tip-over angles | 28.6 / 50.3 / 40.5 deg |
  | boom underside on the egress path (information) | 1.74 m < 1.9 m: WARN |

- **C1 calibration bookkeeping:** CAD empty (excl. growth) minus the 42.4 kg reductions = sum of the calibrated groups.
- **B benchmarks:** empty fraction incl. battery 0.82 (fit [W3] 0.75 +-0.08); payload fraction 0.18; hover power loading
  on the momentum trend [H8]; battery fraction 0.21 within the benchmark range.

The CAD model itself (WP G's `cad/audit.py`) has not been re-run on the iteration-2 geometry in this work package (it
writes outside `sizing/`, `design/`, `validation/sizing/`). The G-checks reproduce its definitions; the remaining
differences are its mesh-based occupant (C9) and the actual fitting parts.

## Open items

1. WP G rebuild and audit on the iteration-2 geometry (weight reductions, packs, cowl, raised wing, faired pylons).
2. WP F re-run: new MTOW and motors, spars at 0.20 / 0.70 c, root fittings at y 0.38 m, damper load case for the
   lighter P4 saddles, parachute 48.8 kN.
3. WP C: polar with the 5 deg nose-up fuselage, faired pylons, download.
4. Owner decision on range / flare requirement (sizing/README.md, status).
