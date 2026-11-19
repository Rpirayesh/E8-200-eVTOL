# E8-200 COTS component catalog

Work package P, pass 1. Sources checked 2026-11-12. Machine-readable data: [catalog.json](catalog.json) (generated together with this page by [build_catalog.py](build_catalog.py); edit the script, not the outputs).

Every number has a source link in `catalog.json`. Prices are in the currency in which they were published; *quote required* items show the nearest published figure and how it was derived. Status: **shortlist** = baseline choice, *alternate* = qualified fallback, reference = benchmark only, not recommended = screened out (kept for traceability).

## Shortlist summary

**Final design (iteration 3.3, frozen, MTOW 1,350 kg):** 8 x EMRAX 268 MV liquid-cooled lift motors + 2 x MGM REB 90
boom-tail pushers, 10 x MGM HBCi 400800, 8 x E-PROPS 1.85 m 2-blade lift rotors, 2 x E-PROPS 1.75 m 2-blade pushers (same
rotation), 4 packs 175s5p Molicel P50B (3,500 cells, 63 kWh) with Orion BMS 2, aluminium HV feeders, Galaxy GRS 6 1200-1390
parachute, Veronte 4x (Cube Orange+ for the uncrewed phase). Priced bill of materials: [BOM.md](BOM.md). The pass-1 screening summary below is kept for traceability.

Selection rule from the consistency check in [validation/parts](../validation/parts/README.md): **8 lift rotors of
about 1.8-1.9 m** (largest diameter with COTS matched CW/CCW pairs and acceptable direct-drive torque); motor chosen by MTOW.

| Function | Baseline family | Mass (each) | Published price | Why |
|---|---|---|---|---|
| Lift motor, MTOW <= 700 kg | MGM COMPRO REB 30: 40 kW peak, 25-30 kW cont., 150 Nm, 1500-4000 rpm | 7.7 kg | quote (est. USD 4-7 k) | Passes hover + one-motor-out at 1000 m ISA+15 up to 700 kg with 1.8-1.9 m rotors; 94s bus |
| Lift motor, MTOW 700-900 kg | MGM COMPRO REB 50: 50 kW peak, 30-40 kW cont., 200 Nm, 400-800 V | 12.0 kg | quote (est. USD 5-9 k) | Passes to 900 kg with 1.9 m rotors on a 180s bus; +4.3 kg/motor vs REB 30 |
| Lift inverter | MGM HBCi 100400 (REB 30) / HBCi 400800 (REB 50) | 1.8 / 4.0 kg | quote (est. USD 2-4 k / 5-9 k) | 4-CPU layout, dual/quad redundant architectures, CAN |
| Lift rotor | E-PROPS UAV ground-adjustable carbon (matched CW/CCW to 1.90 m); Sensenich to 2.48 m; Helix to 2.8 m | t.b.d. | quote (ref. EUR 1,304 / USD 2,185 aircraft props) | COTS; ground-adjustable pitch trims hover rpm to the motor |
| Pusher | REB 90 (60-70 kW cont., 23.8 kg) or REB 50 if cruise <= 30 kW; 1.6-1.9 m E-PROPS / Sensenich / DUC prop | 12-24 kg | quote | Only REB 90 gives >= 40 kW continuous in direct drive at propeller rpm |
| Low-cost alternate (not baseline) | T-Motor U15XXL + Thunder 300A + NS62x24 (24S, 1.575 m) | 5.13 + 0.87 + 1.84 kg | USD 1,999 + 1,599 + 2,599 (kit from USD 5,997) | Fails one-motor-out at the 1000 m hot-day case; 100 V high current; China export licence from 18 Nov 2026 |
| Cells | Molicel P50B 21700 (5.0 Ah, 18 Wh, 71 g, 60 A) | 71 g | USD 7.50 (1000+) | Highest published energy at this power; 2-8C hover use; Samsung 50S second source |
| BMS | Orion BMS 2 (180 cells), one per pack | - | USD 1,680 | CAN, contactor control, proven in EV builds |
| Parachute | Magnum 601 SP (757 kg) or 901 SP (950 kg) | 12.4 / 17.6 kg | USD 7,580 / 12,005 | Published price and rating; Galaxy GRS 6 by quote |
| Flight control | Veronte Autopilot 4x (crewed), Cube Orange+ (uncrewed test phase) | 0.75 kg | EUR 23,500 / USD 350 | Only affordable COTS FCC with redundancy and DO-178C/DO-254 evidence |

Battery approach: build two or more independent packs in-house from P50B cells (pack-level ~170-180 Wh/kg expected - estimate,
benchmarked against the certified Pipistrel Velis pack at ~177 Wh/kg), each with its own Orion BMS 2, EV200 contactors,
fuse and HV bus, so that a single pack failure still allows a controlled landing.

## Lift and pusher motors

