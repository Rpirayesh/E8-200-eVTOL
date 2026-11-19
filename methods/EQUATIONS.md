# E8-200 conceptual-design equations (work package M)

This file is the reference equation set for the E8-200 lift + cruise eVTOL (200 kg payload, crewed). Every equation
has a tag (`[A1]`, `[H3]`, ...). The same tags appear in the independent checker `methods/check_design.py`, in its
reports (`validation/methods/check_report_*.md`) and in the first-order estimate `methods/initial_estimate.py`.
Sizing (WP D) may use other methods; this set is what WP M uses to verify D's numbers.

Units are SI unless stated. Regressions published in US units are written in their original units (lb, ft, kt, lb/ft²)
and converted at the boundary in the code (1 lb = 0.45359237 kg, 1 ft = 0.3048 m, 1 hp = 745.7 W, 1 kt = 0.514444 m/s).

## References

| Key | Reference | Where to get it |
|---|---|---|
| RAY | D. P. Raymer, *Aircraft Design: A Conceptual Approach*, AIAA Education Series, 6th ed. 2018 (ISBN 978-1-62410-490-9). Equation numbers below are those of the 5th/6th editions; chapter 12 aerodynamics, chapter 15 weights | https://search.worldcat.org/title/1048659355 |
| GUD | S. Gudmundsson, *General Aviation Aircraft Design: Applied Methods and Procedures*, Butterworth-Heinemann/Elsevier 2014 (ISBN 978-0-12-397308-5), ch. 2 "Aircraft Cost Analysis" (Eastlake model), ch. 6 weights, ch. 15-16 drag | https://shop.elsevier.com/books/general-aviation-aircraft-design/gudmundsson/978-0-12-397308-5 ; chapter 2: https://www.oreilly.com/library/view/general-aviation-aircraft/9780123973085/xhtml/CHP002.html |
| NDARC | W. Johnson, *NDARC - NASA Design and Analysis of Rotorcraft*, NASA/TP-2009-215402 (theory, rev. with appendices); ch. 19 "AFDD Weight Models" (pp. 167-175 of the appendix volume) | https://rotorcraft.arc.nasa.gov/Publications/files/NASA%20TP-2009-215402-app3.pdf |
| S18 | C. Silva, W. Johnson, K. Antcliff, M. Patterson, "VTOL Urban Air Mobility Concept Vehicles for Technology Development", AIAA 2018-3847 (doi 10.2514/6.2018-3847): eq. (1) motor mass, eq. (3) hover C-rate, Table 1 mission, Table 3 vehicles, sec. VI technology | https://www.nasa.gov/wp-content/uploads/2026/03/silva2018.pdf |
| JS22 | W. Johnson, C. Silva, "NASA concept vehicles and the engineering of advanced air mobility aircraft", *The Aeronautical Journal* 126 (2022), Table 3, secs. 6.3-6.7 | https://ntrs.nasa.gov/api/citations/20210026170/downloads/1521_Johnson%20%26%20Silva_122721%20.pdf |
| LEI | J. G. Leishman, *Principles of Helicopter Aerodynamics*, 2nd ed., Cambridge University Press 2006 (ISBN 978-0-521-85860-1): ch. 2 momentum theory (hover, figure of merit, coaxial rotors), ch. 3 blade-element theory | ISBN |
| MCC | B. W. McCormick, *Aerodynamics, Aeronautics, and Flight Mechanics*, 2nd ed., Wiley 1995 (ISBN 0-471-57506-2), ch. 6 propellers (actuator disc) | ISBN |
| HOE | S. F. Hoerner, *Fluid-Dynamic Drag*, 1965 (self-published): ch. 3 (bluff bodies, cylinders), ch. 6 (fuselages) | ISBN 978-9991194448 |
| CS23 | EASA CS-23 Amendment 4 (2015): CS 23.333 flight envelope, 23.335 design airspeeds, 23.337 limit manoeuvring load factors, 23.341 gust load factors. Amendment 5 moved these to AMC / ASTM F3116 with the same method. Pre-2017 14 CFR 23.333-23.341 is identical | https://www.easa.europa.eu/en/document-library/certification-specifications/cs-23-amendment-4 |
| ISA | ICAO Doc 7488, *Manual of the ICAO Standard Atmosphere* | ICAO |
| GRS | Galaxy GRS 6 ballistic rescue systems, manufacturer pages (600 SD: 12.3 kg / 600 kg; 750 SDS: 14.8 kg; 800-990 SDS: 21.7 kg / to 1050 kg) | https://galaxysky.cz/grs-6-600-sd-speedy-ff-115-m2-p22-en ; https://galaxysky.cz/grs-6-800-990-sds-175m2-p43-en ; https://galaxysky.cz/grs-6-750-sds-ff-140m2-p42-en |
| MAG | Magnum 601 SP (12.4 kg, 757 kg) and 901 SP (17.6 kg, 950 kg), dealer data in `bom/catalog.json` | https://uflyit.com/Magnum%20Parachutes%202.htm |
| CAT | WP P COTS catalog `bom/catalog.json` (motors, inverters, cells, parachutes; every value carries its own link) | ../bom/CATALOG.md |
| BEN | WP M benchmark data `methods/benchmarks/benchmarks.csv` (one source URL per value) | benchmarks/README.md |

