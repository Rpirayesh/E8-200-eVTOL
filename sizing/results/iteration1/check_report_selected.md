# Independent design check - selected

Design: **E8-200 selected design: 8 x 1.75 m lift rotors (MOT-REB50), CELL-P50B 166s9p x 2 packs, 8.8 m wing, 150 km/h**  
Input: `design/selected_design.json`  
Checker: `methods/check_design.py` (equations in `methods/EQUATIONS.md`; tags in the *eq* column).

Summary: **55 PASS, 4 WARN, 0 FAIL**, 0 informational (no D value), 0 missing.

M = this independent check, D = value reported in the design file. diff = (M - D)/D.

| status | quantity | M | D | diff | unit | tolerance | eq | note |
|---|---|---|---|---|---|---|---|---|
| PASS | wing span: geometry.json vs selected_design | 8.800 | 8.800 | +0.0% | m | ±1% warn / ±5% fail | - |  |
| PASS | wing area from geometry.json chords | 10.6 | 10.6 | +0.0% | m^2 | ±1% warn / ±5% fail | trapezoid |  |
| PASS | MTOW = empty (excl. battery) + battery + payload | 1001.7 | 1001.7 | -0.0% | kg | ±1% warn / ±5% fail | [M0] | bookkeeping closure of D's own numbers |
| PASS | wing span <= footprint limit | 8.800 | - | - | m | <= 9 | req. |  |
| PASS | overall length incl. booms and rotor discs <= footprint limit | 8.420 | - | - | m | <= 9 | req. |  |
| PASS | disk loading | 510.5 | 510.5 | -0.0% | N/m^2 | ±1% warn / ±5% fail | [H0] |  |
| PASS | figure of merit (M: blade-element estimate) | 0.718 | 0.719 | -0.0% | - | ±10% warn / ±20% fail | [H2]-[H3] |  |
| PASS | hover shaft power per motor, site (500 m ISA+15) | 27.1 | 27.1 | +0.0% | kW | ±10% warn / ±20% fail | [H1]-[H3] |  |
| PASS | hover electrical power total, site | 246.9 | 246.9 | +0.0% | kW | ±10% warn / ±20% fail | [H1]-[H3],[E1] |  |
| PASS | hover electrical power total, 1000 m ISA+15 ceiling | 250.6 | 250.6 | +0.0% | kW | ±10% warn / ±20% fail | [H1]-[H3],[E1] |  |
| PASS | hover shaft power per motor at 1000 m ISA+15 <= motor continuous | 27.5 | - | - | kW | <= 30 | [H1] |  |
| PASS | lift-rotor hover tip Mach (ISA+15) | 0.518 | 0.518 | -0.0% | - | ±3% warn / ±8% fail | [H7] |  |
| PASS | lift-rotor tip Mach (noise screen) | 0.518 | - | - | - | <= 0.55 | [H7] | NASA UAM concepts use 550-600 ft/s (Mtip ~0.49-0.54) |
| PASS | hover blade loading CT/sigma (stall margin for transition) | 0.114 | - | - | - | <= 0.14 | [H5] |  |
| PASS | rotor-out shaft power, most loaded motor (incl. 10 % thrust control margin) | 45.3 | 48.9 | -7.4% | kW | ±10% warn / ±20% fail | [H6] |  |
| PASS | rotor-out power <= motor peak power | 45.3 | - | - | kW | <= 50 | [H6] req. |  |
| PASS | rotor-out torque <= motor max torque | 181.7 | - | - | N m | <= 200 | [H6] |  |
| PASS | Oswald efficiency | 0.830 | 0.830 | +0.0% | - | ±15% warn / ±30% fail | [I2] |  |
| PASS | zero-lift drag area D/q | 0.510 | 0.510 | +0.1% | m^2 | ±15% warn / ±30% fail | [D1]-[D9] |  |
| PASS | cruise drag | 987.6 | 987.3 | +0.0% | N | ±15% warn / ±30% fail | [I1] |  |
| PASS | cruise L/D | 9.946 | 9.949 | -0.0% | - | ±15% warn / ±30% fail | [I1] |  |
| PASS | pusher propulsive efficiency | 0.824 | 0.824 | -0.0% | - | ±10% warn / ±20% fail | [P1]-[P2] |  |
| PASS | cruise electrical power | 58.0 | 58.0 | +0.0% | kW | ±10% warn / ±20% fail | [E1] |  |
| PASS | cruise shaft power <= pusher motor continuous | 49.9 | - | - | kW | <= 60 | [E1] |  |
| PASS | pusher helical tip Mach in cruise | 0.560 | - | - | - | <= 0.7 | [H7] |  |
| PASS | stall speed (sea level ISA, MTOW) | 30.4 | 30.4 | +0.0% | m/s | ±3% warn / ±8% fail | [S1] |  |
| PASS | cruise speed >= 1.3 x stall (TAS at cruise altitude) | 1.302 | - | - | - | >= 1.3 | [S2] |  |
| PASS | cruise speed >= requirement | 150.0 | - | - | km/h | >= 150 | req. |  |
| PASS | gust load factor at VC (Ude 15.24 m/s) <= design limit | 2.380 | - | - | g | <= 3.8 | [L3] |  |
| PASS | nominal energy from cells (series x parallel x cell Wh) | 53.8 | 53.8 | +0.0% | kWh | ±1% warn / ±5% fail | [B1] |  |
| PASS | battery pack mass (cells / (1 - overhead)) | 303.1 | 303.1 | -0.0% | kg | ±10% warn / ±20% fail | [B2] | overhead fraction 0.30 |
| PASS | mission energy (design range, at battery terminals / eta_batt) | 33.6 | 34.4 | -2.3% | kWh | ±10% warn / ±20% fail | [E2]-[E4] |  |
| PASS | range to 20 % reserve at EOL capacity | 52.0 | 50.1 | +3.9% | km | ±10% warn / ±20% fail | [R1] |  |
| PASS | range at EOL with 20 % reserve >= design range | 52.0 | - | - | km | >= 50 | [R1] |  |
| PASS | nominal battery energy >= required (EOL, reserve) | 53.8 | - | - | kWh | >= 49.8861 | [B3] |  |
| PASS | hover C-rate at EOL capacity (ceiling) | 6.130 | 6.649 | -7.8% | 1/h | ±10% warn / ±20% fail | [B4] |  |
| PASS | hover C-rate <= cell continuous rating - 0.3 C margin | 6.130 | - | - | 1/h | <= 9.7 | [B4] req. |  |
| PASS | rotor-out C-rate <= cell peak rating | 5.792 | - | - | 1/h | <= 15 | [B4] |  |
| PASS | independent battery packs/buses | 2 | - | - | - | >= 2 | req. |  |
| PASS | C-rate with one pack failed (hover landing) <= cell peak rating | 12.3 | - | - | 1/h | <= 15 | [B4] |  |
| PASS | lift motor mass each (catalog) vs NDARC torque regression | 12.0 | 12.0 | -0.4% | kg | ±25% warn / ±50% fail | [M8] |  |
| PASS | inverters + HV harness (vs NASA 0.63 x motor accessory factor) | 60.6 | 63.9 | -5.0% | kg | ±25% warn / ±50% fail | [M16] |  |
| PASS | wing mass | 73.7 | 73.7 | +0.0% | kg | ±25% warn / ±50% fail | [M1] |  |
| PASS | fuselage mass | 39.7 | 39.7 | -0.0% | kg | ±25% warn / ±50% fail | [M5] |  |
| WARN | landing gear mass | 37.1 | 27.0 | +37.5% | kg | ±25% warn / ±50% fail | [M6] |  |
| WARN | booms mass | 44.2 | 33.8 | +30.8% | kg | ±25% warn / ±50% fail | [M10] |  |
| PASS | lift motors mass | 95.6 | 96.0 | -0.4% | kg | ±25% warn / ±50% fail | [M8] |  |
| PASS | lift rotors mass | 24.1 | 28.8 | -16.1% | kg | ±25% warn / ±50% fail | [M9] |  |
| PASS | parachute mass | 19.5 | 21.7 | -10.1% | kg | ±25% warn / ±50% fail | [M15] |  |
| PASS | tail (H + V) mass | 8.281 | 8.281 | -0.0% | kg | ±25% warn / ±50% fail | [M3]-[M4] |  |
| PASS | pusher motor mass | 18.2 | 23.8 | -23.7% | kg | ±25% warn / ±50% fail | [M8] |  |
| WARN | pusher propeller mass | 2.451 | 4.583 | -46.5% | kg | ±25% warn / ±50% fail | [M9] |  |
| PASS | seats mass | 28.8 | 24.0 | +20.1% | kg | ±25% warn / ±50% fail | [M11] |  |
| PASS | avionics mass | 10.7 | 10.7 | -0.0% | kg | ±25% warn / ±50% fail | [M12] |  |
| PASS | lv electrical mass | 10.0 | 10.0 | +0.0% | kg | ±25% warn / ±50% fail | [M13] |  |
| WARN | wing mass, NDARC AFDD93 cross-check | 95.6 | 73.7 | +29.7% | kg | ±25% warn / ±50% fail | [M2] |  |
| PASS | empty mass excluding battery | 479.7 | 498.6 | -3.8% | kg | ±10% warn / ±20% fail | [M0] | D's breakdown contains a growth allowance; M has none |
| PASS | MTOW recomputed (M empty + D battery + payload) | 982.8 | 1001.7 | -1.9% | kg | ±10% warn / ±20% fail | [M0] |  |
| PASS | acquisition cost per aircraft (Eastlake airframe + COTS propulsion/systems) | 3.96e+05 | 386812 | +2.3% | USD | ±30% warn / ±60% fail | [C1]-[C9] | recurring airframe (Eastlake hours x rate + materials) + D's COTS propulsion/systems total |

