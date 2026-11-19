# Independent design check - example_750kg

Design: **Hand-built test case: 750 kg lift + cruise, 8 x 1.7 m lift rotors, 200 kg payload**  
Input: `methods/examples/example_750kg_selected_design.json`  
Checker: `methods/check_design.py` (equations in `methods/EQUATIONS.md`; tags in the *eq* column).

Summary: **39 PASS, 7 WARN, 13 FAIL**, 0 informational (no D value), 0 missing.

M = this independent check, D = value reported in the design file. diff = (M - D)/D.

| status | quantity | M | D | diff | unit | tolerance | eq | note |
|---|---|---|---|---|---|---|---|---|
| PASS | wing span: geometry.json vs selected_design | 9.000 | 9.000 | +0.0% | m | ±1% warn / ±5% fail | - |  |
| PASS | wing area from geometry.json chords | 9.450 | 9.450 | +0.0% | m^2 | ±1% warn / ±5% fail | trapezoid |  |
| PASS | MTOW = empty (excl. battery) + battery + payload | 750.0 | 750.0 | +0.0% | kg | ±1% warn / ±5% fail | [M0] | bookkeeping closure of D's own numbers |
| PASS | wing span <= footprint limit | 9.000 | - | - | m | <= 9 | req. |  |
| PASS | overall length incl. booms and rotor discs <= footprint limit | 8.100 | - | - | m | <= 9 | req. |  |
| PASS | disk loading | 405.0 | 405.0 | +0.0% | N/m^2 | ±1% warn / ±5% fail | [H0] |  |
| PASS | figure of merit (M: blade-element estimate) | 0.737 | 0.750 | -1.7% | - | ±10% warn / ±20% fail | [H2]-[H3] |  |
| PASS | hover shaft power per motor, site (500 m ISA+15) | 17.6 | 18.5 | -4.8% | kW | ±10% warn / ±20% fail | [H1]-[H3] |  |
| PASS | hover electrical power total, site | 160.9 | 163.0 | -1.3% | kW | ±10% warn / ±20% fail | [H1]-[H3],[E1] |  |
| PASS | hover electrical power total, 1000 m ISA+15 ceiling | 163.5 | 170.0 | -3.8% | kW | ±10% warn / ±20% fail | [H1]-[H3],[E1] |  |
| PASS | hover shaft power per motor at 1000 m ISA+15 <= motor continuous | 17.9 | - | - | kW | <= 30 | [H1] |  |
| PASS | lift-rotor hover tip Mach (ISA+15) | 0.432 | 0.430 | +0.5% | - | ±3% warn / ±8% fail | [H7] |  |
| PASS | lift-rotor tip Mach (noise screen) | 0.432 | - | - | - | <= 0.55 | [H7] | NASA UAM concepts use 550-600 ft/s (Mtip ~0.49-0.54) |
| PASS | hover blade loading CT/sigma (stall margin for transition) | 0.131 | - | - | - | <= 0.14 | [H5] |  |
| WARN | rotor-out shaft power, most loaded motor (incl. 10 % thrust control margin) | 34.6 | 30.0 | +15.2% | kW | ±10% warn / ±20% fail | [H6] |  |
| PASS | rotor-out power <= motor peak power | 34.6 | - | - | kW | <= 45 | [H6] req. |  |
| PASS | rotor-out torque <= motor max torque | 153.3 | - | - | N m | <= 220 | [H6] |  |
| PASS | Oswald efficiency | 0.795 | 0.800 | -0.7% | - | ±15% warn / ±30% fail | [I2] |  |
| FAIL | zero-lift drag area D/q | 0.490 | 0.300 | +63.4% | m^2 | ±15% warn / ±30% fail | [D1]-[D9] |  |
| PASS | cruise drag | 781.0 | 820.0 | -4.8% | N | ±15% warn / ±30% fail | [I1] |  |
| PASS | cruise L/D | 9.418 | 9.000 | +4.6% | - | ±15% warn / ±30% fail | [I1] |  |
| PASS | pusher propulsive efficiency | 0.832 | 0.820 | +1.4% | - | ±10% warn / ±20% fail | [P1]-[P2] |  |
| PASS | cruise electrical power | 48.7 | 48.0 | +1.5% | kW | ±10% warn / ±20% fail | [E1] |  |
| WARN | cruise shaft power <= pusher motor continuous | 41.7 | - | - | kW | <= 40 | [E1] |  |
| PASS | pusher helical tip Mach in cruise | 0.570 | - | - | - | <= 0.7 | [H7] |  |
| PASS | stall speed (sea level ISA, MTOW) | 29.1 | 29.5 | -1.3% | m/s | ±3% warn / ±8% fail | [S1] |  |
| PASS | cruise speed >= 1.3 x stall (TAS at cruise altitude) | 1.453 | - | - | - | >= 1.3 | [S2] |  |
| PASS | cruise speed >= requirement | 160 | - | - | km/h | >= 150 | req. |  |
| PASS | gust load factor at VC (Ude 15.24 m/s) <= design limit | 2.797 | - | - | g | <= 3.8 | [L3] |  |
| PASS | nominal energy from cells (series x parallel x cell Wh) | 41.6 | 41.6 | -0.0% | kWh | ±1% warn / ±5% fail | [B1] |  |
| PASS | battery pack mass (cells / (1 - overhead)) | 234.3 | 230.0 | +1.9% | kg | ±10% warn / ±20% fail | [B2] | overhead fraction 0.30 |
| PASS | mission energy (design range, at battery terminals / eta_batt) | 40.9 | 40.0 | +2.4% | kWh | ±10% warn / ±20% fail | [E2]-[E4] |  |
| FAIL | range to 20 % reserve at EOL capacity | 55.3 | 101.0 | -45.3% | km | ±10% warn / ±20% fail | [R1] |  |
| FAIL | range at EOL with 20 % reserve >= design range | 55.3 | - | - | km | >= 100 | [R1] |  |
| FAIL | nominal battery energy >= required (EOL, reserve) | 41.6 | - | - | kWh | >= 60.78 | [B3] |  |
| WARN | hover C-rate at EOL capacity (ceiling) | 5.172 | 4.500 | +14.9% | 1/h | ±10% warn / ±20% fail | [B4] |  |
| PASS | hover C-rate <= cell continuous rating - 0.3 C margin | 5.172 | - | - | 1/h | <= 9.7 | [B4] req. |  |
| PASS | rotor-out C-rate <= cell peak rating | 5.065 | - | - | 1/h | <= 15 | [B4] |  |
| PASS | independent battery packs/buses | 2 | - | - | - | >= 2 | req. |  |
| PASS | C-rate with one pack failed (hover landing) <= cell peak rating | 10.3 | - | - | 1/h | <= 15 | [B4] |  |
| PASS | lift motor mass each (catalog) vs NDARC torque regression | 10.3 | 9.000 | +14.7% | kg | ±25% warn / ±50% fail | [M8] |  |
| FAIL | inverters + HV harness (vs NASA 0.63 x motor accessory factor) | 60.8 | 32.0 | +90.0% | kg | ±25% warn / ±50% fail | [M16] |  |
| WARN | wing mass | 77.7 | 55.0 | +41.3% | kg | ±25% warn / ±50% fail | [M1] |  |
| PASS | fuselage mass | 53.1 | 45.0 | +17.9% | kg | ±25% warn / ±50% fail | [M5] |  |
| FAIL | landing gear mass | 27.8 | 15.0 | +85.3% | kg | ±25% warn / ±50% fail | [M6] |  |
| FAIL | booms mass | 35.7 | 22.0 | +62.4% | kg | ±25% warn / ±50% fail | [M10] |  |
| PASS | lift motors mass | 82.6 | 72.0 | +14.7% | kg | ±25% warn / ±50% fail | [M8] |  |
| PASS | lift rotors mass | 18.6 | 16.0 | +16.4% | kg | ±25% warn / ±50% fail | [M9] |  |
| PASS | parachute mass | 14.3 | 15.0 | -4.8% | kg | ±25% warn / ±50% fail | [M15] |  |
| WARN | tail (H + V) mass | 17.0 | 12.0 | +41.3% | kg | ±25% warn / ±50% fail | [M3]-[M4] |  |
| FAIL | pusher motor mass | 13.9 | 9.000 | +54.4% | kg | ±25% warn / ±50% fail | [M8] |  |
| FAIL | pusher propeller mass | 1.251 | 4.000 | -68.7% | kg | ±25% warn / ±50% fail | [M9] |  |
| WARN | seats mass | 16.0 | 12.0 | +33.3% | kg | ±25% warn / ±50% fail | [M11] |  |
| FAIL | avionics mass | 17.2 | 10.0 | +72.1% | kg | ±25% warn / ±50% fail | [M12] |  |
| FAIL | lv electrical mass | 36.4 | 6.000 | +507.0% | kg | ±25% warn / ±50% fail | [M13] |  |
| WARN | wing mass, NDARC AFDD93 cross-check | 78.6 | 55.0 | +42.9% | kg | ±25% warn / ±50% fail | [M2] |  |
| FAIL | empty mass excluding battery | 477.9 | 320.0 | +49.3% | kg | ±10% warn / ±20% fail | [M0] | M sums its own component estimates; D's growth allowance excluded from both |
| FAIL | MTOW recomputed (M empty + D battery + payload) | 907.9 | 750.0 | +21.0% | kg | ±10% warn / ±20% fail | [M0] |  |
| PASS | acquisition cost per aircraft (Eastlake airframe + COTS propulsion/systems) | 2.95e+05 | 320000 | -7.7% | USD | ±30% warn / ±60% fail | [C1]-[C9] | recurring airframe (Eastlake hours x rate + materials) + D's COTS propulsion/systems total |