Where a reference is a book without a stable public URL, the ISBN is given; WP R records the library/online copies in
`resources/`.

---

## 0. Default assumptions used by the checker

Every value can be overridden per design in the input block `assumptions_for_checker` (see `design_schema.md`).

| Symbol | Default | Meaning | Basis |
|---|---|---|---|
| kappa | 1.20 | induced-power factor in hover | LEI ch. 3: 1.15 for ideal twist, higher for fixed-pitch, low-twist blades; WP M choice |
| c_d0 | 0.015 | mean blade profile drag coefficient | LEI ch. 3 (0.008-0.012 for helicopter blades at high Re); raised for Re ~ 0.5-1e6 composite propeller blades |
| f_DL | 0.03 | hover download / weight | estimate for a high wing partly under the discs; WP C to replace |
| k_ctrl | 0.10 | thrust margin above trim on the most loaded rotor in rotor-out | estimate; JS22 sec. 6.7 reports P_max/P_hover = 2.15 for the NASA lift+cruise handling-qualities design (much larger, for gust rejection) |
| eta_m, eta_inv, eta_w | 0.93, 0.97, 0.98 | motor, inverter, wiring efficiency | estimate; motor catalog peaks 0.93-0.96 (CAT) |
| eta_b | 0.95 | battery discharge efficiency (I²R) | estimate for P50B class at 2-6C (12.8 mOhm/cell, CAT) |
| f_EOL | 0.80 | end-of-life capacity fraction | requirement |
| f_res | 0.20 | energy remaining at landing (fraction of EOL capacity) | requirement |
| dC | 0.3 C | C-rate margin below the cell rating | requirement ("0.3 C margin"); interpretation: demanded C-rate at EOL <= cell continuous rating - 0.3 C. Open item for the requirements owner |
| f_ovh | 0.30 | non-cell mass fraction of a battery pack | S18 sec. VI A (30 % for BMS and pack structure); CAT reference: Pipistrel Velis pack ~177 Wh/kg on 253 Wh/kg cells = 0.30 |
| k_exc | 1.10 | excrescence/interference multiplier on the drag build-up | RAY sec. 12.5.7 (leakage and protuberance 2-5 % for clean aircraft; eVTOL fittings, gaps, sensors -> 10 %) |
| eta_p/eta_i | 0.90 | propeller efficiency relative to actuator-disc ideal | MCC ch. 6 (good propellers reach 85-90 % of ideal) |
| U_de | 15.24 m/s | derived gust velocity at V_C (50 ft/s) | CS23 23.333(c) |
| tech factor | 1.0 | Raymer GA structure regressions without composite credit (wet lay-up) | RAY table 15.4 gives 0.85-0.90 for advanced composites; not taken for wet lay-up in the conservative case |

---

## 1. Atmosphere