| ID | Status | Item | Mass (kg) | Key ratings | Price | Source |
|---|---|---|---|---|---|---|
| MOT-REB30 | **shortlist** | MGM COMPRO REB 30 (40 kW) outrunner, air or hybrid cooled | 7.7 | peak_power_kW: 40; cont_power_kW: 25-30; max_torque_Nm: 150; rpm_range: 1500-4000; voltage_V: 63-800 (winding specific); diameter_mm: 266; kv: winding specific, not published; cooling: air or hybrid air+fluid; rating_ambient_C: 25 | quote required (est. USD 4,000-7,000) | [link](https://pdf.aeroexpo.online/pdf/mgm-compro/reb-30-40kw-electric-motor/171210-21274.html) |
| MOT-REB50 | **shortlist** | MGM COMPRO REB 50 (50 kW) outrunner | 12 | peak_power_kW: 50; cont_power_kW: 30-40 (max continuous); max_torque_Nm: 200; rpm_range: 1500-4000; voltage_V: 400-800; diameter_mm: 266.8; cooling: air or hybrid fluid/air; sensors: sensored or sensorless | quote required (est. USD 5,000-9,000) | [link](https://mgm-compro.com/electric-motor/reb-50-50-kw/) |
| MOT-REB60 | alternate | MGM COMPRO REB 60 (60 kW) | 15.3 (excluding the optional encoder (+65 g)) | peak_power_kW: 60; max_torque_Nm: 250; max_rpm: 4000; voltage_V: 400-800; cont_power_kW: 35-45 (summary block); rpm_range: 1500-4000; diameter_mm: 270.8; table_25C_peak_power_kW: 33.5; table_25C_cont_power_kW: 25; table_25C_peak_torque_Nm: 133; table_25C_cont_torque_Nm: 95; table_kv_no_load_rpm_per_V: 42.5; table_kt_Nm_per_Arms: 0.313; table_max_phase_current_A: 700; phase_resistance_mOhm: 3.8; rotor_inertia_kgm2: 0.03; max_axial_load_N: 2500; bearings: 6205 2RS1 / 6204 2Z; max_operating_temp_C: 130; min_cable_mm2: 25; cooling: air or hybrid (fluid/air); sensors: U,V,W hall; PT1000; optional abs. encoder | quote required (est. USD 6,000-10,000) | [link](https://mgm-compro.com/electric-motor/reb-60-60-kw/) |
| MOT-REB90 | **shortlist** | MGM COMPRO REB 90 (80 kW) - E8-200 boom-tail pusher (x2) | 23.8 | peak_power_kW: 80; cont_power_kW: 60-70; max_torque_Nm: 300; rpm_range: 1500-4000; voltage_V: 400-800; diameter_mm: 270.2 | quote required (est. USD 8,000-14,000) | [link](https://mgm-compro.com/electric-motor/reb-90-80-kw/) |
| MOT-EMRAX188 | alternate | EMRAX 188 MV (axial flux) | 7.6 (7.1 AC / 7.9 LC / 7.6 CC) | peak_power_kW: 60 @ 6500 rpm (30 s); cont_power_kW: 23 AC / 29 LC / 33 CC; peak_torque_Nm: 100; cont_torque_Nm: 34 AC / 43 LC / 48 CC; limit_rpm: 8000; kv_no_load_rpm_per_V: 29.58; kv_nominal_load: 22.83; peak_current_Arms: 310; voltage_for_peak_V: 390; variants: HV 660 V / MV 390 V / LV 160 V | quote required | [link](https://emrax.com/wp-content/uploads/2025/03/EMRAX-188_datasheet_v1.7.pdf) |
| MOT-EMRAX208 | alternate | EMRAX 208 MV (axial flux) | 10 (9.4 AC / 10.3 LC / 10.0 CC) | peak_power_kW: 86 @ 6000 rpm (30 s); cont_power_kW: 33 AC / 47 LC / 52 CC; peak_torque_Nm: 150; cont_torque_Nm: 53 AC / 75 LC / 83 CC; limit_rpm: 7000; kv_no_load_rpm_per_V: 25.02; kv_nominal_load: 18.94; kt_Nm_per_Arms: 0.38; peak_current_Arms: 400; cont_current_LC_Arms: 220; voltage_for_peak_V: 420 | quote required | [link](https://emrax.com/wp-content/uploads/2025/03/EMRAX-208_datasheet_v1.7.pdf) |
| MOT-EMRAX228 | alternate | EMRAX 228 MV (axial flux) | 13.2 (12.9 AC / 13.5 LC / 13.2 CC) | peak_power_kW: 124 @ 5500 rpm (30 s); cont_power_kW: 48 AC / 68 LC / 75 CC; peak_torque_Nm: 220; cont_torque_Nm: 83 AC / 118 LC / 130 CC; limit_rpm: 6500; kv_no_load_rpm_per_V: 15.53; kv_nominal_load: 12.05; peak_current_Arms: 360; cont_current_LC_Arms: 180; voltage_for_peak_V: 630 | quote required | [link](https://emrax.com/wp-content/uploads/2025/03/EMRAX-228_datasheet_v1.7.pdf) |
| MOT-EMRAX268 | **shortlist** | EMRAX 268 MV (axial flux) - E8-200 lift motor (x8), iteration 3.3 | 21.9 (21.4 AC / 22.3 LC / 21.9 CC) | peak_power_kW: 210 @ 4250 rpm (30 s); cont_power_kW: 64 AC / 91 LC / 101 CC; peak_torque_Nm: 500; cont_torque_Nm: 144 AC / 205 LC / 226 CC; limit_rpm: 4500; kv_no_load_rpm_per_V: 8.68; peak_current_Arms: 500; cont_current_LC_Arms: 220 | quote required (ref. USD 12,000) | [link](https://emrax.com/wp-content/uploads/2025/08/EMRAX-268_datasheet_v1.7_version_C.pdf) |
| MOT-U15XXL | alternate | T-Motor U15XXL KV29 (24S) manned-aircraft motor | 5.13 (with cable) | kv: 29; voltage: 24S LiPo (~100 V); config: 36N42P; shaft_mm: 25; peak_current_A: 210 (80 s); internal_resistance_mOhm: 20; bench_max: 101.4 kgf, 20.09 kW, 209 A, 2203 rpm at 96 V with NS62x24; bench_67kgf: 67.6 kgf, 10.61 kW, 109 A, 1800 rpm; coil_temp_note: 184 C after 1 min full throttle at 32 C ambient (not a continuous rating) | USD 1,999.00 | [link](https://shop.tmotor.com/products/u15xxl-manned-aircraft-combo) |
| MOT-TM-S150 | alternate | T-Motor S150 high-power heavy-load drive system (400 V) | 9.1 | max_power_kW: 42; voltage_V: 400; max_pull_kgf: 165 | quote required | [link](https://uav-en.tmotor.com/news/61.html) |
| MOT-MAD-M90C60 | alternate | MAD Components M90C60 EEE V1.0, 9 KV manned-drone motor | 12.7 (reseller figure (14 kg boxed)) | kv: 9; pole_pairs: 21; size_mm: 257 x 123; shaft_mm: 35; sustained_power_kW: up to 45 (MAD USA); max_power_kW: 55.6 (reseller); max_current_A: 150.8 (reseller); voltage_V: 400 (reseller); recommended_lift_kgf: 70-100; max_thrust_kgf: 200.1 (reseller); insulation: 220 C wire, 180 C magnets | USD 5,000.00 | [link](https://www.madcomponentsusa.com/m90c60-eee-manned-drone-motor.html) |
| MOT-HW-P50M | not recommended | Hobbywing P50M propulsion system (400 V, 9/11 KV) | 6.2 (system incl. ESC and prop; motor 4.25 kg, ESC 1.2 kg) | input_V: 280-480 (400 rated); official_thrust_per_axis_kgf: 50; max_thrust_kgf: 116; esc_current_A: 40 cont / 80 peak (3 s); props: MSC 64x23 or USC 54x23 | quote required | [link](https://www.hobbywing.com/en/products/p50m) |
| MOT-GEIGER-HPD32D | reference | Geiger Engineering HPD 32D (duplex) | 12 | power_kW: 40 @ 2200 rpm; note: HPD 50D: 60 kW @ 2200 rpm, 15 kg; HPD 25D: 30 kW @ 1950 rpm, 10 kg | quote required | [link](https://aeroenginesaz.com/en/brand_geiger-engineering) |
| MOT-PLETT-NOVA30 | reference | Plettenberg Nova 30 | 5 | power_kW: 30; voltage_V: 120; torque_Nm: 105; peak_eff: 0.93 | quote required (ref. EUR 2,101) | [link](https://sustainableskies.org/plettenbergs-new-motors-ready-for-real-airplanes/) |
| MOT-H3X-180R | not recommended | H3X HPDM-180R (integrated motor-drive with reduction) | 16 | power_kW: 180; output_rpm: ~2985; integrated_inverter: True; note: HPDM-180D direct drive: 13 kg, 86 Nm continuous, 20,000 rpm | quote required | [link](https://www.h3x.tech/products/hpdm-180r) |
| MOT-OTHERS | reference | Hacker, Rotex Electric, Saluqi, Sky-Watcher, Scorpion large (screened) | - |  | quote required | [link](https://en.wikipedia.org/wiki/Rotex_Electric_REB_90) |

- **MOT-REB30**: Direct-drive torque class suits 1.8-2.0 m rotors at 1,500-2,000 rpm. Same frame family as REB 50/60/90, so the lift and pusher motors can share mounts, sensors and supplier. Ratings from the manufacturer's catalogue sheet hosted on aeroexpo; confirm against the current MGM datasheet and ask for the winding matched to a 94s (~340 V nominal, 395 V max) bus. Passes the one-motor-out check to 700 kg MTOW with 8 rotors of 1.8-1.9 m (validation/parts).
- **MOT-REB50**: Lift motor for MTOW 700-900 kg with 8 rotors of ~1.9 m (validation/parts); also the pusher if cruise needs <= 30 kW continuous (single motor type). Needs a 400-800 V bus (~180s). Previous E8 iteration screened it at 30 kW continuous.
- **MOT-REB60**: The MGM page carries two inconsistent rating sets: the summary block (60 kW, 250 Nm, 35-45 kW continuous, 400-800 V) used by WP D, and a detailed table 'valid for 25 C' (33.5 kW peak, 25 kW continuous, 133 Nm peak, 95 Nm continuous, KV 42.5 rpm/V, 700 A). The table KV is a low-voltage winding (4,000 rpm at ~94 V); the E8-200 175s bus needs a no-load KV of at least ~5.7 rpm/V (validation/parts). The design case needs 248 Nm and 56 kW in the one-motor-out flare: the winding, torque and continuous rating must be confirmed in the MGM quote before ordering (manufacturing/QUOTES_TO_REQUEST.md). Max axial load 2,500 N vs 2,148 N rotor thrust in the OEI flare.
- **MOT-REB90**: Pusher option if cruise power exceeds ~40 kW continuous. Wikipedia lists the same REB 90 under Rotex Electric at 20 kg dry; the MGM page (23.8 kg) is used here.
- **MOT-EMRAX188**: Too little torque for direct drive of a lift rotor (48 Nm continuous). Datasheet v1.7 states the 188/208/228/268/348 range is being replaced by a next-generation range with the same envelope.
- **MOT-EMRAX208**: Continuous power is reached only near 6000 rpm; at a 2,400 rpm pusher the 83 Nm continuous torque gives about 21 kW. Dual-winding (2x UVW) version available for inverter redundancy.
- **MOT-EMRAX228**: Direct-drive pusher at ~2,400 rpm: 130 Nm continuous -> ~33 kW, 220 Nm peak -> ~55 kW.
- **MOT-EMRAX268**: Iteration 3.3 lift motor, direct drive at about 1,900 rpm hover; ratings used: 500 N m peak, 205 N m / 91 kW LC continuous (published datasheet). Winding for the 175-180s bus (525-756 V) to be confirmed with EMRAX; liquid cooled. Each station needs a coolant loop (COOL-MOT) and the MP-EMX adapter plate. EMRAX states the 188-348 range is being replaced by a next-generation range with the same envelope: quote the successor.
- **MOT-U15XXL**: Lowest-cost published option and complete bench data, but a 100 V system needs ~4x the current of a 400 V bus; usable only for an MTOW near the low end with 8 rotors. Export licensing: China requires licences from 18 Nov 2026 for drone motors >=48 V, >=3 kW, >=3 kW/kg, <=3000 rpm, their ESCs and large carbon blades; this motor meets all four criteria. T-Motor is also on the US Entity List.
- **MOT-TM-S150**: Right power class and voltage for 6-8 lift rotors, but only show-announcement data; same export licensing and entity-list exposure as other T-Motor heavy-lift products.
- **MOT-MAD-M90C60**: Published price and 400 V rating; mass and power partly from a reseller. Matching ESC/inverter must be sourced separately (an MGM HBCi 400400 class unit fits the voltage). Export licensing risk as above.
- **MOT-HW-P50M**: 50 kgf official per-axis rating would need 12-18 rotors at 600-900 kg MTOW; the 40 A continuous ESC limits sustained power to ~16 kW at 400 V.
- **MOT-GEIGER-HPD32D**: Third-party data (aeroenginesaz.com, last updated 2018); duplex winding gives inherent drive redundancy. Current availability to be confirmed with Geiger.
- **MOT-PLETT-NOVA30**: Paramotor/ultralight class, 120 V; low voltage and 30 kW cap make it a fallback only.
- **MOT-H3X-180R**: Integrated inverter saves mass but is 2-4x oversized and a single-source development product.
- **MOT-OTHERS**: Hacker's published Q-series are RC-scale (Q100-5L 2.3 kg, no kW rating for aircraft use). The REB line marketed as 'Rotex Electric' is the MGM COMPRO REB family listed above. No manufacturer data was found for 'Saluqi' or a 'Sky-Watcher' aviation motor; Scorpion's largest motors are below 15 kW. These are not carried further.

## Inverters / ESCs

| ID | Status | Item | Mass (kg) | Key ratings | Price | Source |
|---|---|---|---|---|---|---|
| INV-HBCI100400 | **shortlist** | MGM COMPRO HBCi 100400 (400 V, 100 A) | 1.8 (cold-plate version; 2.3 kg fluid cooler; 2.3-2.7 kg air-cooled) | voltage_V: 120-400 (28-96 Li-ion cells); cont_current_A: 100 fluid / 80 KGR air / 60 KEA300 air; peak_power_kW: 40 (air, headline) / 50 short-time (table); cont_power_kW: 25; logic_supply_V: 11-25; comms: CAN, RS-485, RS-232 TTL, logic I/O; redundancy: 4-CPU layout; dual/quad-controller architectures, multi-winding motors | quote required (est. USD 2,000-4,000) | [link](https://mgm-compro.com/controllers-inverters-escs/hbci-100400/) |
| INV-HBCI400400 | alternate | MGM COMPRO HBCi 400400 (400 V, 400 A) | 4 | voltage_V: up to 400; current_A: 400; peak_power_kW: 200; cont_power_kW: 160; redundancy: 4-CPU layout | quote required (est. USD 4,000-8,000) | [link](https://mgm-compro.com/controllers-inverters-escs/hbci-400400/) |
| INV-HBCI400800 | **shortlist** | MGM COMPRO HBCi 400800 (800 V, 400 A) | 4 (cooling-plate version; larger cooled versions weigh more) | voltage_V: 120-800; current_A: 400; peak_power_kW: 400; cont_power_kW: 320 | quote required (est. USD 5,000-9,000) | [link](https://mgm-compro.com/controllers-inverters-escs/hbci-400800/) |
| INV-HBCI380120 | alternate | MGM COMPRO HBCi 380120 (120 V, 380 A) | 1.035 | voltage_V: up to 120; current_A: 380; peak_power_kW: 51; cont_power_kW: 45 | quote required (est. USD 1,500-3,500) | [link](https://mgm-compro.com/controllers-inverters-escs/hbci-380120/) |
| INV-THUNDER300 | alternate | T-Motor Thunder 300A 24S ESC | 0.87 | voltage: 14-24S; cont_current_A: 150 (T-Motor shop) / 240 (LigPower) - sources conflict; peak_current_A: 300 (10 s); bec: False; programmable: False | USD 1,599.00 | [link](https://shop.tmotor.com/products/u15xxl-manned-aircraft-combo) |
| INV-CM200DX | reference | Cascadia Motion CM200DX | 11.3 (25 lb (New Eagle listing)) | voltage_V: 50-480; cont_current_Arms: 300; peak_current_Arms: 740 | USD 7,202.00 | [link](https://store.neweagle.net/?p=18103) |
| INV-SEVCON-G5S9 | reference | Sevcon (BorgWarner) Gen5 Size 9 | 6 (13.2 lb (Thunderstruck); another reseller gives 18 lb) | voltage_V: 128-450 (derated above 420); cont_current_A: 200; peak_current_A: 400; ip: IP6K9K | quote required | [link](https://www.thunderstruck-ev.com/sevcon-g5s9-controller.html) |
| INV-PLETT-MST | reference | Plettenberg MST 140-200 / MST 400-400 | 1.3 (MST 140-200 1.3 kg; MST 400-400 2.9 kg) | MST140-200: 30 kW cont / 40 kW peak; MST400-400: 120 kW cont / 160 kW peak, water cooled | quote required (ref. EUR 1,547) | [link](https://sustainableskies.org/plettenbergs-new-motors-ready-for-real-airplanes/) |
| INV-EMSISO-H20 | reference | Emsiso emDrive H20 (400/800 V, 30-60 kW PMSM) | - | voltage_V: 400 and 800 variants; motor_range_kW: 30-60 | quote required | [link](https://metstrade.com/exhibitors/emsiso-d-o-o/products/emdrive-h20) |

- **INV-HBCI100400**: Partner for REB 30 on a 94s bus (395 V max; 96s would reach 403 V). 100 A continuous only with fluid cooling: plan a cold plate in the boom/pylon or accept the 80 A air-cooled rating.
- **INV-HBCI400400**: Oversized for one lift motor; suits the pusher (EMRAX 228/REB 50 at 400 V) or MAD M90C60.
- **INV-HBCI400800**: Needed if REB 50 (400-800 V) is chosen; strongly oversized per motor. Ask MGM for a smaller 800 V unit.
- **INV-HBCI380120**: Higher-grade alternative to the Thunder 300A for a 24S (~100 V) U15XXL configuration.
- **INV-THUNDER300**: The kit's own bench data draw 209 A at full thrust, above the 150 A continuous figure on the T-Motor page. No CAN telemetry; not programmable. Export licensing applies to matching ESCs.
- **INV-CM200DX**: Automotive unit, robust and well documented, but ~3x the mass of an MGM unit of equal rating.
- **INV-SEVCON-G5S9**: Industrial/automotive; heavier than aviation-oriented controllers.
- **INV-PLETT-MST**: Low-voltage paramotor-class controllers.
- **INV-EMSISO-H20**: Slovenian inverter commonly paired with EMRAX motors; marine-oriented listing.

## Propellers and rotors

| ID | Status | Item | Mass (kg) | Key ratings | Price | Source |
|---|---|---|---|---|---|---|
| PROP-TM-NS62 | alternate | T-Motor NS62x24 carbon 2-blade (1.575 m) | 1.84 (920 +/- 40 g per blade) | diameter_m: 1.575; pitch_in: 24; material: CF + epoxy; bench_max_kgf: 101.4; bench_rpm_max: 2203; tip_speed_at_max_mps: 181.7 | USD 2,599.00 | [link](https://shop.tmotor.com/products/u15xxl-manned-aircraft-combo) |
| PROP-EPROPS-UAV-ADJ | **shortlist** | E-PROPS UAV ground-adjustable carbon propellers (50-180 kW) | - | diameter_CW_in: 47-82 (1.20-2.09 m); diameter_CCW_in: 47-75 (1.20-1.90 m); matched_CW_CCW_max_in: 74.8; max_power_2blade_kW: 86; max_power_3blade_kW: 128; max_power_4blade_kW: 172; hub_pattern: 6M8 d101.6 or 6M8 d100 | quote required (ref. EUR 1,304) | [link](https://uav.e-props.fr/adjustable-pitch.php) |
| PROP-SENSENICH-UAV | **shortlist** | Sensenich ground-adjustable composite UAV propellers | - | diameter_in: 15-98 (0.38-2.48 m); power_hp: 5-200; rotation: CW or CCW, tractor or pusher; hub: standard and custom flange patterns | quote required (ref. USD 2,185) | [link](https://sensenich.com/?p=4931) |
| PROP-HELIX | alternate | Helix carbon propellers (fixed F / ground-adjustable V series) | - | diameter_m: 0.75-2.8; types: fixed pitch, ground adjustable, in-flight (electric/hydraulic) | quote required | [link](https://helix-propeller.de/) |
| PROP-DUC-SWIRL | alternate | DUC Hélices SWIRL ground-adjustable (2 or 3 blade) | 2.72 (2-blade 68.1 in: 6.0 lb; 3-blade: 8.0 lb) | diameters_in: 59.8, 63.8, 65.4, 68.1 | USD 2,226.00 | [link](https://aircraftspruce.com/catalog/appages/duc_swirl-blade.php) |
| PROP-NEUFORM | not recommended | Neuform CR3-V in-flight adjustable | - |  | quote required | [link](https://www.experimentalaircraft.info/articles/neuform-composites.php) |
| PROP-INHOUSE | not recommended | In-house CNC wood or wet-layup composite rotor blades | - |  | quote required | [link](https://store.astm.org/f2506-22.html) |

- **PROP-TM-NS62**: Matched to U15XXL with full bench table. Blade radius 31 in exceeds the 30 in threshold in the Chinese licence list.
- **PROP-EPROPS-UAV-ADJ**: CCW blades are published only to 75 in (1.90 m): the 1.90 m lift pairs are exactly at the matched limit and a 2.05 m CCW pusher is outside the published range (quote). Best COTS fit for 1.7-1.9 m lift rotors with matched CW/CCW pairs and for the pusher. Ground-adjustable pitch lets the team trim hover rpm to the motor without new blades. Warranty excludes VTOL use on the manned-aircraft site, so a UAV/VTOL supply agreement is needed.
- **PROP-SENSENICH-UAV**: Only US COTS source found that covers 2.0-2.48 m with both rotation directions. Request-for-quote.
- **PROP-HELIX**: Widest diameter range found (to 2.8 m): the only COTS route for 2.5-2.8 m lift rotors.
- **PROP-DUC-SWIRL**: Rotax-class pusher propeller; maximum 1.73 m. Hub to be adapted to the motor flange.
- **PROP-NEUFORM**: In-flight adjustable pitch adds an actuator and failure mode; contrary to the low-complexity objective.
- **PROP-INHOUSE**: Feasible to manufacture (two-sided 3-axis machining with flip jig and dowel registration; or wet-layup in CNC-machined split moulds), but flight use requires the strength, vibratory-stress, fatigue and endurance testing of ASTM F2506 / AC 20-66A / AC 35.37-1 class methods. Lift rotors on an eVTOL see 1P-nP cyclic loads in edgewise flow during transition. Use only for whirl-tower and ground rigs.

## Battery cells

| ID | Status | Item | Mass (kg) | Key ratings | Price | Source |
|---|---|---|---|---|---|---|
| CELL-P50B | **shortlist** | Molicel INR-21700-P50B | 0.071 (maximum) | capacity_Ah: 5.0; energy_Wh: 18.0 typ / 17.5 min; nominal_V: 3.6; charge_V: 4.2; cont_discharge_A: 60 (80 C cut-off); dc_impedance_mOhm: 12.8 typ at 50 % SOC; specific_energy_Wh_per_kg: 253 (18.0 Wh / 71 g, computed) | USD 7.50 | [link](https://www.molicel.com/product/inr-21700-p50b/) |
| CELL-P45B | alternate | Molicel INR-21700-P45B | 0.069 (maximum) | capacity_Ah: 4.5; nominal_V: 3.6; cont_discharge_A: 45; specific_energy_Wh_per_kg: 242 | USD 6.99 | [link](https://www.molicel.com/product/inr-21700-p45b/) |
| CELL-SAM50S | alternate | Samsung INR21700-50S | 0.072 (70.1 g typ / 72 g max (sellers)) | capacity_Ah: 5.0; cont_discharge_A: 25 (45 with 80 C cut-off); nominal_V: 3.6 | USD 5.99 | [link](https://18650batterystore.com/products/samsung-50s-21700-5000mah-25a-battery) |
| CELL-SAM50G | not recommended | Samsung INR21700-50G | 0.068 (68.0 g measured, no wrap) | capacity_Ah: 4.85-4.9 min; cont_discharge_A: 9.7; nominal_V: 3.63 | quote required | [link](https://www.nkon.nl/en/samsung-inr21700-50g.html) |
| CELL-EVE50PL | alternate | EVE INR21700/50PL (tabless) | 0.072 (approx., retailer) | capacity_Ah: 5.0; nominal_V: 3.6; cont_discharge_A: 50 (retailer; another lists 125) | quote required | [link](https://www.18650batterystore.com/products/eve-50pl-21700-5000mah-50a-battery) |
| CELL-AMPRIUS | reference | Amprius SiCore 21700 (6.3 Ah) / SiCore aviation cells | - | 21700_6p3Ah_Wh_per_kg: 315; sicore_aviation_Wh_per_kg: 370; sicore_power_W_per_kg: 3000; discharge: up to 10C uncooled / 15C cooled (SiCore) | quote required | [link](https://www.businesswire.com/news/home/20250306597630/en) |
| CELL-VTC6A | reference | Sony/Murata US18650VTC6A | - |  | quote required | - |

- **CELL-P50B**: Best published energy at high power. Hover at ~3-5C on a 1.5-2 kWh/cell-group pack is well inside the 12C (60 A) rating, which leaves margin for one-pack-out operation.
- **CELL-P45B**: Lower energy than P50B with no advantage at this C-rate.
- **CELL-SAM50S**: Equal capacity to P50B at lower discharge rating; second source if P50B supply is short.
- **CELL-SAM50G**: ~2C limit is insufficient for hover and motor-out power.
- **CELL-EVE50PL**: Potential low-cost alternative; ratings need the manufacturer datasheet.
- **CELL-AMPRIUS**: Highest specific energy found; supply to small builders and cycle life to be confirmed. Growth option.
- **CELL-VTC6A**: 18650 format would double the cell count vs 21700; not pursued.

## Commercial packs (benchmarks)

| ID | Status | Item | Mass (kg) | Key ratings | Price | Source |
|---|---|---|---|---|---|---|
| PACK-PIPISTREL | reference | Pipistrel Velis Electro battery pack (2 modules) | 70 (per pack per Wikipedia; another source gives 60 kg) | aircraft_total_kWh: 24.8; packs_per_aircraft: 2; cooling: liquid; pack_specific_energy_Wh_per_kg: ~177 (24.8 kWh / 140 kg, computed) | EUR 25,000 / pack | [link](https://en.wikipedia.org/wiki/Pipistrel_Velis_Electro) |
| PACK-H55 | reference | H55 certifiable propulsion battery modules | - | status: EASA-witnessed module certification tests completed Dec 2025; CS-23 path; DOA+POA | quote required | [link](https://www.electrive.com/2026/02/03/h55-completes-certification-tests-for-propulsion-battery-modules-for-electric-aircraft) |

- **PACK-PIPISTREL**: Certified-aircraft pack, not sold for other airframes. Used as the benchmark for pack-level specific energy (~177 Wh/kg) and cost (~EUR 1,000/kWh).
- **PACK-H55**: Reference for thermal-runaway containment practice; Electroflight: no current product data found.

## Battery management

| ID | Status | Item | Mass (kg) | Key ratings | Price | Source |
|---|---|---|---|---|---|---|
| BMS-ORION2 | **shortlist** | Orion BMS 2 (up to 180 cells in series) | - | cells_series_max: 180; interface: CAN, contactor/charger control | USD 1,680.00 | [link](https://www.orionbms.com/manuals/pdf/orionbms2_purchasing_guide.pdf) |
| BMS-EMUS-G1 | alternate | EMUS G1 BMS control unit + per-cell-group modules | - | architecture: distributed cell modules | USD 397.00 | [link](https://www.electricmotorsport.com/ev-parts/emus-bms-g1-control-unit-9-32v-dc-supply-voltage.html) |
| BMS-ENNOID | reference | ENNOID-BMS HV (open source) | - |  | quote required | [link](https://sites.google.com/ennoid.me/2017/bms/gen-1) |

- **BMS-ORION2**: One unit per independent pack (2-4 per aircraft). Widely used in EV conversions with CAN DBC files.
- **BMS-EMUS-G1**: 96 cell modules (USD 1,728) + controller per pack; more wiring points than Orion.
- **BMS-ENNOID**: Open hardware; would need in-house validation.

## HV distribution and power conversion

| ID | Status | Item | Mass (kg) | Key ratings | Price | Source |
|---|---|---|---|---|---|---|
| HV-EV200 | **shortlist** | TE Kilovac EV200 main contactor (500 A, 900 VDC) | - | cont_current_A: 500; voltage_VDC: 900 | USD 193.00 | [link](https://nl.farnell.com/en-NL/kilovac-te-connectivity/ev200adana/contactor-spst-no-95v-500a-panel/dp/2581484) |
| HV-FUSE | **shortlist** | EV pack fuse 1000 VDC 200 A class (Eaton Bussmann FWE-200A / Mersen MEV100A200) | - | voltage_VDC: 1000; current_A: 200; Mersen_breaking: 20 kA at 1000 V, L/R <= 1 ms | USD 186.34 | [link](https://us.mersen.com/en/products/evpack-fuse-mev100a-1000-vdc-max-l-r-less-or-equal-1ms-50-300a-round-body-fuse) |
| HV-CONN | **shortlist** | Amphenol SurLok Plus 8 mm HV connectors | - | family: touch-safe single-pole HV, 8 mm | USD 13.13 | [link](https://www.digikey.co.uk/en/products/detail/amphenol-industrial-operations/SLPIPB35BSB0/9444330) |
| HV-DCDC | alternate | Isolated HV-to-28 V DC-DC (Vicor V375A28H600BL 600 W, 250-425 V in) | - | input_V: 250-425; output_V: 28; power_W: 600 | GBP 1,178.29 | [link](https://www.digikey.co.uk/en/products/detail/vicor-corporation/V375A28H600BL/3002341) |
| HV-AL-CABLE | **shortlist** | Aluminium-conductor HV cable (single core, screened, 35 mm2 class) with bimetal lugs | - | length_m: ~92 (design/selected_design.json hv_cable_length_m); voltage: >= 1000 VDC rating required | quote required (ref. USD 20.3) | [link](https://hilltop-products.co.uk//35mm-screened-automotive-high-voltage-electric-vehicle-cable-ev350-coroplast-9-2611.html) |
| HV-DCDC-MW | **shortlist** | Mean Well RSDH-300-24 DC-DC (250-1500 VDC in, 24 V 12.5 A, 300 W) | - | input_V: 250-1500 (800 nominal); output: 24 V / 12.5 A; power_W: 300 | USD 136.89 | [link](https://www.digikey.sg/en/products/detail/mean-well-usa-inc/RSDH-300-24/18069326) |

- **HV-EV200**: Two per pack (positive and negative) plus a precharge relay/resistor. LEV200 lighter variant exists.
- **HV-FUSE**: Rating to be set from the final bus current; one main fuse per pack plus per-inverter branch fuses.
- **HV-CONN**: Anderson SBS75X is rated 600 V / 110 A (USD ~7.6) - acceptable for a <=400 V bus only.
- **HV-DCDC**: Two units (one per HV bus) diode-ORed with a 28 V LiFePO4 backup battery. For an 800 V bus use Recom RMOD4000-650-28SEW (180-950 V in, 4 kW; listed 'coming soon').
- **HV-AL-CABLE**: WP D iteration 3 uses aluminium feeders (half the copper mass at equal resistance). Cross-section per run from WP D; REB 60 table asks for >= 25 mm2 copper. Termination with bimetal crimp lugs and contact grease; torque-seal.
- **HV-DCDC-MW**: Replaces HV-DCDC (Vicor, 250-425 V input) which does not cover the 148s bus (444-622 V). Two per HV bus side (4 total, 1.2 kW), diode-ORed with the 24 V LiFePO4 backup. Railway-type industrial unit: vibration and EMI test required.

## Ballistic parachutes

| ID | Status | Item | Mass (kg) | Key ratings | Price | Source |
|---|---|---|---|---|---|---|
| CHUTE-MAG601 | **shortlist** | Magnum 601 SP softpack (Stratos 07) | 12.4 (27.3 lb system) | max_gross_lb: 1670; max_gross_kg: 757; max_deploy_mph: 199 | USD 7,580.00 | [link](https://uflyit.com/Magnum%20Parachutes%202.htm) |
| CHUTE-MAG901 | **shortlist** | Magnum 901 SP softpack (Stratos 07) | 17.6 (38.8 lb system) | max_gross_lb: 2094; max_gross_kg: 950; max_deploy_mph: 199 | USD 12,005.00 | [link](https://uflyit.com/Magnum%20Parachutes%202.htm) |
| CHUTE-GRS600 | alternate | Galaxy GRS 6/600 SD Speedy 115 m2 | 12.3 (11.5 kg unit / ~12.3 kg total packed) | mtow_kg: 600; vne_kmh: 380 (400 high-speed variant); standard: ASTM F2316-12 | quote required | [link](https://galaxysky.cz/grs-6-600-sd-speedy-ff-115-m2-p22-en) |
| CHUTE-GRS750 | alternate | Galaxy GRS 6 650-700 SD Speedy / 750 SDS 140 m2 | 14.8 (750 SDS/FF softpack ~14.8 kg) | mtow_kg: 650 / 700 / 750; vne_kmh: 325 / 295 / 250; descent_mps: 7.2 @700 kg, 7.6 @750 kg (1500 m) | quote required | [link](https://galaxysky.cz/grs-6-650-700-sd-speedy-140m2-p40-en) |
| CHUTE-GRS990 | alternate | Galaxy GRS 6 800-990 SDS 175 m2 | 21.7 ('total weight +/-4 %') | mtow_kg: 800 / 900 / 1050; vne_kmh: 380 / 350 / 315; descent_mps: 7.1-7.9 at 1000 m; canopy_m2: 175; standard: ASTM F2316-12 | quote required (ref. USD 14,000) | [link](https://galaxysky.cz/grs-6-800-990-sds-175m2-p43-en) |
| CHUTE-BRS6 | reference | BRS-6 (models 600-1800) | 18.1 (BRS6-1800 softpack ~40 lb (used-sale listing)) | models: 600, 800, 1050, 1350, 1350HS, 1600, 1800 (lb class); repack: 6 years; rocket 12 years | USD 9,341.00 | [link](https://www.aircraftspruce.com/catalog/pspages/brs-parachutes-lsa.php) |
| CHUTE-GRS1190 | alternate | Galaxy GRS 6 990-1190 SDS/FF 245 m2 | 28.9 (Soft B2 pack, total packed) | mtow_kg: 990 / 1190; vne_kmh: 320 / 280; opening_shock: 45.6 kN / 4.7 g at 990 kg; 48.8 kN / 4.2 g at 1190 kg; descent_mps: 5.6-6.2 at 1000 m; pack_cm: B1 64x34x23; B2 63x38x21; standard: ASTM F2316-12 | quote required (ref. USD 16,000) | [link](https://galaxysky.cz/grs-6-990-1190-sds-ff-245m2-p44-en) |
| CHUTE-GRS1390 | **shortlist** | Galaxy GRS 6 1200-1390 SDS/FF 245 m2 | 28.9 (Soft B2 pack, total packed (+-4 %)) | mtow_kg: 1200 / 1390; vne_kmh: 280 / 260; opening_shock: 48.8 kN / 4.2 g at 1200 kg; 57.4 kN / 4.2 g at 1390 kg; 57.8 kN at 250 km/h; max_load_kg: 1500 at 250 km/h; descent_mps: 6.3-6.7 at 1000 m AMSL; 6.5-6.9 at 1500 m (MTOW); min_rescue_height_m: 150 at 95 km/h, horizontal flight; pack_cm: B1 64x34x23; B2 63x38x21 | quote required (ref. USD 17,000) | [link](https://galaxysky.cz/grs-6-1200-1390-sds-ff-245m2-p45-en) |

- **CHUTE-MAG601**: Covers MTOW up to 757 kg. Dealer notes the column mapping on its page is inconsistent in places: confirm with Magnum.
- **CHUTE-MAG901**: Use if MTOW is 757-950 kg.
- **CHUTE-GRS990**: Galaxy also lists a multicopter range.
- **CHUTE-BRS6**: BRS sells installation-specific systems; a custom eVTOL installation needs BRS engineering.
- **CHUTE-GRS1190**: Use if MTOW grows above the 1,050 kg top variant of the GRS 6 800-990, or if Galaxy rates the 800-990 opening load too high at 1,043 kg. +7.2 kg vs the 800-990 system; lower descent rate.
- **CHUTE-GRS1390**: Iteration 3.3 recovery system (MTOW 1,350 kg on the 1,390 kg variant). Same canopy area and packed mass as the 990-1190; higher opening shock (57.4 kN) for the airframe attachment loads.

## Flight control and avionics

| ID | Status | Item | Mass (kg) | Key ratings | Price | Source |
|---|---|---|---|---|---|---|
| FCC-VERONTE4X | **shortlist** | Embention Veronte Autopilot 4x (triple core + optional external 4th) | 0.75 | redundancy: 3 internal cores + optional external core, no single point of failure; assurance: DO-178C / DO-254 DAL B evidence (DAL A ongoing); DO-160G tested | EUR 23,500 | [link](https://www.embention.com/veronte-ecosystem/autopilots/4x-system-redundancy) |
| FCC-CUBE-ORANGEP | alternate | CubePilot Cube Orange+ Standard Set with ADS-B carrier | - | firmware: ArduPilot / PX4; imus: triple redundant IMU; adsb: uAvionix 1090 MHz receiver | USD 350.00 | [link](https://irlock.com/products/cube-orange-plus-standard-set) |
| FCC-PIXHAWK6X | reference | Holybro Pixhawk 6X Standard v2A (PM02D) | 0.105 | imus: triple IMU | USD 422.99 | [link](https://holybro.com/products/pixhawk-6x) |
| FCC-MICROPILOT | reference | MicroPilot MP2128 3X triple-redundant | - |  | quote required | [link](https://www.micropilot.com/) |
| GNSS-HERE4 | **shortlist** | CubePilot Here4 multiband RTK GNSS (x2) | - | bands: multiband L1/L5 | USD 225.00 | [link](https://irlock.com/products/here4-multiband-rtk-gnss) |
| AIRSPEED-MS4525 | **shortlist** | Digital airspeed sensor (MS4525DO) with pitot (x2) | 0.02 |  | USD 49.99 | [link](https://holybro.com/collections/sensors) |
| EFIS-DYNON-HDX7 | **shortlist** | Dynon SkyView HDX 7-inch system (from) | - | includes: configured system, starting configuration | USD 4,909.00 | [link](https://generalaviationnews.com/2026/07/28/the-evolution-of-the-skyview-hdx/) |
| EFIS-G5 | alternate | Garmin G5 standby (experimental) | - |  | USD 1,655.00 | [link](https://www8.garmin.com/aviation/brochures/Experimental%20Pricing%20Sheet%202023.pdf) |
| XPDR-TAILBEACONX | **shortlist** | uAvionix tailBeaconX (Mode S + 1090ES ADS-B Out) | - |  | USD 2,499.00 | [link](https://uavionix.com/tailbeaconX) |
| XPDR-TT21 | alternate | Trig TT21 Mode S transponder | - |  | GBP 2,186.67 | [link](https://g-tlac.com/?p=2180) |
| COM-TY91 | **shortlist** | Trig TY91 VHF COM radio | - |  | GBP 1,477.33 | [link](https://g-tlac.com/?p=2178) |

- **FCC-VERONTE4X**: Only COTS FCC found with published redundancy plus DO-178C/DO-254 evidence at a price a small team can afford. Under an experimental certificate this is engineering evidence, not certification credit.
- **FCC-CUBE-ORANGEP**: For unmanned flight-test and hardware-in-the-loop. Three independent Cubes with a voter would be an in-house redundancy design with no assurance pedigree; use for the uncrewed phase only.
- **FCC-PIXHAWK6X**: Same role as Cube; already used on the E8-S subscale.
- **FCC-MICROPILOT**: Listed for completeness.
- **GNSS-HERE4**: Two units for dissimilar placement.
- **AIRSPEED-MS4525**: FCC airspeed; the pilot display (Dynon) has its own pitot-static ADAHRS.
- **EFIS-DYNON-HDX7**: Independent ADAHRS for the pilot, separate from the FCC sensor set.
- **EFIS-G5**: Standby attitude/airspeed with own battery.
- **XPDR-TAILBEACONX**: Self-contained in a tail-light form factor: no separate antenna; fits the tail between the booms.
- **XPDR-TT21**: Needs a separate GPS source for ADS-B Out.

## Cabin and canopy

| ID | Status | Item | Mass (kg) | Key ratings | Price | Source |
|---|---|---|---|---|---|---|
| CAB-HARNESS | **shortlist** | Hooker 4-point aircraft harness (per seat) | - |  | EUR 519.92 | [link](https://www.aircraftspruce.eu/airframe-parts/seat-belts---harnesses/multipoint-sets/hooker-custom-harnesses.html) |
| CAB-CONFOR | **shortlist** | CONFOR CF-45 (blue) energy-absorbing seat foam | - | size: 1 x 16 x 18 in | USD 43.95 | [link](https://aircraftspruce.com/catalog/pnpages/01-09310.php) |
| CAB-PC-SHEET | **shortlist** | Polycarbonate sheet 0.125 x 48 x 96 in (canopy/windows) | - | thickness_mm: 3.2 | USD 239.99 | [link](https://zoro.com/professional-plastics-clear-gp-polycarbonate-9034-polycarbonate-sheet-0125-x-48-x-96-each-spccl125x48000x96000gp-polycarbonate/i/G000907887) |
| CAB-PETG-SHEET | alternate | PETG sheet 3 mm, 1250 x 2050 mm | - |  | EUR 33.60 | [link](https://www.ultraplast.lv/shop/petg/petg-3-mm) |

- **CAB-HARNESS**: Custom-length 4-point; anchor to the seat/keel structure, not to skins.
- **CAB-CONFOR**: Seat cushions in layered CF-45/CF-47 over a composite seat pan with a crushable honeycomb or foam stroke zone below; pan and stroke zone designed by WP F for the 3 g landing and crash cases.
- **CAB-PC-SHEET**: PC must be dried before thermoforming; better impact strength (bird/rotor debris) than PETG or acrylic.
- **CAB-PETG-SHEET**: Supplier data: forms at ~170 C without pre-drying (orthopedix-france.fr/en/produits/petg-en/petg/) - easiest for in-house drape forming of side windows and test bubbles.

## Landing gear

| ID | Status | Item | Mass (kg) | Key ratings | Price | Source |
|---|---|---|---|---|---|---|
| LG-MATCO-W51LT | alternate | Matco W51LT 5.00-5 wheel and brake kit (pair, no axle) | 4.17 (9.2 lb assembly) | tire: 5.00-5; static_capacity_lb: 1420 | USD 1,096.00 / pair | [link](https://www.aircraftspruce.com/catalog/pnpages/06-00079.php) |
| LG-SKID-REF | reference | Helicopter skid tubes (6061-T6) - certified-helicopter reference | - | material: 6061-T6 | USD 605.00 / skid tube | [link](https://dartaerospace.com/collections/skidtubes-407/skidtubes-float-w-standard-wearplates.oembed) |
| LG-OLEO | **shortlist** | Air/oil (oleo-pneumatic) damper for the pivoting skid legs, 80 mm stroke, 517 mm eye-to-eye (x4) | 1.2 (CAD allowance (LG-DAMP)) | stroke_required_mm: 80; eye_to_eye_extended_mm: 517; peak_force_kN: 6.7; reference_product: FOX 2.0 Factory Series air shock, 1-1/4 in shaft, nitrogen air spring + oil damping | quote required (ref. USD 474.95) | [link](https://www.strutmasters.com/products/fox-factory-inc-980-02-236-fox-2-0-factory-series-air-shock) |

- **LG-MATCO-W51LT**: Only needed if a wheeled (rolling take-off/landing capable) gear is chosen; a VTOL-only skid gear is lighter and simpler. Small castoring ground-handling wheels can be clipped on for hangar moves.
- **LG-SKID-REF**: No COTS ultralight-helicopter skid kit with a published price was found; the skid gear is therefore a make item (straight 6061-T6 skid tubes + outsourced-bent cross tubes, see MANUFACTURING_METHODS.md).
- **LG-OLEO**: WP F phase 3: damper peak force 6.7 kN, 80 mm stroke (reserve drop uses 68 mm). Off-road shocks are not aviation parts: drop-test the gear with the chosen unit; spherical bearings at both eyes.

## Raw materials and hardware

| ID | Status | Item | Mass (kg) | Key ratings | Price | Source |
|---|---|---|---|---|---|---|
| MAT-TUBE-DP-3x72 | **shortlist** | DragonPlate roll-wrapped twill carbon tube 3.0 in ID x 3.125 in OD x 72 in | - | id_mm: 76.2; od_mm: 79.4; wall_mm: 1.59; length_mm: 1829 | USD 386.50 | [link](https://dragonplate.com/carbon-fiber-roll-wrapped-twill-tube-3-id-x-96-gloss-finish) |
| MAT-TUBE-DP-4x96 | **shortlist** | DragonPlate roll-wrapped twill carbon tube ~4 in ID x 96 in thin wall | - | id_mm: 101.6; length_mm: 2438 | USD 645.00 | [link](https://dragonplate.com/carbon-fiber-roll-wrapped-twill-tube-4-id-x-96-thin-wall-gloss-finish) |
| MAT-TUBE-RW-4x72 | alternate | Rock West fabric carbon tube 4.000 x 4.060 x 72 in | - | id_in: 4.0; od_in: 4.06 | USD 396.99 | [link](https://www.rockwestcomposites.com/46324) |
| MAT-TUBE-RW-UD325 | alternate | Rock West unidirectional carbon tube 3.25 x 3.38 x 72 in | - | id_in: 3.25; od_in: 3.38 | USD 614.99 | [link](https://www.rockwestcomposites.com/45503.html) |
| MAT-TUBE-EC | alternate | Easy Composites roll-wrapped carbon tubes, 5-60 mm OD | - | od_range_mm: 5-60 | EUR 41.30 | [link](https://easycomposites.eu/roll-wrapped-carbon-fibre-tube) |
| MAT-CF-FABRIC | **shortlist** | Carbon fabric 3K 2x2 twill 5.7 oz (193 g/m2), 50 in wide | - | areal_g_m2: 193 | USD 39.50 / yard | [link](https://uscomposites.com/carbonpage.html) |
| MAT-RESIN-MGS | **shortlist** | MGS L285 laminating epoxy + H285F / H287S hardener | - | note: aviation laminating system | USD 439.00 / gallon resin | [link](https://www.aircraftspruce.com/catalog/cmpages/mgsresin.php) |
| MAT-RESIN-WEST | alternate | West System 105 resin + 206 slow hardener, 1.2 gal kit | - |  | USD 180.23 / 1.2 gal kit | [link](https://www.westsystem.com/app/uploads/2023/06/2023.05_WS_Vacuum-Bagging-Techniques-Manual.pdf) |
| MAT-FOAM-H80 | **shortlist** | Divinycell H80 PVC foam (10 mm, 2440 x 1220 mm, grooved/perforated) | - | density_kg_m3: 80 | EUR 109.00 / sheet | [link](https://fiberglasssupply.com/sheet-1-2-h-80-divinycell-plain-sheet-48-x-96/) |
| MAT-FOAM-ROHACELL | alternate | Rohacell IG-F 31 PMI foam 48 x 96 x 0.460 in | - | density_kg_m3: 31 | USD 566.99 / sheet | [link](https://www.rockwestcomposites.com/roh-igf31-0460-d.html) |
| MAT-ADH-EA9394 | **shortlist** | Loctite EA 9394 AERO structural paste adhesive, quart kit | - |  | USD 353.10 / quart kit | [link](https://skygeek.com/henkel-hysol-ea-9394-high-temperature-filled-paste-quart-system-as9277016.html) |
| MAT-AL-6061-SHEET | **shortlist** | Aluminium 6061-T6 sheet 0.063 x 24 x 36 in | - |  | USD 62.75 | [link](https://zoro.com/onlinemetals-0063-aluminum-sheet-6061-t6-1242/i/G307151068) |
| MAT-4130 | alternate | 4130 steel tube (Aircraft Spruce, pre-cut lengths) | - | example: 1 x 1 x 0.049 in square, 0.6337 lb/ft | USD 22.50 / see note | [link](https://www.aircraftspruce.com/catalog/pnpages/03-13500.php) |
| MAT-FASTENERS | **shortlist** | AN/MS hardware (AN4 bolts, MS21042 nuts, CherryMAX rivets) | - |  | USD 1.06 / AN4-5 bolt | [link](https://www.airpowerinc.com/an4-5) |
| MAT-UD-CF | **shortlist** | Unidirectional carbon fabric 300 g/m2, 12k (Hyosung H2550), 50 in wide | - | areal_g_m2: 300; width_in: 50 | USD 31.19 / yard | [link](https://www.compositeenvisions.com/Carbon-Fiber-Fabric-Unidirectional-12k-8.8oz-300gsm-Hyosung-H2550) |
| MAT-GLASS-7781 | **shortlist** | E-glass fabric style 7781, 8.95 oz/yd2 (303 g/m2), 50 in | - | areal_g_m2: 303 | USD 13.65 / yard | [link](https://www.aircraftspruce.com/catalog/cmpages/7781.php) |
| MAT-FOAM-H45 | **shortlist** | Divinycell H45 PVC foam (Aircraft Spruce sheets) | - | density_kg_m3: 48; sheets: 2 in 48x96 USD 778.00 (01-12920); 5/8 in 32x48 USD 75.85 (01-12500) | USD 778.00 / 2 in 48x96 sheet | [link](https://aircraftspruce.com/catalog/cmpages/divinycellfoam.php) |
| MAT-FOAM-H100 | **shortlist** | Divinycell H100 1 in x 42 x 85 in plain sheet | - | density_kg_m3: 100 | USD 510.52 / sheet | [link](https://bluewatersupply.com/resources/catalog/2025/13) |
| MAT-FOAM-H80-12 | **shortlist** | Divinycell H80 1/2 in plain sheet 48 x 96 in | - | density_kg_m3: 80 | USD 208.95 / sheet | [link](https://fiberglasssupply.com/sheet-1-2-h-80-divinycell-plain-sheet-48-x-96/) |
| MAT-XPS | **shortlist** | XPS foam board Owens Corning FOAMULAR 250, 2 in x 4 x 8 ft | - | thickness_mm: 50.8 | USD 57.08 / board | [link](https://superarbor.io/products/1631292-owens-corningr-foamularr-250-25-psi-r-10-extruded-polystyrene-foam-board-insulation-2-x-4-x-8-scored-square-edge) |
| MAT-MDF | **shortlist** | MDF 3/4 in x 4 x 8 ft | - |  | USD 48.98 / sheet | [link](https://www.thepricer.org/the-cost-of-plywood/) |
| MAT-G10 | **shortlist** | G10/FR4 sheet 3/16 in x 12 x 24 in | - | thickness_mm: 4.76 | USD 34.85 / sheet | [link](https://www.hanessupply.com/usasealing-bulk-cs-gfr4-30) |
| MAT-CU-STRIP | alternate | Copper bus strip 0.2 x 31 mm for 21700 (per metre) | - |  | USD 8.99 / m | [link](https://www.ebay.com/itm/305567325562) |
| MAT-AL-PLATE | **shortlist** | Aluminium 6061 plate 1/2 x 12 x 24 in (price basis for all 6061 plate/bar) | 6.37 | usd_per_kg: 23.5 | USD 149.99 / plate | [link](https://www.zoro.com/zoro-select-aluminum-plate-6061-24-in-overall-l-12501224/i/G205374453) |
| MAT-AL7075-PLATE | **shortlist** | Aluminium 7075-T651 plate 1-1/2 x 12 x 12 in (price basis for 7075) | 9.9 | usd_per_kg: 27.3 | USD 269.97 / plate | [link](https://www.speedymetals.com/p-2730-1-12-7075-t651-aluminum-plate.aspx) |
| MAT-AL-TUBE | **shortlist** | 6061-T6 round tube (Aircraft Spruce, per ft) | - | 2-1/4 x .125: USD 21.70/ft (03-38310); 3 x .065: USD 23.75/ft (03-38340) | USD 21.70 / ft | [link](https://www.aircraftspruce.com/catalog/mepages/alumtube_6061t6.php) |
| MAT-SEAT-TRACK | **shortlist** | Brownline-style seat track extrusion (05-07172), per inch | - |  | USD 4.65 / inch | [link](https://www.aircraftspruce.com/catalog/pnpages/05-07172.php) |
| MAT-UHMW | **shortlist** | UHMW-PE sheet 3/4 x 12 x 48 in | - |  | USD 147.99 / sheet | [link](https://www.zoro.com/usa-industrials-uhmw-polyethylene-48-l-x-12-w-x-34-thick-bulk-ps-uhmw-355/i/G300437510/) |
| MAT-4130-PLATE | **shortlist** | 4130 alloy steel plate 1/2 in (annealed), size per order | - |  | USD 306.33 / plate | [link](https://www.onlinemetals.com/en/buy/alloy-steel-sheet-plate-4130-annealed) |
| MAT-BAGGING | **shortlist** | Vacuum-bagging consumables (US Composites): nylon bag film 110 in, breather 4 oz 60 in, peel ply 60 in, perforated film 60 in, sealant tape | - | bag_film: USD 4.95/yd (25+); breather_4oz: USD 4.30/yd (25+); peel_ply: USD 5.55/yd (25+); perforated_film: USD 6.50/yd (25+); sealant_tape: USD 7.15/roll 25 ft (10+) | USD 5.55 / yard (peel ply) | [link](https://uscomposites.com/vacuum.html) |

- **MAT-TUBE-DP-3x72**: Boom / spar tube candidate; laminate schedule (UD vs twill) to be confirmed for stiffness. Lead time 10-15 days for options.
- **MAT-TUBE-DP-4x96**: ~100 mm boom. Wall must be thickened (in-house UD over-wrap) if FEA requires.
- **MAT-TUBE-RW-4x72**: Thin wall (0.03 in); stiffness to be checked.
- **MAT-TUBE-RW-UD325**: High-bending-stiffness lay-up, spar candidate.
- **MAT-TUBE-EC**: Struts, pylons, tail-boom bracing; does not cover 76-120 mm.
- **MAT-CF-FABRIC**: Skins and local reinforcements; buy UD carbon tape separately for spar caps (quote).
- **MAT-RESIN-MGS**: Primary laminating resin for structure; cure/post-cure schedule from the manufacturer TDS, recorded per batch.
- **MAT-RESIN-WEST**: Tooling, moulds, fillets and non-primary parts.
- **MAT-FOAM-H80**: Cabin floor, bulkheads, seat pans, tail panels. Epoxy-compatible, CNC-routable.
- **MAT-FOAM-ROHACELL**: Lighter, higher temperature (post-cure friendly) but ~3x cost of PVC; for weight-critical panels only.
- **MAT-ADH-EA9394**: Metal-to-composite fittings (boom clamps, motor mounts). Plexus MA530: no published price found - quote.
- **MAT-AL-6061-SHEET**: Plate (6.35-25 mm) for motor mounts and boom clamps: quote by cut size from Online Metals/Metals Depot.
- **MAT-4130**: Only if the outsourced welded cabin cage option is taken.
- **MAT-FASTENERS**: Budget per aircraft set in pass 2 from the CAD fastener count.
- **MAT-UD-CF**: Spar caps, boom UD over-wrap, keel/frame straps (CAD settings call for UD 300 g/m2).
- **MAT-GLASS-7781**: Fuselage shell, fairings, hatches, tapes.
- **MAT-FOAM-H45**: Main-spar box foam W-SPM-F, 15 mm strip W-SPM-S.
- **MAT-FOAM-H100**: Seat crush blocks SEAT-EA (bonded layers).
- **MAT-FOAM-H80-12**: Nose crush block NOSE-EA (stacked).
- **MAT-XPS**: Wing/tail/control-surface cores (epoxy only) and the moldless shell plugs (laminated blocks). Building-supply product: check density and adhesion on coupons.
- **MAT-MDF**: Cap jigs, hot-wire templates, cradles, canopy plug.
- **MAT-G10**: Cell holder plates (CAD: 5 mm G10, waterjet-cut); 3/16 in is the nearest stock thickness - confirm with WP G.
- **MAT-CU-STRIP**: CAD calls for nickel-plated copper laser-welded strips; buy plated stock in bulk by quote.
- **MAT-AL-PLATE**: USD/kg derived (149.99 / 6.37 kg) and applied to other 6061 plate and bar (estimate).
- **MAT-AL7075-PLATE**: Wing-root lugs and seat fittings (12-14 mm plate by quote).
- **MAT-AL-TUBE**: Skids (CAD 60 x 3.2 mm: nearest inch stock 2-1/4 x 0.125), gear legs (CAD 76 x 2.0: 3 x 0.083 by quote), pylons 100 x 1.6 by quote.
- **MAT-SEAT-TRACK**: SR seat rails 4 x 600 mm.
- **MAT-UHMW**: Skid shoes LG-SHOE, skid end plugs.
- **MAT-4130-PLATE**: Parachute fittings W-CHUTE-FIT x2, CH-ATT-R.
- **MAT-BAGGING**: Quantities from the bagged laminate area (bom/build_bom.py).

## Notes on certification realities and supply

- **Flight controller.** No COTS flight controller in this catalog is certified for a crewed eVTOL. Veronte 4x offers
  DO-178C/DO-254 DAL B evidence and triple-core hardware; Pixhawk/Cube-class units are open-source hobby/industrial
  hardware without design assurance. Under an experimental (FAA amateur-built/R&D, or EASA permit) route these are
  engineering choices, not certification credit; FAA AC 21.17-4 (powered-lift, 18 Jul 2025) and EASA SC-VTOL set the
  expectations a type-certificated product would face.
- **Export licensing.** From 18 Nov 2026 China requires export licences for heavy-lift drone motors (>=48 V, >=3 kW,
  >=3 kW/kg, <=3000 rpm), matching ESCs and carbon blades longer than 30 in from the rotation axis
  ([DroneXL](https://dronexl.co/2026/10/19/china-drone-export-controls-motors-props-november-18/)); T-Motor is also on
  the US Entity List ([DroneXL](https://dronexl.co/2024/12/30/china-drone-export-controls)). This is why the baseline
  uses European motors/inverters/propellers and keeps T-Motor/MAD/Hobbywing as alternates.
- **EMRAX transition.** EMRAX datasheets v1.7 state that the 188/208/228/268/348 range will gradually go out of
  production in favour of a next-generation range with the same envelope; quote the successor.
- **Parachute at low height.** All ballistic systems need height to inflate; the hover/transition phase near the
  ground is not covered and must be handled by the one-motor-out and dual-bus requirements.
- **Prices** are single listings on the date checked; volume, tax, shipping, duties and hazmat fees are excluded
  unless stated. The final BOM (pass 2) will refresh them.