## Key recomputed values

- Disk loading 405 N/m^2; hover FM (M) 0.737; hover electrical 160.9 kW at the site, 163.5 kW at the ceiling.
- Cruise: CL 0.711, CD0 0.0519, L/D 9.42, drag 781 N, propeller eta 0.832, electrical 48.7 kW.
- Mission energy 40.95 kWh (hover 5.69, transitions 1.84, climb 1.37, cruise 32.04); nominal energy required 60.8 kWh; range 55.3 km.
- C-rates at EOL: hover (site) 5.09, hover (ceiling) 5.17, cruise 1.54, rotor-out (approx.) 5.07.
- Gust load factor at VC 2.80 g; wing loading 778 N/m^2.
- Empty mass excluding battery (M) 477.9 kg; MTOW (M) 907.9 kg.

### Drag-area build-up (m^2)

| item | D/q |
|---|---|
| wing | 0.0719 |
| fuselage | 0.0880 |
| booms | 0.0189 |
| tail_h | 0.0249 |
| tail_v | 0.0137 |
| stopped_lift_rotors | 0.1780 |
| landing_gear | 0.0500 |
| other_listed | 0.0000 |
| excrescence_interference | 0.0446 |
| total | 0.4901 |
| swet_wing_m2 | 16.8911 |
| swet_fuselage_m2 | 15.5000 |