[A1] Temperature with offset: `T = 288.15 - 0.0065 h + dT` (K), `h` geopotential altitude (m), valid 0-11 km.

[A2] Pressure from the standard day: `p = 101325 (1 - 0.0065 h / 288.15)^5.25588` (Pa). Density `rho = p / (287.053 T)`.

[A3] Speed of sound `a = sqrt(1.4 * 287.053 * T)`; viscosity (Sutherland) `mu = 1.458e-6 T^1.5 / (T + 110.4)`.

Design points (requirements): hover sizing at 500 m and at the 1000 m ceiling, both ISA + 15 °C
(`rho` = 1.123 and 1.065 kg/m³); cruise at 500 m ISA + 15 °C. Source: ISA.

---

## 2. Mass fractions and empty-mass regressions

[W1] Closure: `m_TO = m_payload + m_empty,xb + m_battery` (m_empty,xb = empty mass excluding battery).
Written as `m_TO = m_payload / (1 - f_e,xb - f_b)` this shows the snowball: with `f_e,xb ~ 0.50` (benchmarks) and
`f_b ~ 0.30-0.45`, the payload fraction is 0.05-0.20.

[W2] Historical empty-weight fraction (RAY eq. 3.1, table 3.1): `We/W0 = A W0^C` (W0 in lb), e.g. general-aviation
single engine A = 2.36, C = -0.18; homebuilt composite A = 1.15, C = -0.09. Valid for conventional aircraft only: these
do not contain batteries or lift systems and are not used for E8-200 sizing, only to show the gap.

[W3] eVTOL benchmark fit (this work, `benchmarks/trend_fits.json`, n = 12 aircraft with published empty mass and
MTOW, empty mass **including** battery): `m_e/m_TO = 0.312 m_TO^0.126` (m_TO in kg). At 1000 kg: 0.75; data scatter
±0.08. Valid 200-4300 kg, all configurations mixed (multicopter, tilt, lift + cruise). Quality of the underlying values
is marked in `benchmarks.csv`.

[W4] Reference points for a lift + cruise aircraft (S18 Table 3, electric L+C): empty incl. battery 0.853, battery
0.206 at 400 Wh/kg pack, payload 0.146 of MTOW. Joby S4 (claim): empty incl. battery 0.81, payload 0.19.

Validity: [W3] mixes design classes; use it as a sanity band (±10 % on empty fraction) around component build-ups,
not as a sizing law.

---

## 3. Component masses

Notation for RAY GA equations (RAY eqs. 15.46-15.58, units lb, ft, ft², lb/ft²): `W_dg` design gross weight (lb),
`N_z` ultimate load factor = 1.5 × limit (5.7 for n = 3.8), `q` cruise dynamic pressure (lb/ft²), `S_w` wing area,
`A` aspect ratio, `Lambda` quarter-chord sweep, `lambda` taper, `t/c` thickness ratio. Validity: GA aircraft
1,000-12,000 lb; below 1,000 lb they over-predict (expect +10 to +30 % for a 700-1000 kg composite eVTOL wing).

[M0] Empty mass excl. battery = sum of [M1]-[M16] (+ growth allowance, stated separately).

[M1] Wing (RAY 15.46): `W_wing = 0.036 S_w^0.758 W_fw^0.0035 (A/cos²Λ)^0.6 q^0.006 λ^0.04 (100 t/c / cosΛ)^-0.3 (N_z W_dg)^0.49`.
`W_fw` (wing fuel) is set to 1 lb for an electric aircraft (term = 1). Composite factor 0.85 (RAY table 15.4) only in the
"light" scenario.

[M2] Wing cross-check, NDARC parametric (AFDD93; NDARC ch. 19-1.2, average error 3.4 % on 25 aircraft):
`w_wing = 5.66411 f_LGloc (W_SD / (1000 cosΛ))^0.847 n_z^0.39579 S_w^0.21754 A^0.50016 ((1+λ)/τ)^0.09359 (1-b_fold)^-0.14356`
(lb, W_SD structural design gross weight lb, `n_z` ultimate, `τ` = t/c, f_LGloc = 1.0 with gear not on the wing).

