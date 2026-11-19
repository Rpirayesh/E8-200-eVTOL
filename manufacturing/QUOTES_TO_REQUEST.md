# Vendor quotes to request (E8-200 prototype, iteration 3.3)

The items below carry estimates in [bom/BOM.md](../bom/BOM.md). Together they are about two thirds of the cash total,
so these quotes decide the real budget. For every quote, also ask for:
- unit price at quantity 1 and at the quantity shown;
- lead time;
- warranty terms for a crewed experimental aircraft;
- export classification (ECCN / EU dual-use entry) and the documents for delivery to the US;
- the datasheet or drawing revision the quote is based on.

Attach `design/selected_design.json` (iteration 3.3, MTOW 1,350 kg), the relevant STEP files from `cad/parts/`, and the
duty table in `validation/parts/results_tables.md` (section "Final design").

## 1. EMRAX (SI): 8 x EMRAX 268, liquid cooled, lift motors (BOM USD 96 k estimate) - priority 1

1. **Winding for our bus.** The bus is 175s Li-ion: 735 V at full charge, 630 V nominal, about 525 V loaded, and 492 V
   with one of four packs out. Which winding do you recommend: HV, MV, or a custom one?
   - The datasheet MV winding has a no-load KV of 8.68 rpm/V. At full charge that gives about 6,400 rpm no-load, above
     the 4,500 rpm limiting speed.
   - We need at least 5.9 rpm/V to reach the one-motor-out speed (2,289 rpm) at 492 V.
   - Please give KV, KT, phase resistance and peak/continuous current for the recommended winding, and say whether the
     inverter must limit speed or use field weakening.
2. **Duty points per motor.** Direct drive of a 1.85 m two-blade rotor:

   | Case | Power | Torque | Speed | Duration |
   |---|---|---|---|---|
   | Hover | 39.9 kW | 202 N m | 1,889 rpm | 120 s per flight |
   | One motor out, 1.0 g | 72.1 kW | 301 N m | 2,289 rpm | up to 60 s |
   | One motor out, flare | 71.0 kW | 296 N m | 2,289 rpm | about 10 s |

   The hover torque is within 1.6 % of the 205 N m liquid-cooled continuous rating. Please confirm the continuous
   rating at 40 C ambient and the coolant flow and temperature it needs. Please also give the time limits at 300 N m.
3. **Axial and overhung loads.** Rotor thrust is up to 2,511 N in the OEI flare, and the rotor is 1.85 m. Please give the
   maximum axial load, bearing life at the 1,710 N hover thrust, and the allowed overhung mass and inertia.
4. **Mounting and transition.**
   - Mounting drawing: stator bolt circle and coolant-port positions. Our MP-EMX adapter ring depends on these.
   - The 188-348 range is going out of production. Which next-generation model and price apply, and when?
5. **Price and lead time.** For 8 motors with resolvers.

## 2. MGM COMPRO (CZ): 2 x REB 90 pushers and 10 x HBCi 400800 inverters (BOM about USD 92 k) - priority 2

1. **REB 90 continuous torque.** Please send the continuous-torque curve from 1,800 to 2,200 rpm at 25 C and 40 C
   ambient, air-cooled and hybrid-cooled.
   - Cruise duty per pusher is 53 kW shaft at 2,074 rpm, which is 244 N m.
   - Our sizing assumes 60 kW continuous, about 276 N m at 2,074 rpm, to keep its 10 % margin. Your page gives
     60-70 kW and 300 N m but no curve.
   - Please give the S1/S2 ratings and the time limits at 280 and 300 N m.
2. **Winding.** Which REB 90 winding suits a 525-735 V bus? Please give KV, KT and the axial-load limit. The propeller is a
   1.75 m two-blade with up to 2,305 N thrust.
3. **Inverters.** 10 x HBCi 400800 (8 for EMRAX lift motors, 2 for REB 90).
   - Please confirm the HBCi controls the EMRAX 268: resolver input, current and speed limiting.
   - Is there a smaller 800 V unit (about 100 kW peak, 200 A)?
   - Please give mass, cooling, CAN protocol and the redundancy options.
4. **Price, spares and lead time.**

## 3. Galaxy GRS (CZ): GRS 6 1200-1390 SDS/FF (BOM USD 17,000 estimate) - priority 3