## Key recomputed values

- Disk loading 510 N/m^2; hover FM (M) 0.718; hover electrical 246.9 kW at the site, 250.6 kW at the ceiling.
- Cruise: CL 0.966, CD0 0.0483, L/D 9.95, drag 988 N, propeller eta 0.824, electrical 58.0 kW.
- Mission energy 33.61 kWh (hover 8.73, transitions 2.67, climb 1.85, cruise 20.35); nominal energy required 49.9 kWh; range 52.0 km.
- C-rates at EOL: hover (site) 6.04, hover (ceiling) 6.13, cruise 1.42, rotor-out (approx.) 5.79.
- Gust load factor at VC 2.38 g; wing loading 930 N/m^2.
- Empty mass excluding battery (M) 479.7 kg; MTOW (M) 982.8 kg.

### Drag-area build-up (m^2)

| item | D/q |
|---|---|
| wing | 0.0813 |
| fuselage | 0.0678 |
| booms | 0.0182 |
| tail_h | 0.0139 |
| tail_v | 0.0081 |
| stopped_lift_rotors | 0.1632 |
| landing_gear | 0.1012 |
| other_listed | 0.0100 |
| excrescence_interference | 0.0464 |
| total | 0.5100 |
| swet_wing_m2 | 19.6781 |
| swet_fuselage_m2 | 13.6610 |