[M3] Horizontal tail (RAY 15.47): `W_ht = 0.016 (N_z W_dg)^0.414 q^0.168 S_ht^0.896 (100 t/c / cosΛ)^-0.12 (A/cos²Λ_ht)^0.043 λ_h^-0.02`.

[M4] Vertical tail(s) (RAY 15.48): `W_vt = 0.073 (1 + 0.2 H_t/H_v) (N_z W_dg)^0.376 q^0.122 S_vt^0.873 (100 t/c / cosΛ_vt)^-0.49 (A/cos²Λ_vt)^0.357 λ_vt^0.039`,
applied per fin with `H_t/H_v = 0` (H-tail between booms).

[M5] Fuselage (RAY 15.49): `W_fus = 0.052 S_f^1.086 (N_z W_dg)^0.177 L_t^-0.051 (L/D)^-0.072 q^0.241` (S_f fuselage wetted
area ft², L_t tail arm ft, L/D fuselage length/depth). Unpressurised.

[M6] Landing gear (skid): NDARC fractional model (ch. 19-5): `W_LG = f_LG W_MTO (1 + f_LGcw)`, f_LG = 0.0325,
crashworthiness f_LGcw = 0.14 -> 3.7 % MTOW. Cross-check RAY 15.50 main gear `0.095 (N_l W_l)^0.768 (L_m/12)^0.409`
(N_l = 1.5 × 3.0 landing load factor), which is for wheeled GA gear and gives ~6.5 %.

[M7] Flight controls (RAY 15.54): `W_fc = 0.053 L^1.536 B_w^0.371 (N_z W_dg 1e-4)^0.80` (L fuselage length ft, B_w span ft).

[M8] Electric motor, NDARC/S18 eq. (1): `W_motor = 0.3928 Q^0.8587` (lb, Q in ft·lb = maximum torque). Cross-check
against CAT (this work): MGM REB 50 12.0 kg / 200 N·m -> 13.0 kg (+8 %); REB 60 15.3 kg / 250 N·m -> 15.7 kg (+3 %);
EMRAX 208 10.0 kg / 150 N·m -> 10.1 kg (+1 %); EMRAX 228 13.2 kg / 220 N·m -> 14.1 kg (+7 %); EMRAX 188 -6 %;
REB 30 7.7 kg / 150 N·m -> 10.1 kg (+32 %); REB 90 23.8 kg / 300 N·m -> 18.4 kg (-23 %). Valid 100-1000 N·m direct
drive. Design torque for lift motors = rotor-out torque [H6].

[M9] Rotor blades + hub, NDARC AFDD00 (ch. 19-2; blade 7.9 %, hub 9.2 % average error on 51 helicopter rotors):
`W_blade = 0.0024419 f_tilt N_rotor N_b^0.53479 R^1.74231 c^0.77291 V_tip^0.87562 ν^2.51048`,
`W_hub = 0.0061182 N_rotor N_b^0.20373 R^0.60406 V_tip^0.52803 ν^1.00218 (W_blade/N_rotor)^0.87127`
(lb, ft, ft/s; N_rotor enters linearly - the equations give the weight of all rotors - so the checker evaluates one rotor
and multiplies; ν flap frequency per rev, 1.10 assumed for hingeless fixed-pitch rotors; f_tilt = 1 for fixed rotors).
Helicopter-derived; for 1.5-2.5 m COTS composite propellers the result (2-5 kg per rotor) must be replaced by catalog
masses when available. In the NASA reproduction (validation/methods/nasa_lpc_reproduction.md) AFDD00 gives 40 % of
NASA's "rotor group", which also contains the rotor supports and the pusher.

[M10] Booms (physics-based, WP M): CFRP tube, outer diameter D_b, wall
`t = M_ult / (π (D_b/2)² σ_allow)` with `M_ult = 1.5 T_max,ctrl a_max × (2 if two rotors on the arm)`, σ_allow = 300 MPa
(quasi-isotropic wet lay-up / roll-wrapped tube, estimate), t ≥ 1.5 mm, ρ = 1550 kg/m³;
`m_boom = n_booms ρ π D_b t L_b × 1.6` (fittings, pylons, fairings). Strength only; stiffness, whirl and torsion are
for WP F. S18 notes that NDARC's standard rotor-support model is "likely quite optimistic" for booms.