1. **Variant and loads.** MTOW is **1,350 kg**: please confirm the 1,390 kg variant.
   - Your page lists 57.4 kN at 1,390 kg.
   - Please give the opening load at 1,350 kg at 172 km/h cruise and at our dive speed.
   - Please give the minimum rescue height in hover and at low speed.
2. **Installation.** Bridle/riser set to three hard points: CH-ATT-R, plus W-CHUTE-FIT on the left and right. Please advise
   on the canister mounting (CH-CRADLE with forward post) and the firing direction for our drawing.
3. **Logistics.** Price, dangerous-goods shipping to the US, US dealer, and the rocket and repack intervals.

## 4. E-PROPS (FR): lift rotors and pusher propellers (BOM about USD 14.3 k estimate) - priority 4

1. **Lift rotors.** 8 x ground-adjustable carbon two-blade rotors at **1.85 m**, matched pairs (4 CW + 4 CCW).
   - Duty: 1,889 rpm in hover at 1,710 N; 2,289 rpm and 2,511 N in the OEI flare; 72 kW maximum.
   - Your 2-blade rating is 86 kW; please confirm, or quote 3 blades.
   - Please give the rpm limit, fatigue data, blade mass and inertia, and the balance/track tolerance.
2. **Pusher propellers.** 2 x **1.75 m** two-blade, both the same rotation (one part number).
   - Duty: 53 kW at 2,074 rpm in cruise at 172 km/h, with up to 2,305 N thrust.
   - REB 90 flange; ground-adjustable pitch about 22 deg.
3. **Crewed VTOL use.** Your manned-aircraft warranty excludes VTOL use. Please give the conditions for this use, plus price,
   lead time and spare blades.

## 5. FOX (or an aircraft-oleo supplier): gear dampers (BOM about USD 1,900 estimate)

1. 4 x air/oil dampers, 80 mm stroke, 517 mm eye-to-eye extended, spherical bearings at both eyes. WP F will update the
   peak force and static load for 1,350 kg. Please give force-stroke curves, valving, price and service interval.

## 6. Coroplast / LEONI: aluminium HV cable (BOM about USD 2,100 estimate)

1. About 105 m of single-core screened aluminium-conductor HV cable rated 1,000 VDC, 35 mm2 class, with bimetal lugs and
   tooling. Please give mass per metre and the bend radius.

## 7. Battery cells and pack parts

1. **Cells.** Molicel P50B, **3,500 cells** plus 5 % spares, lot-traceable, priced at 3,700 pcs. Please confirm the 60 A
   rating conditions; the one-pack-out case is about 50 A per cell (validation/parts).
2. **Strip and welding.** Nickel-plated copper strip in bulk, and laser welding for 4 packs if we outsource it.
3. **Mica liner.** Mica fire-liner sheet for 4 battery boxes (no published price found).
4. **Precharge.** Precharge relays and resistors rated for 735 V.

## 8. Embention: Veronte Autopilot 4x (BOM EUR 23,500 reseller figure)

1. Price direct and through the US distributor: triple core, ADS-B option, external 4th core.
2. US export licence.
3. Support package for a crewed experimental eVTOL. The rotor rpm cap is implemented in the flight-control software; can
   Veronte enforce per-rotor rpm limits?
4. CAN interface to 10 MGM HBCi inverters.

## 9. Raw-material and service quotes

- **Carbon tubes.**
  - Tail spar HT-SPAR: 50 x 2 mm, 2.95 m or longer (Rock West or DragonPlate custom length).
  - Booms: 4 in ID DragonPlate, quantity per the cut list in BOM.md.
- **6061-T6 tube.**
  - Gear legs: 3 x 0.095 in. The CAD uses this size, but `design/geometry.json` still gives a 5.82 mm wall.
  - Skids: 2-1/4 x 0.125 in, 3.21 m long, so longer than the 12 ft stock.
  - Pylons: 100 x 1.6 mm.
- **7075-T651 plate.** 15 and 18 mm for W-FIT-MS, CH-ATT-R, W-CHUTE-FIT and LG-DUP, plus CH-CRADLE stock (job shop: taller
  than our 150 mm mill Z).
- **Foam.** Plain Divinycell H80 10 mm sheets.
- **Waterjet.** Battery-box flat patterns (4), lids, IP panel, G10 holder plates.
- **Bending, forming and finishing.**
  - Tube bending: 4 gear legs.
  - Thermoforming: canopy.
  - Alodine/anodize and paint.