### Component mass estimates (kg)

| item | kg |
|---|---|
| wing | 73.7 |
| tail_horizontal | 4.7 |
| tail_vertical | 3.6 |
| fuselage | 39.7 |
| landing_gear | 37.1 |
| flight_controls | 6.7 |
| booms_and_fittings | 44.2 |
| lift_motors | 95.6 |
| pusher_motor | 18.2 |
| lift_rotors_blades_hubs | 24.1 |
| pusher_propeller | 2.5 |
| inverters_cooling_accessories | 60.6 |
| parachute | 19.5 |
| avionics_installed | 10.7 |
| electrical_lv | 10.0 |
| furnishings_seats | 28.8 |

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
 "tech_factor_structure": 0.85,
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
 "accessory_factor": 0.533,
 "lv_electrical_kg": 10.0,
 "_reasons": {
  "tech_factor_structure": "foam-core / wet-laid carbon sandwich structure; Raymer table 15.4 composite factor 0.85 (the WP M 'light' scenario uses the same value)",
  "accessory_factor": "inverters from the catalog (MGM HBCi, 1 per motor), HV harness from [M14] physics, cooling build-up; replaces the NASA 1.63 technology factor",
  "lv_electrical_kg": "COTS build-up (2 x 600 W DC-DC, 24 V LiFePO4, LV harness, panel, lights) instead of the Raymer GA electrical-system regression"
 }
}
```