[M11] Furnishings incl. seats and restraints: `max(RAY 15.58 = 0.0582 W_dg - 65 lb, 8 kg per seat)`.

[M12] Installed avionics (RAY 15.57): `W_av = 2.117 W_uav^0.933` (lb; W_uav uninstalled avionics, default 10 kg).

[M13] LV electrical system (RAY 15.56): `W_el = 12.57 (W_fs + W_av)^0.51` (lb), W_fs = 0 -> ~36 kg; override with a COTS
build-up (DC-DC, LV battery, LV harness) in the "light" scenario (12 kg).

[M14] HV harness cross-check: two conductors sized at J = 5 A/mm² for the rotor-out peak current,
`m = 2 L A ρ_Cu × 1.4` (insulation, lugs, shielding).

[M15] Ballistic parachute: least-squares line through GRS and MAG data (600-1050 kg):
`m_chute = 0.0208 m_TO - 1.34` (kg). Valid 600-1050 kg.

[M16] Inverters, cooling, connectors, wiring: S18 sec. VI B motor technology factor 1.63 ->
`m_acc = 0.63 m_motors` (conservative scenario). COTS check (CAT): MGM HBCi 400800 4.0 kg per REB 50 (0.33) or
HBCi 100400 1.8 kg per REB 30 (0.23) for the inverter alone; "light" scenario uses 0.35 including some cooling.

[B2] Battery pack: `m_pack = N_s N_p m_cell / (1 - f_ovh)`.

---

## 4. Hover and rotor sizing

[H0] Disk loading `DL = W / (N_disc π D²/4)` (N/m²); coaxial pairs count one disc per pair.

[H1] Momentum theory (LEI ch. 2): thrust per disc `T = W (1 + f_DL) / N_disc`; induced velocity
`v_h = sqrt(T / (2 ρ A))`; ideal power `P_i = T v_h = T^1.5 / sqrt(2 ρ A)`.

[H2] Blade-element/momentum power (LEI ch. 3): `P = κ P_i + σ c_d0 ρ A V_tip³ / 8`, solidity `σ = N_b c / (π R)`.

[H3] Figure of merit `FM = P_i / P`; shaft power `P_shaft = P_i / FM`; electrical `P_el = P_shaft / (η_m η_inv η_w) + P_aux`.
Validity: axial hover, CT/σ below stall. Measured FM of COTS propellers used as lift rotors is 0.60-0.75; S18 aircraft
FM 0.74 (download included).

[H4] Coaxial pair (LEI ch. 2, coaxial rotor): power of the pair = `k_coax T_pair^1.5 / sqrt(2 ρ A)` / FM with
k_coax = 1.0 (rotors close together, equivalent to one disc at the pair thrust; LEI gives an interference factor
1.16-1.28 relative to two isolated rotors).

[H5] Blade loading `C_T/σ = T / (ρ A V_tip² σ)`; keep `C_T/σ ≤ 0.12-0.14` in hover so that transition (where fixed-pitch
rotors at rpm control see rising C_T/σ, JS22 sec. 6.3, fig. 12) has stall margin.

[H6] One lift motor out, continued hover (requirement): trim of vertical force, roll, pitch and yaw with one rotor at
zero thrust, minimising the largest rotor thrust (linear programme with `T_i ≥ 0`; yaw from `Q_i = k_QT T_i`,
`k_QT = Q/T` from hover). Closed-form fallback: opposite rotor (row) throttled back, `T_max = W (1+f_DL)/(n-2)`
(S18 sec. V C: 6 rotors +50 %, 8 rotors +33 %). Four single rotors cannot trim (fail). Most-loaded motor power at
`T_max (1 + k_ctrl)`; torque `Q = P / (Ω sqrt(T/T_hover))` because fixed-pitch thrust scales with rpm². Criteria:
`P ≤ P_peak` and `Q ≤ Q_max` of the motor.