### Component mass estimates (kg)

| item | kg |
|---|---|
| wing | 77.7 |
| tail_horizontal | 9.5 |
| tail_vertical | 7.4 |
| fuselage | 53.1 |
| landing_gear | 27.8 |
| flight_controls | 5.6 |
| booms_and_fittings | 35.7 |
| lift_motors | 82.6 |
| pusher_motor | 13.9 |
| lift_rotors_blades_hubs | 18.6 |
| pusher_propeller | 1.3 |
| inverters_cooling_accessories | 60.8 |
| parachute | 14.3 |
| avionics_installed | 17.2 |
| electrical_lv | 36.4 |
| furnishings_seats | 16.0 |

### Assumptions used by the checker

```json
{
 "kappa_induced": 1.2,
 "cd0_blade": 0.015,
 "coax_factor": 1.0,
 "download_fraction": 0.03,
 "control_thrust_margin": 0.1,
 "eta_motor": 0.93,
 "eta_inverter": 0.97,
 "eta_wiring": 0.98,
 "eta_battery": 0.95,
 "aux_power_kw": 1.5,
 "battery_eol_fraction": 0.8,
 "reserve_fraction": 0.2,
 "c_rate_margin": 0.3,
 "pack_overhead_fraction": 0.3,
 "laminar_fraction_wing": 0.1,
 "laminar_fraction_body": 0.05,
 "excrescence_factor": 1.1,
 "cl_max_default": 1.4,
 "prop_profile_factor": 0.9,
 "eta_prop_cap": 0.86,
 "climb_rate_ms": 2.5,
 "cruise_alt_m": 500.0,
 "takeoff_alt_m": 0.0,
 "gust_ude_ms": 15.24,
 "transition_power_rule": "mean",
 "tech_factor_structure": 1.0,
 "tech_factor_rotor": 1.0,
 "flap_frequency": 1.1,
 "parachute_points": [
  [
   600.0,
   12.3
  ],
  [
   750.0,
   14.8
  ],
  [
   1050.0,
   21.7
  ],
  [
   757.0,
   12.4
  ],
  [
   950.0,
   17.6
  ]
 ],
 "cfrp_allowable_mpa": 300.0,
 "cfrp_density": 1550.0,
 "boom_fitting_factor": 1.6,
 "copper_density": 8960.0,
 "hv_current_density_a_mm2": 5.0,
 "harness_overhead": 1.4,
 "seat_mass_kg": 8.0,
 "accessory_factor": 0.63,
 "lv_electrical_kg": null
}
```