[H7] Tip Mach `M_tip = V_tip / a` (hover, hot day); pusher helical tip Mach `sqrt(V_tip² + V²) / a`. Screens:
lift rotor `M_tip ≤ 0.55` (NASA UAM concept rotors are designed at 550-600 ft/s, `M_tip` 0.49-0.54, S18 sec. VII C,
for noise), pusher helical `≤ 0.70` (compressibility and noise).

[N1] Noise trend (screening only): at fixed thrust, rotational and broadband noise rise steeply with tip speed (a
`~50-60 log10 V_tip` dependence is the usual rule of thumb for rotational noise; LEI noise chapter); lowering disk
loading lowers induced velocity and loading noise. No absolute dB prediction is made in M; WP C/F may add one.

[H8] Disk loading vs power loading trend: `W/P = FM sqrt(2 ρ / DL)` (N/W). Plotted with benchmark data in
`benchmarks/plots/disk_loading_vs_power_loading.png`.

---

## 5. Transition

[T1] Each transition (30 s, requirement) is charged at the mean of the hover and cruise electrical power,
`E_tr = t_tr (P_h,el + P_cr,el)/2`. Rationale: thrust on fixed lift rotors stays near W early in the transition while
induced power falls with speed (JS22 sec. 6.3, S18 fig. 8), and the pusher accelerates the aircraft. Bound: a fully
conservative value is `t_tr P_h,el`. A time-domain transition model is a WP D/C task (S18 sec. VII C notes that
force- and moment-trimmed conversion must be analysed).

---

## 6. Cruise drag, induced drag, propeller

[D1] Laminar skin friction `C_f = 1.328 / sqrt(Re)` (RAY 12.25).

[D2] Turbulent `C_f = 0.455 / ((log10 Re)^2.58 (1 + 0.144 M²)^0.65)` (RAY 12.27); mixed: `C_f = k_lam C_f,lam + (1-k_lam) C_f,turb`,
k_lam = 0.10 wing, 0.05 bodies (wet lay-up surfaces). Re on the component length.

[D3] Wing/tail form factor (RAY 12.30): `FF = [1 + 0.6/(x/c)_m (t/c) + 100 (t/c)^4] [1.34 M^0.18 cos^0.28 Λ_m]`.

[D4] Body/boom form factor (RAY 12.31): `FF = 1 + 60/f³ + f/400`, `f = l / sqrt(w h)`.

[D5] Wing wetted area (RAY 7.9): `S_wet = S_exp (1.977 + 0.52 t/c)`; interference Q = 1.0 (high wing, filleted),
1.04 tails, 1.1 booms (RAY sec. 12.5.5).

[D6] Fuselage wetted area from CAD; fallback `0.80 π d_eq L` (estimate).

[D7] Stopped lift rotors (per rotor): `D/q = 0.8 d_m h_m + 0.3 A_pylon + N_b C_f 1.3 (2 R c 0.9)`: exposed motor
bell as a short cylinder (HOE ch. 3, C_D ~ 0.8 on frontal area), faired pylon C_D 0.3, two blades parked along the
flow (skin friction with FF 1.3). Reference points: S18 Table 3 gives 1.2 ft² of "rotor hubs" for 8 R = 5 ft rotors
(0.014 m² per rotor, NASA-streamlined); the E8 subscale CFD scaled to 1.7 m rotors gave 0.047 m² per rotor
(../E8-eVTOL-Build/fullscale/FULLSCALE.md). [D7] gives 0.02-0.03 m² per rotor for COTS 25 cm motors.

[D8] Landing gear: skids `D/q = C_D A_frontal`, C_D = 1.0 (HOE ch. 3, cylinders in cross-flow).

[D9] Total: `(D/q)_0 = k_exc Σ (C_f FF Q S_wet)_i + Σ (D/q)_bluff`; `C_D0 = (D/q)_0 / S_ref`.

[I1] Drag `D = q S (C_D0 + C_L²/(π e A))`, `C_L = W/(q S)`; L/D = W/D.

[I2] Oswald factor (RAY 12.48, straight wing): `e = 1.78 (1 - 0.045 A^0.68) - 0.64`. Valid A = 5-12, unswept.

[P1] Actuator disc (MCC ch. 6): ideal efficiency `η_i = 2 / (1 + sqrt(1 + T/(q A_p)))`.

[P2] Real propeller `η_p = min(0.90 η_i, 0.86)`.

[E1] Cruise electrical power `P_cr,el = D V / (η_p η_m η_inv η_w) + P_aux`.

---

## 7. Battery, mission energy, range

[B1] Nominal energy `E_nom = N_s N_p E_cell`; nominal pack voltage `N_s V_cell`; capacity `N_p C_cell`.

[B3] Required nominal energy `E_nom,req = E_mission η_b / (f_EOL (1 - f_res))`; with the requirement values only
0.8 × 0.8 × 0.95 = 0.61 of the nameplate energy is available for the mission.

[B4] C-rate at end of life `C = P_el / (η_b f_EOL E_nom)` (1/h); compare with cell continuous rating
`I_cont / (f_EOL C_cell)` minus 0.3 C; one-pack-out case `C × n_packs/(n_packs - 1)` against the peak rating.
S18 eq. (3): `x_hover ∝ sqrt(W/(2ρA)) (η_cruise L/De)/(η_hover FM) / Range` - high hover C-rate comes from high disk
loading, poor FM, good cruise efficiency and short range. S18 reports 2.4 C for its electric L+C; 2-3 C "reasonable
near-term".

[E2] Hover energy `E_h = P_h,el (t_TO + t_L)` + vertical climb 30 m `W h / (η FM)` / 2 (approximate).

[E3] Climb to cruise altitude `E_cl = W Δh / (η_p η_drive)` (potential energy; the climb distance is credited to range).

[E4] Cruise `E_cr = P_cr,el R / V`.

[E6] Mission energy at the cells `E_mission = (E_h + E_tr + E_cl + E_cr) / η_b`.

[R1] Range at EOL with reserve `R = (E_nom f_EOL (1-f_res) η_b - (E_h + E_tr + E_cl)) / P_cr,el × V`.

---

## 8. Stall and speeds

[S1] `V_S = sqrt(2 W / (ρ_0 S C_Lmax))` (sea-level ISA, MTOW, EAS). C_Lmax from airfoil/flap data (default 1.4
clean, plain flap 1.5-1.7).

[S2] `V_cruise ≥ 1.3 V_S` (TAS at cruise altitude), RAY ch. 5 / CS23 23.335 minimum `V_C ≥ 33 sqrt(W/S)` (kt, lb/ft²)
and `V_D ≥ 1.25 V_C` (CS23 23.335(b)).

---

## 9. Loads

[L1] Limit manoeuvre load factors (requirements; CS23 23.337 normal category): +3.8 / -1.5; ultimate = 1.5 × limit;
landing 3.0 g. V-n: `V_A = V_S sqrt(n_+)`.

[L2] Finite-wing lift slope (Helmbold / RAY 12.6): `a = 2π A / (2 + sqrt(4 + A²/η² (1 + tan²Λ)))`, η = 0.95.

[L3] Gust load factor (CS23 23.341, Pratt): `μ_g = 2 (W/S) / (ρ c̄ a g)`, `K_g = 0.88 μ_g / (5.3 + μ_g)`,
`n = 1 + K_g ρ_0 U_de V_e a / (2 W/S)`, with U_de = 15.24 m/s at V_C and 7.62 m/s at V_D. Light, low-wing-loading
aircraft can be gust-critical: the checker compares n_gust(V_C) with the 3.8 g limit.

---

## 10. Cost

[C1]-[C8] Eastlake development and production model as given in GUD ch. 2 (W = airframe structural weight lb,
V_H = maximum level speed KTAS, N = units in 5 years, Q_m = units/month):
- engineering hours `H_eng = 0.0396 W^0.791 V_H^1.526 N^0.183 F_cert F_comp`
- tooling hours `H_tool = 1.0032 W^0.764 V_H^0.899 N^0.178 Q_m^0.066 F_comp`
- manufacturing hours `H_mfg = 9.6613 W^0.74 V_H^0.543 N^0.524 F_cert F_comp,mfg`
- development support `C_dev = 0.06458 W^0.873 V_H^1.89 N_p^0.346 CPI F_cert F_comp`
- flight test `C_ft = 0.009646 W^1.16 V_H^1.3718 N_p^1.281 CPI F_cert`
- materials `C_mat = 24.896 W^0.689 V_H^0.624 N^0.792 CPI F_cert`
- quality control `C_QC = 0.13 C_mfg F_cert F_comp`
with F_cert = 1 (Part 23) or 0.5 (LSA/experimental), F_comp = 1 + f_comp (engineering, tooling), 1 + 0.25 f_comp
(manufacturing), N_p = 2 prototypes.

Adaptation used by WP M (stated method): labour cost = hours × 2026 burdened in-house rates (engineering 95, tooling 65,
manufacturing 55 USD/h; estimates), without the additional rate multiplier that appears in GUD's labour-cost lines;
regression cost terms (materials, development support, flight test) escalated from 2012 USD by CPI = 1.40 (estimate
of the 2012-2026 CPI-U ratio; WP R to confirm). F_cert = 0.5 for the in-house build. The model is a DAPCA-IV derivative;
its developers report that DAPCA IV is unrealistically high for small, simple GA aircraft - Eastlake is used for the
*airframe* only.

[C9] Bottom-up COTS: cells × unit price × 1.6 (pack build: BMS, contactors, enclosure, cooling plates; estimate) +
motors/controllers at USD/kW of peak power (from CAT/the first-iteration ledger: T-Motor U15XXL + Thunder 300A,
USD 3,598 for ~20 kW bench peak -> ~180 USD/kW; MGM REB 50 + HBCi quotes pending, CAT estimate USD 10-18 k per set) +
propellers (CAT: E-PROPS reference EUR 1,304) + parachute (CAT: Magnum 601 SP USD 7,580, 901 SP USD 12,005) + flight
control (CAT: Veronte 4x EUR 23,500) + avionics and miscellaneous (estimates). Acquisition cost per aircraft =
[C9] + recurring Eastlake airframe cost at N = 10.

Complexity metric (for the objective): number of propulsion line-replaceable units (motors, inverters, propellers,
pylons) and number of distinct motor types; reported by `initial_estimate.py`.

---

## 11. What the checker compares and its tolerances

| Quantity class | warn | fail | Notes |
|---|---|---|---|
| total masses (empty, MTOW) | ±10 % | ±20 % | regressions are ±10-20 % at best |
| component masses | ±25 % | ±50 % | regression scatter; replaced by catalog masses when available |
| powers (hover, rotor-out, cruise), FM, η_p | ±10 % | ±20 % | |
| drag area, drag, L/D, Oswald | ±15 % | ±30 % | build-up vs CFD typically ±15 % |
| energy, range | ±10 % | ±20 % | |
| speeds (stall) | ±3 % | ±8 % | same equation, different inputs only |
| tip Mach | ±3 % | ±8 % | |
| C-rate | ±10 % | ±20 % | |
| geometry identities (closure, span, disk loading, cell energy) | ±1 % | ±5 % | bookkeeping |
| cost | ±30 % | ±60 % | |

Limit checks (PASS/WARN/FAIL against a requirement) are listed with the requirement value in the report.

## 12. Open verification items

1. AFDD00 [M9] is calibrated on helicopter rotors; replace with catalog propeller masses (WP P) as soon as published.
2. Eastlake coefficients and the CPI base in GUD ch. 2 [C1]-[C8] - check against the book (WP R).
3. Interpretation of the "0.3 C margin" requirement [B4] - requirements owner.
4. Stopped-rotor drag [D7] and download [H1] - replace with WP C results.
5. Boom mass [M10] - replace with WP F sizing.
