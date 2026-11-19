#!/usr/bin/env python3
"""Build bom/catalog.json and bom/CATALOG.md from one data table.

E8-200 work package P (parts, materials, BOM, manufacturing), pass 1: COTS catalog.

Conventions
-----------
* Every number has a source URL, or its price/mass block is typed "estimate" with the basis stated.
* Prices are kept in the currency in which they were published (no FX conversion is applied here);
  "type" says what kind of price it is: list | retail | dealer | reseller | quote_required | estimate.
* checked: date on which the source page was read by the team (all 2026-11-12 unless stated).
* status: shortlist (preferred for the baseline) | alternate | reference (benchmark or fallback only)
  | not_recommended (kept so the decision is traceable).

Run:  python3 bom/build_catalog.py
"""
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
CHECKED = "2026-11-12"


def P(value, currency="USD", unit="each", type_="retail", source=None, note=""):
    return {"value": value, "currency": currency, "unit": unit, "type": type_, "source": source, "note": note}


def Q(estimate=None, currency="USD", unit="each", basis="", source=None):
    """Quote required, with the best published estimate (or None) and its basis."""
    return {"value": None, "currency": currency, "unit": unit, "type": "quote_required",
            "estimate": estimate, "estimate_basis": basis, "source": source}


ITEMS = []


def add(**kw):
    kw.setdefault("checked", CHECKED)
    kw.setdefault("notes", "")
    ITEMS.append(kw)


# =====================================================================================
# 1. LIFT / PUSHER MOTORS
# =====================================================================================
MGM_REB50 = "https://mgm-compro.com/electric-motor/reb-50-50-kw/"
MGM_REB90 = "https://mgm-compro.com/electric-motor/reb-90-80-kw/"
MGM_REB30 = "https://pdf.aeroexpo.online/pdf/mgm-compro/reb-30-40kw-electric-motor/171210-21274.html"
MGM_REB30_B = "https://www.aeroexpo.online/prod/mgm-compro/product-171210-35928.html"
EMRAX_188 = "https://emrax.com/wp-content/uploads/2025/03/EMRAX-188_datasheet_v1.7.pdf"
EMRAX_208 = "https://emrax.com/wp-content/uploads/2025/03/EMRAX-208_datasheet_v1.7.pdf"
EMRAX_228 = "https://emrax.com/wp-content/uploads/2025/03/EMRAX-228_datasheet_v1.7.pdf"
EMRAX_268 = "https://emrax.com/wp-content/uploads/2025/08/EMRAX-268_datasheet_v1.7_version_C.pdf"
EMRAX_QUOTE = "https://emrax.com/get-a-quote/"
TM_U15XXL = "https://shop.tmotor.com/products/u15xxl-manned-aircraft-combo"
TM_U15XXL_MOTOR = "https://shop.tmotor.com/products/u15xxl-manned-aircraft-drone-motor"
TM_COLLECTION = "https://shop.tmotor.com/collections/manned-aircraft-power"
TM_S150 = "https://uav-en.tmotor.com/news/61.html"
MAD_M90 = "https://www.madcomponentsusa.com/m90c60-eee-manned-drone-motor.html"
MAD_M90_OZ = "https://ozrobotics.com/shop/mad-m90c60-eee-manned-drone-motor-9kv-big-thrust-drone-motor-for-large-manned-multi-rotor-aircraft/"
HW_P50M = "https://www.hobbywing.com/en/products/p50m"
GEIGER_AZ = "https://aeroenginesaz.com/en/brand_geiger-engineering"
PLETT = "https://sustainableskies.org/plettenbergs-new-motors-ready-for-real-airplanes/"
PLETT_PRICE = "https://endless-sphere.com/sphere/threads/what-motor-would-you-choose-for-a-25kw-paramotor-setup.75715/"
H3X = "https://www.h3x.tech/products/hpdm-180r"
H3X_180D = "https://www.h3x.tech/products/hpdm-180d"
REB90_WIKI = "https://en.wikipedia.org/wiki/Rotex_Electric_REB_90"
EXPORT_RULE = "https://dronexl.co/2026/10/19/china-drone-export-controls-motors-props-november-18/"
ENTITY_LIST = "https://dronexl.co/2024/12/30/china-drone-export-controls"

MOTOR_EST = ("No published price. Estimate from published prices of motors in the same 30-60 kW class: "
             "MAD M90C60 EEE USD 5,000 (madcomponentsusa.com) and T-Motor U15XXL USD 1,999 (shop.tmotor.com); "
             "European aviation-grade motors are expected at or above the upper figure.")

add(id="MOT-REB30", category="motor", role=["lift"], status="shortlist",
    name="MGM COMPRO REB 30 (40 kW) outrunner, air or hybrid cooled", maker="MGM COMPRO (CZ)",
    mass_kg=7.7,
    ratings={"peak_power_kW": 40, "cont_power_kW": "25-30", "max_torque_Nm": 150, "rpm_range": "1500-4000",
             "voltage_V": "63-800 (winding specific)", "diameter_mm": 266, "kv": "winding specific, not published",
             "cooling": "air or hybrid air+fluid", "rating_ambient_C": 25},
    price=Q(estimate=[4000, 7000], basis=MOTOR_EST),
    sources=[MGM_REB30, MGM_REB30_B],
    notes="Direct-drive torque class suits 1.8-2.0 m rotors at 1,500-2,000 rpm. Same frame family as REB 50/60/90, "
          "so the lift and pusher motors can share mounts, sensors and supplier. Ratings from the manufacturer's "
          "catalogue sheet hosted on aeroexpo; confirm against the current MGM datasheet and ask for the winding "
          "matched to a 94s (~340 V nominal, 395 V max) bus. Passes the one-motor-out check to 700 kg MTOW with 8 rotors of 1.8-1.9 m (validation/parts).")

add(id="MOT-REB50", category="motor", role=["lift", "pusher"], status="shortlist",
    name="MGM COMPRO REB 50 (50 kW) outrunner", maker="MGM COMPRO (CZ)",
    mass_kg=12.0,
    ratings={"peak_power_kW": 50, "cont_power_kW": "30-40 (max continuous)", "max_torque_Nm": 200,
             "rpm_range": "1500-4000", "voltage_V": "400-800", "diameter_mm": 266.8,
             "cooling": "air or hybrid fluid/air", "sensors": "sensored or sensorless"},
    price=Q(estimate=[5000, 9000], basis=MOTOR_EST),
    sources=[MGM_REB50],
    notes="Lift motor for MTOW 700-900 kg with 8 rotors of ~1.9 m (validation/parts); also the pusher if cruise needs <= 30 kW "
          "continuous (single motor type). Needs a 400-800 V bus (~180s). Previous E8 iteration screened it at 30 kW continuous.")

add(id="MOT-REB60", category="motor", role=["lift", "pusher"], status="shortlist",
    name="MGM COMPRO REB 60 (60 kW) - E8-200 lift and pusher motor (x10)", maker="MGM COMPRO (CZ)", mass_kg=15.3,
    mass_note="excluding the optional encoder (+65 g)",
    ratings={"peak_power_kW": 60, "max_torque_Nm": 250, "max_rpm": 4000, "voltage_V": "400-800",
             "cont_power_kW": "35-45 (summary block)", "rpm_range": "1500-4000", "diameter_mm": 270.8,
             "table_25C_peak_power_kW": 33.5, "table_25C_cont_power_kW": 25, "table_25C_peak_torque_Nm": 133,
             "table_25C_cont_torque_Nm": 95, "table_kv_no_load_rpm_per_V": 42.5, "table_kt_Nm_per_Arms": 0.313,
             "table_max_phase_current_A": 700, "phase_resistance_mOhm": 3.8, "rotor_inertia_kgm2": 0.03,
             "max_axial_load_N": 2500, "bearings": "6205 2RS1 / 6204 2Z", "max_operating_temp_C": 130,
             "min_cable_mm2": 25, "cooling": "air or hybrid (fluid/air)", "sensors": "U,V,W hall; PT1000; optional abs. encoder"},
    price=Q(estimate=[6000, 10000], basis=MOTOR_EST),
    sources=["https://mgm-compro.com/electric-motor/reb-60-60-kw/"],
    notes="The MGM page carries two inconsistent rating sets: the summary block (60 kW, 250 Nm, 35-45 kW continuous, "
          "400-800 V) used by WP D, and a detailed table 'valid for 25 C' (33.5 kW peak, 25 kW continuous, 133 Nm peak, "
          "95 Nm continuous, KV 42.5 rpm/V, 700 A). The table KV is a low-voltage winding (4,000 rpm at ~94 V); the "
          "E8-200 175s bus needs a no-load KV of at least ~5.7 rpm/V (validation/parts). The design case needs 248 Nm and 56 kW in the one-motor-out "
          "flare: the winding, torque and continuous rating must be confirmed in the MGM quote before ordering "
          "(manufacturing/QUOTES_TO_REQUEST.md). Max axial load 2,500 N vs 2,148 N rotor thrust in the OEI flare.")

add(id="MOT-REB90", category="motor", role=["pusher"], status="alternate",
    name="MGM COMPRO REB 90 (80 kW)", maker="MGM COMPRO (CZ)", mass_kg=23.8,
    ratings={"peak_power_kW": 80, "cont_power_kW": "60-70", "max_torque_Nm": 300, "rpm_range": "1500-4000",
             "voltage_V": "400-800", "diameter_mm": 270.2},
    price=Q(estimate=[8000, 14000], basis=MOTOR_EST),
    sources=[MGM_REB90, REB90_WIKI],
    notes="Pusher option if cruise power exceeds ~40 kW continuous. Wikipedia lists the same REB 90 under "
          "Rotex Electric at 20 kg dry; the MGM page (23.8 kg) is used here.")

add(id="MOT-EMRAX188", category="motor", role=["pusher"], status="alternate",
    name="EMRAX 188 MV (axial flux)", maker="EMRAX d.o.o. (SI)", mass_kg=7.6,
    mass_note="7.1 AC / 7.9 LC / 7.6 CC",
    ratings={"peak_power_kW": "60 @ 6500 rpm (30 s)", "cont_power_kW": "23 AC / 29 LC / 33 CC",
             "peak_torque_Nm": 100, "cont_torque_Nm": "34 AC / 43 LC / 48 CC", "limit_rpm": 8000,
             "kv_no_load_rpm_per_V": 29.58, "kv_nominal_load": 22.83, "peak_current_Arms": 310,
             "voltage_for_peak_V": 390, "variants": "HV 660 V / MV 390 V / LV 160 V"},
    price=Q(basis="No published price; EMRAX sells by quotation.", source=EMRAX_QUOTE),
    sources=[EMRAX_188, "https://emrax.com/e-motors/emrax-188/"],
    notes="Too little torque for direct drive of a lift rotor (48 Nm continuous). Datasheet v1.7 states the "
          "188/208/228/268/348 range is being replaced by a next-generation range with the same envelope.")

add(id="MOT-EMRAX208", category="motor", role=["pusher"], status="alternate",
    name="EMRAX 208 MV (axial flux)", maker="EMRAX d.o.o. (SI)", mass_kg=10.0,
    mass_note="9.4 AC / 10.3 LC / 10.0 CC",
    ratings={"peak_power_kW": "86 @ 6000 rpm (30 s)", "cont_power_kW": "33 AC / 47 LC / 52 CC",
             "peak_torque_Nm": 150, "cont_torque_Nm": "53 AC / 75 LC / 83 CC", "limit_rpm": 7000,
             "kv_no_load_rpm_per_V": 25.02, "kv_nominal_load": 18.94, "kt_Nm_per_Arms": 0.38,
             "peak_current_Arms": 400, "cont_current_LC_Arms": 220, "voltage_for_peak_V": 420},
    price=Q(basis="No published price; EMRAX sells by quotation.", source=EMRAX_QUOTE),
    sources=[EMRAX_208, "https://emrax.com/e-motors/emrax-208/"],
    notes="Continuous power is reached only near 6000 rpm; at a 2,400 rpm pusher the 83 Nm continuous torque "
          "gives about 21 kW. Dual-winding (2x UVW) version available for inverter redundancy.")

add(id="MOT-EMRAX228", category="motor", role=["pusher"], status="alternate",
    name="EMRAX 228 MV (axial flux)", maker="EMRAX d.o.o. (SI)", mass_kg=13.2,
    mass_note="12.9 AC / 13.5 LC / 13.2 CC",
    ratings={"peak_power_kW": "124 @ 5500 rpm (30 s)", "cont_power_kW": "48 AC / 68 LC / 75 CC",
             "peak_torque_Nm": 220, "cont_torque_Nm": "83 AC / 118 LC / 130 CC", "limit_rpm": 6500,
             "kv_no_load_rpm_per_V": 15.53, "kv_nominal_load": 12.05, "peak_current_Arms": 360,
             "cont_current_LC_Arms": 180, "voltage_for_peak_V": 630},
    price=Q(basis="No published price; EMRAX sells by quotation.", source=EMRAX_QUOTE),
    sources=[EMRAX_228, "https://emrax.com/e-motors/emrax-228/"],
    notes="Direct-drive pusher at ~2,400 rpm: 130 Nm continuous -> ~33 kW, 220 Nm peak -> ~55 kW.")

add(id="MOT-EMRAX268", category="motor", role=["pusher"], status="reference",
    name="EMRAX 268 MV (axial flux)", maker="EMRAX d.o.o. (SI)", mass_kg=21.9,
    mass_note="21.4 AC / 22.3 LC / 21.9 CC",
    ratings={"peak_power_kW": "210 @ 4250 rpm (30 s)", "cont_power_kW": "64 AC / 91 LC / 101 CC",
             "peak_torque_Nm": 500, "cont_torque_Nm": "144 AC / 205 LC / 226 CC", "limit_rpm": 4500,
             "kv_no_load_rpm_per_V": 8.68, "peak_current_Arms": 500, "cont_current_LC_Arms": 220},
    price=Q(basis="No published price; EMRAX sells by quotation.", source=EMRAX_QUOTE),
    sources=[EMRAX_268],
    notes="Oversized for this aircraft; kept as the upper bound of the direct-drive pusher range.")

add(id="MOT-U15XXL", category="motor", role=["lift"], status="alternate",
    name="T-Motor U15XXL KV29 (24S) manned-aircraft motor", maker="T-Motor (CN)", mass_kg=5.13,
    mass_note="with cable",
    ratings={"kv": 29, "voltage": "24S LiPo (~100 V)", "config": "36N42P", "shaft_mm": 25,
             "peak_current_A": "210 (80 s)", "internal_resistance_mOhm": 20,
             "bench_max": "101.4 kgf, 20.09 kW, 209 A, 2203 rpm at 96 V with NS62x24",
             "bench_67kgf": "67.6 kgf, 10.61 kW, 109 A, 1800 rpm",
             "coil_temp_note": "184 C after 1 min full throttle at 32 C ambient (not a continuous rating)"},
    price=P(1999.00, source=TM_U15XXL_MOTOR, type_="list",
            note="Kit (motor + Thunder 300A ESC + propeller) listed from USD 5,997."),
    sources=[TM_U15XXL, TM_U15XXL_MOTOR, TM_COLLECTION, EXPORT_RULE],
    notes="Lowest-cost published option and complete bench data, but a 100 V system needs ~4x the current of a "
          "400 V bus; usable only for an MTOW near the low end with 8 rotors. Export licensing: China requires "
          "licences from 18 Nov 2026 for drone motors >=48 V, >=3 kW, >=3 kW/kg, <=3000 rpm, their ESCs and "
          "large carbon blades; this motor meets all four criteria. T-Motor is also on the US Entity List.")

add(id="MOT-TM-S150", category="motor", role=["lift"], status="alternate",
    name="T-Motor S150 high-power heavy-load drive system (400 V)", maker="T-Motor (CN)", mass_kg=9.1,
    ratings={"max_power_kW": 42, "voltage_V": 400, "max_pull_kgf": 165},
    price=Q(basis="Announced at AERO Asia 2025; no price published.", source=TM_S150),
    sources=[TM_S150, EXPORT_RULE],
    notes="Right power class and voltage for 6-8 lift rotors, but only show-announcement data; same export "
          "licensing and entity-list exposure as other T-Motor heavy-lift products.")

add(id="MOT-MAD-M90C60", category="motor", role=["lift"], status="alternate",
    name="MAD Components M90C60 EEE V1.0, 9 KV manned-drone motor", maker="MAD Components (CN)", mass_kg=12.7,
    mass_note="reseller figure (14 kg boxed)",
    ratings={"kv": 9, "pole_pairs": 21, "size_mm": "257 x 123", "shaft_mm": 35,
             "sustained_power_kW": "up to 45 (MAD USA)", "max_power_kW": "55.6 (reseller)",
             "max_current_A": "150.8 (reseller)", "voltage_V": "400 (reseller)",
             "recommended_lift_kgf": "70-100", "max_thrust_kgf": "200.1 (reseller)",
             "insulation": "220 C wire, 180 C magnets"},
    price=P(5000.00, source=MAD_M90, type_="dealer", note="'As low as' price on MAD Components USA."),
    sources=[MAD_M90, MAD_M90_OZ, EXPORT_RULE],
    notes="Published price and 400 V rating; mass and power partly from a reseller. Matching ESC/inverter must be "
          "sourced separately (an MGM HBCi 400400 class unit fits the voltage). Export licensing risk as above.")

add(id="MOT-HW-P50M", category="motor", role=["lift"], status="not_recommended",
    name="Hobbywing P50M propulsion system (400 V, 9/11 KV)", maker="Hobbywing (CN)", mass_kg=6.2,
    mass_note="system incl. ESC and prop; motor 4.25 kg, ESC 1.2 kg",
    ratings={"input_V": "280-480 (400 rated)", "official_thrust_per_axis_kgf": 50, "max_thrust_kgf": 116,
             "esc_current_A": "40 cont / 80 peak (3 s)", "props": "MSC 64x23 or USC 54x23"},
    price=Q(basis="No price on the manufacturer page.", source=HW_P50M),
    sources=[HW_P50M],
    notes="50 kgf official per-axis rating would need 12-18 rotors at 600-900 kg MTOW; the 40 A continuous ESC "
          "limits sustained power to ~16 kW at 400 V.")

add(id="MOT-GEIGER-HPD32D", category="motor", role=["pusher"], status="reference",
    name="Geiger Engineering HPD 32D (duplex)", maker="Geiger Engineering (DE)", mass_kg=12.0,
    ratings={"power_kW": "40 @ 2200 rpm", "note": "HPD 50D: 60 kW @ 2200 rpm, 15 kg; HPD 25D: 30 kW @ 1950 rpm, 10 kg"},
    price=Q(basis="No published price found.", source=GEIGER_AZ),
    sources=[GEIGER_AZ],
    notes="Third-party data (aeroenginesaz.com, last updated 2018); duplex winding gives inherent drive "
          "redundancy. Current availability to be confirmed with Geiger.")

add(id="MOT-PLETT-NOVA30", category="motor", role=["pusher"], status="reference",
    name="Plettenberg Nova 30", maker="Plettenberg (DE)", mass_kg=5.0,
    ratings={"power_kW": 30, "voltage_V": 120, "torque_Nm": 105, "peak_eff": 0.93},
    price=Q(estimate=2101, currency="EUR", basis="Old forum-quoted price for the smaller Nova 15 (air cooled); "
                                                  "Nova 30 price not published.", source=PLETT_PRICE),
    sources=[PLETT],
    notes="Paramotor/ultralight class, 120 V; low voltage and 30 kW cap make it a fallback only.")

add(id="MOT-H3X-180R", category="motor", role=["pusher"], status="not_recommended",
    name="H3X HPDM-180R (integrated motor-drive with reduction)", maker="H3X (US)", mass_kg=16.0,
    ratings={"power_kW": 180, "output_rpm": "~2985", "integrated_inverter": True,
             "note": "HPDM-180D direct drive: 13 kg, 86 Nm continuous, 20,000 rpm"},
    price=Q(basis="No published price.", source=H3X),
    sources=[H3X, H3X_180D],
    notes="Integrated inverter saves mass but is 2-4x oversized and a single-source development product.")

add(id="MOT-OTHERS", category="motor", role=["lift", "pusher"], status="reference",
    name="Hacker, Rotex Electric, Saluqi, Sky-Watcher, Scorpion large (screened)", maker="various", mass_kg=None,
    ratings={},
    price=Q(basis="No current 25-80 kW product data found in Nov 2026 searches."),
    sources=["https://en.wikipedia.org/wiki/Rotex_Electric_REB_90", "https://www.lindinger.at/en/AIRPLANES/ELECTRIC-POWERPLANTS/Motors/HACKER-Q80-7L-V2-KV155-Bruhsless-Motor/9795259"],
    notes="Hacker's published Q-series are RC-scale (Q100-5L 2.3 kg, no kW rating for aircraft use). The REB "
          "line marketed as 'Rotex Electric' is the MGM COMPRO REB family listed above. No manufacturer data was "
          "found for 'Saluqi' or a 'Sky-Watcher' aviation motor; Scorpion's largest motors are below 15 kW. "
          "These are not carried further.")

# =====================================================================================
# 2. INVERTERS / ESCs
# =====================================================================================
add(id="INV-HBCI100400", category="inverter", role=["lift"], status="shortlist",
    name="MGM COMPRO HBCi 100400 (400 V, 100 A)", maker="MGM COMPRO (CZ)", mass_kg=1.8,
    mass_note="cold-plate version; 2.3 kg fluid cooler; 2.3-2.7 kg air-cooled",
    ratings={"voltage_V": "120-400 (28-96 Li-ion cells)", "cont_current_A": "100 fluid / 80 KGR air / 60 KEA300 air",
             "peak_power_kW": "40 (air, headline) / 50 short-time (table)", "cont_power_kW": 25,
             "logic_supply_V": "11-25", "comms": "CAN, RS-485, RS-232 TTL, logic I/O",
             "redundancy": "4-CPU layout; dual/quad-controller architectures, multi-winding motors"},
    price=Q(estimate=[2000, 4000], basis="No published price. Estimate between the published T-Motor Thunder "
                                         "300A (USD 1,599) and Cascadia CM200DX (USD 7,202-8,700) prices, scaled "
                                         "to a 25-40 kW unit."),
    sources=["https://mgm-compro.com/controllers-inverters-escs/hbci-100400/",
             "https://mgm-compro.com/controllers-inverters-escs/"],
    notes="Partner for REB 30 on a 94s bus (395 V max; 96s would reach 403 V). 100 A continuous only with fluid cooling: plan "
          "a cold plate in the boom/pylon or accept the 80 A air-cooled rating.")

add(id="INV-HBCI400400", category="inverter", role=["lift", "pusher"], status="alternate",
    name="MGM COMPRO HBCi 400400 (400 V, 400 A)", maker="MGM COMPRO (CZ)", mass_kg=4.0,
    ratings={"voltage_V": "up to 400", "current_A": 400, "peak_power_kW": 200, "cont_power_kW": 160,
             "redundancy": "4-CPU layout"},
    price=Q(estimate=[4000, 8000], basis="No published price; estimate by analogy with Cascadia CM200DX listings."),
    sources=["https://mgm-compro.com/controllers-inverters-escs/hbci-400400/"],
    notes="Oversized for one lift motor; suits the pusher (EMRAX 228/REB 50 at 400 V) or MAD M90C60.")

add(id="INV-HBCI400800", category="inverter", role=["lift", "pusher"], status="shortlist",
    name="MGM COMPRO HBCi 400800 (800 V, 400 A)", maker="MGM COMPRO (CZ)", mass_kg=4.0,
    mass_note="cooling-plate version; larger cooled versions weigh more",
    ratings={"voltage_V": "120-800", "current_A": 400, "peak_power_kW": 400, "cont_power_kW": 320},
    price=Q(estimate=[5000, 9000], basis="No published price; estimate by analogy with Cascadia CM200DX listings."),
    sources=["https://mgm-compro.com/controllers-inverters-escs/hbci-400800/"],
    notes="Needed if REB 50 (400-800 V) is chosen; strongly oversized per motor. Ask MGM for a smaller 800 V unit.")

add(id="INV-HBCI380120", category="inverter", role=["lift"], status="alternate",
    name="MGM COMPRO HBCi 380120 (120 V, 380 A)", maker="MGM COMPRO (CZ)", mass_kg=1.035,
    ratings={"voltage_V": "up to 120", "current_A": 380, "peak_power_kW": 51, "cont_power_kW": 45},
    price=Q(estimate=[1500, 3500], basis="No published price; bracketed by T-Motor Thunder 300A (USD 1,599)."),
    sources=["https://mgm-compro.com/controllers-inverters-escs/hbci-380120/"],
    notes="Higher-grade alternative to the Thunder 300A for a 24S (~100 V) U15XXL configuration.")

add(id="INV-THUNDER300", category="inverter", role=["lift"], status="alternate",
    name="T-Motor Thunder 300A 24S ESC", maker="T-Motor (CN)", mass_kg=0.87,
    ratings={"voltage": "14-24S", "cont_current_A": "150 (T-Motor shop) / 240 (LigPower) - sources conflict",
             "peak_current_A": "300 (10 s)", "bec": False, "programmable": False},
    price=P(1599.00, source="https://www.ligpower.com/product/thunder-300A-24s-manned-aircraft-esc.html",
            type_="dealer", note="LigPower (T-Motor distributor); other resellers up to USD 2,399."),
    sources=[TM_U15XXL, "https://www.ligpower.com/product/thunder-300A-24s-manned-aircraft-esc.html", EXPORT_RULE],
    notes="The kit's own bench data draw 209 A at full thrust, above the 150 A continuous figure on the T-Motor "
          "page. No CAN telemetry; not programmable. Export licensing applies to matching ESCs.")

add(id="INV-CM200DX", category="inverter", role=["pusher"], status="reference",
    name="Cascadia Motion CM200DX", maker="Cascadia Motion (US)", mass_kg=11.3,
    mass_note="25 lb (New Eagle listing)",
    ratings={"voltage_V": "50-480", "cont_current_Arms": 300, "peak_current_Arms": 740},
    price=P(7202.00, source="https://www.fuel2electric.com/cascadia-motion-cm200-inverter", type_="reseller",
            note="Another reseller lists USD 8,700 (reach.dog)."),
    sources=["https://store.neweagle.net/?p=18103", "https://www.fuel2electric.com/cascadia-motion-cm200-inverter",
             "https://reach.dog/shop/legacy-ev/products/cm200dx-propulsion-inverter"],
    notes="Automotive unit, robust and well documented, but ~3x the mass of an MGM unit of equal rating.")

add(id="INV-SEVCON-G5S9", category="inverter", role=["pusher"], status="reference",
    name="Sevcon (BorgWarner) Gen5 Size 9", maker="BorgWarner / Sevcon", mass_kg=6.0,
    mass_note="13.2 lb (Thunderstruck); another reseller gives 18 lb",
    ratings={"voltage_V": "128-450 (derated above 420)", "cont_current_A": 200, "peak_current_A": 400, "ip": "IP6K9K"},
    price=Q(basis="Reseller prices vary; obtain from Thunderstruck/BorgWarner.",
            source="https://www.thunderstruck-ev.com/sevcon-g5s9-controller.html"),
    sources=["https://www.thunderstruck-ev.com/sevcon-g5s9-controller.html"],
    notes="Industrial/automotive; heavier than aviation-oriented controllers.")

add(id="INV-PLETT-MST", category="inverter", role=["pusher"], status="reference",
    name="Plettenberg MST 140-200 / MST 400-400", maker="Plettenberg (DE)", mass_kg=1.3,
    mass_note="MST 140-200 1.3 kg; MST 400-400 2.9 kg",
    ratings={"MST140-200": "30 kW cont / 40 kW peak", "MST400-400": "120 kW cont / 160 kW peak, water cooled"},
    price=Q(estimate=1547, currency="EUR", basis="Old forum-quoted price for MST 140-200.", source=PLETT_PRICE),
    sources=[PLETT], notes="Low-voltage paramotor-class controllers.")

add(id="INV-EMSISO-H20", category="inverter", role=["pusher"], status="reference",
    name="Emsiso emDrive H20 (400/800 V, 30-60 kW PMSM)", maker="Emsiso (SI)", mass_kg=None,
    ratings={"voltage_V": "400 and 800 variants", "motor_range_kW": "30-60"},
    price=Q(basis="No published price or mass.", source="https://metstrade.com/exhibitors/emsiso-d-o-o/products/emdrive-h20"),
    sources=["https://metstrade.com/exhibitors/emsiso-d-o-o/products/emdrive-h20"],
    notes="Slovenian inverter commonly paired with EMRAX motors; marine-oriented listing.")

# =====================================================================================
# 3. PROPELLERS / ROTORS
# =====================================================================================
add(id="PROP-TM-NS62", category="propeller", role=["lift"], status="alternate",
    name="T-Motor NS62x24 carbon 2-blade (1.575 m)", maker="T-Motor (CN)", mass_kg=1.84,
    mass_note="920 +/- 40 g per blade",
    ratings={"diameter_m": 1.575, "pitch_in": 24, "material": "CF + epoxy", "bench_max_kgf": 101.4,
             "bench_rpm_max": 2203, "tip_speed_at_max_mps": 181.7},
    price=P(2599.00, type_="list", source="https://store.tmotor.com/product/u15xxl-manned-aircraft-combo.html",
            note="Listing price recorded 2026-11-09 (E8 ledger S07); sales unit (blade/pair) to be confirmed."),
    sources=[TM_U15XXL, EXPORT_RULE],
    notes="Matched to U15XXL with full bench table. Blade radius 31 in exceeds the 30 in threshold in the "
          "Chinese licence list.")

add(id="PROP-EPROPS-UAV-ADJ", category="propeller", role=["lift", "pusher"], status="shortlist",
    name="E-PROPS UAV ground-adjustable carbon propellers (50-180 kW)", maker="E-PROPS (FR)", mass_kg=None,
    ratings={"diameter_CW_in": "47-82 (1.20-2.09 m)", "diameter_CCW_in": "47-75 (1.20-1.90 m)",
             "matched_CW_CCW_max_in": 74.8, "max_power_2blade_kW": 86, "max_power_3blade_kW": 128,
             "max_power_4blade_kW": 172, "hub_pattern": "6M8 d101.6 or 6M8 d100"},
    price=Q(estimate=1304, currency="EUR", basis="Manned-aircraft Durandal-2 two-blade list price (ex VAT, April "
                                                  "2026) as the nearest published figure; UAV rotors are quoted.",
            source="https://aircraft.e-props.fr/ordering.php"),
    sources=["https://uav.e-props.fr/adjustable-pitch.php", "https://aircraft.e-props.fr/ordering.php"],
    notes="CCW blades are published only to 75 in (1.90 m): the 1.90 m lift pairs are exactly at the matched limit and a 2.05 m CCW pusher is outside the published range (quote). "
          "Best COTS fit for 1.7-1.9 m lift rotors with matched CW/CCW pairs and for the pusher. Ground-adjustable "
          "pitch lets the team trim hover rpm to the motor without new blades. Warranty excludes VTOL use on the "
          "manned-aircraft site, so a UAV/VTOL supply agreement is needed.")

add(id="PROP-SENSENICH-UAV", category="propeller", role=["lift", "pusher"], status="shortlist",
    name="Sensenich ground-adjustable composite UAV propellers", maker="Sensenich (US)", mass_kg=None,
    ratings={"diameter_in": "15-98 (0.38-2.48 m)", "power_hp": "5-200", "rotation": "CW or CCW, tractor or pusher",
             "hub": "standard and custom flange patterns"},
    price=Q(estimate=2185, basis="Aircraft Spruce price of the 70 in two-blade Rotax ground-adjustable "
                                 "composite prop 2A0R5R70EN (P/N 05-01609).",
            source="https://www.aircraftspruce.com/catalog/appages/sensenich.php"),
    sources=["https://sensenich.com/?p=4931", "https://www.aircraftspruce.com/catalog/appages/sensenich.php"],
    notes="Only US COTS source found that covers 2.0-2.48 m with both rotation directions. Request-for-quote.")

add(id="PROP-HELIX", category="propeller", role=["lift", "pusher"], status="alternate",
    name="Helix carbon propellers (fixed F / ground-adjustable V series)", maker="Helix-Carbon GmbH (DE)", mass_kg=None,
    ratings={"diameter_m": "0.75-2.8", "types": "fixed pitch, ground adjustable, in-flight (electric/hydraulic)"},
    price=Q(basis="No price list published; quote via info@helix-propeller.de.", source="https://helix-propeller.de/"),
    sources=["https://helix-propeller.de/", "https://helix-propeller.de/downloads/manuals/H50F_en_15-01-2016.pdf"],
    notes="Widest diameter range found (to 2.8 m): the only COTS route for 2.5-2.8 m lift rotors.")

add(id="PROP-DUC-SWIRL", category="propeller", role=["pusher"], status="alternate",
    name="DUC Hélices SWIRL ground-adjustable (2 or 3 blade)", maker="DUC Hélices (FR)", mass_kg=2.72,
    mass_note="2-blade 68.1 in: 6.0 lb; 3-blade: 8.0 lb",
    ratings={"diameters_in": "59.8, 63.8, 65.4, 68.1"},
    price=P(2226.00, source="https://aircraftspruce.com/catalog/appages/duc_swirl-blade.php", type_="retail",
            note="2-blade; 3-blade USD 3,102; replacement blades USD 425-722."),
    sources=["https://aircraftspruce.com/catalog/appages/duc_swirl-blade.php",
             "https://www.aircraftspruce.ca/catalog/pnpages/05-06675.php"],
    notes="Rotax-class pusher propeller; maximum 1.73 m. Hub to be adapted to the motor flange.")

add(id="PROP-NEUFORM", category="propeller", role=["pusher"], status="not_recommended",
    name="Neuform CR3-V in-flight adjustable", maker="Neuform (DE)", mass_kg=None, ratings={},
    price=Q(basis="No published price."), sources=["https://www.experimentalaircraft.info/articles/neuform-composites.php"],
    notes="In-flight adjustable pitch adds an actuator and failure mode; contrary to the low-complexity objective.")

add(id="PROP-INHOUSE", category="propeller", role=["lift"], status="not_recommended",
    name="In-house CNC wood or wet-layup composite rotor blades", maker="in-house", mass_kg=None, ratings={},
    price=Q(basis="Material cost low (laminated hardwood or carbon/epoxy); the cost driver is substantiation testing."),
    sources=["https://store.astm.org/f2506-22.html", "https://www.faa.gov/sites/faa.gov/files/2022-11/AC20-66A.pdf",
             "https://www.faa.gov/regulations_policies/advisory_circulars/index.cfm/go/document.information/documentID/22940"],
    notes="Feasible to manufacture (two-sided 3-axis machining with flip jig and dowel registration; or wet-layup "
          "in CNC-machined split moulds), but flight use requires the strength, vibratory-stress, fatigue and "
          "endurance testing of ASTM F2506 / AC 20-66A / AC 35.37-1 class methods. Lift rotors on an eVTOL see "
          "1P-nP cyclic loads in edgewise flow during transition. Use only for whirl-tower and ground rigs.")

# =====================================================================================
# 4. CELLS, PACKS, BMS AND HV COMPONENTS
# =====================================================================================
P50B_DS = "https://www.molicel.com/wp-content/uploads/4.TR%E7%B0%A1%E6%98%93%E8%A6%8F%E6%A0%BC_INR21700P50B_1.1_Product-Data-Sheet-of-INR-21700-P50B-80122.pdf"
add(id="CELL-P50B", category="cell", role=["battery"], status="shortlist",
    name="Molicel INR-21700-P50B", maker="Molicel (TW)", mass_kg=0.071, mass_note="maximum",
    ratings={"capacity_Ah": 5.0, "energy_Wh": "18.0 typ / 17.5 min", "nominal_V": 3.6, "charge_V": 4.2,
             "cont_discharge_A": "60 (80 C cut-off)", "dc_impedance_mOhm": "12.8 typ at 50 % SOC",
             "specific_energy_Wh_per_kg": "253 (18.0 Wh / 71 g, computed)"},
    price=P(7.50, source="https://www.18650batterystore.com/products/molicel-21700-p50b-5000mah-50a-battery",
            type_="retail", note="1000+ tier; single cell USD 11.99 (recorded 2026-11-09, E8 ledger S06)."),
    sources=["https://www.molicel.com/product/inr-21700-p50b/", P50B_DS,
             "https://www.18650batterystore.com/products/molicel-21700-p50b-5000mah-50a-battery"],
    notes="Best published energy at high power. Hover at ~3-5C on a 1.5-2 kWh/cell-group pack is well inside "
          "the 12C (60 A) rating, which leaves margin for one-pack-out operation.")

add(id="CELL-P45B", category="cell", role=["battery"], status="alternate",
    name="Molicel INR-21700-P45B", maker="Molicel (TW)", mass_kg=0.069, mass_note="maximum",
    ratings={"capacity_Ah": 4.5, "nominal_V": 3.6, "cont_discharge_A": 45, "specific_energy_Wh_per_kg": 242},
    price=P(6.99, source="https://18650battery.com/products/molicel-p45b-21700-4500mah-45a-battery", type_="retail",
            note="18650batterystore lists USD 5.19 sale but sold out."),
    sources=["https://www.molicel.com/product/inr-21700-p45b/", "https://www.18650batterystore.com/products/molicel-p45b"],
    notes="Lower energy than P50B with no advantage at this C-rate.")

add(id="CELL-SAM50S", category="cell", role=["battery"], status="alternate",
    name="Samsung INR21700-50S", maker="Samsung SDI (KR)", mass_kg=0.072, mass_note="70.1 g typ / 72 g max (sellers)",
    ratings={"capacity_Ah": 5.0, "cont_discharge_A": "25 (45 with 80 C cut-off)", "nominal_V": 3.6},
    price=P(5.99, source="https://18650batterystore.com/products/samsung-50s-21700-5000mah-25a-battery", type_="retail",
            note="Sale price; regular USD 8.99. Supply reported limited."),
    sources=["https://18650batterystore.com/products/samsung-50s-21700-5000mah-25a-battery"],
    notes="Equal capacity to P50B at lower discharge rating; second source if P50B supply is short.")

add(id="CELL-SAM50G", category="cell", role=["battery"], status="not_recommended",
    name="Samsung INR21700-50G", maker="Samsung SDI (KR)", mass_kg=0.068, mass_note="68.0 g measured, no wrap",
    ratings={"capacity_Ah": "4.85-4.9 min", "cont_discharge_A": 9.7, "nominal_V": 3.63},
    price=Q(basis="Retail listings vary.", source="https://www.nkon.nl/en/samsung-inr21700-50g.html"),
    sources=["https://www.nkon.nl/en/samsung-inr21700-50g.html"],
    notes="~2C limit is insufficient for hover and motor-out power.")

add(id="CELL-EVE50PL", category="cell", role=["battery"], status="alternate",
    name="EVE INR21700/50PL (tabless)", maker="EVE Energy (CN)", mass_kg=0.072, mass_note="approx., retailer",
    ratings={"capacity_Ah": 5.0, "nominal_V": 3.6, "cont_discharge_A": "50 (retailer; another lists 125)"},
    price=Q(basis="Retail listing price not captured; EVE 50E (15 A) retails at USD 2.89-5.99.",
            source="https://www.18650batterystore.com/products/eve-50pl-21700-5000mah-50a-battery"),
    sources=["https://www.18650batterystore.com/products/eve-50pl-21700-5000mah-50a-battery",
             "https://www.18650batterystore.com/products/eve-50e-21700-5000mah-15a-battery"],
    notes="Potential low-cost alternative; ratings need the manufacturer datasheet.")

add(id="CELL-AMPRIUS", category="cell", role=["battery"], status="reference",
    name="Amprius SiCore 21700 (6.3 Ah) / SiCore aviation cells", maker="Amprius (US)", mass_kg=None,
    ratings={"21700_6p3Ah_Wh_per_kg": 315, "sicore_aviation_Wh_per_kg": 370, "sicore_power_W_per_kg": 3000,
             "discharge": "up to 10C uncooled / 15C cooled (SiCore)"},
    price=Q(basis="No published price.", source="https://www.businesswire.com/news/home/20250306597630/en"),
    sources=["https://www.businesswire.com/news/home/20250306597630/en",
             "https://ainonline.com/aviation-news/futureflight/2025-01-14/amprius-boosts-evtol-performance-sicore-battery-cells"],
    notes="Highest specific energy found; supply to small builders and cycle life to be confirmed. Growth option.")

add(id="CELL-VTC6A", category="cell", role=["battery"], status="reference",
    name="Sony/Murata US18650VTC6A", maker="Murata (JP)", mass_kg=None, ratings={},
    price=Q(basis="No current datasheet/price found in Nov 2026 searches."), sources=[],
    notes="18650 format would double the cell count vs 21700; not pursued.")

add(id="PACK-PIPISTREL", category="pack", role=["battery"], status="reference",
    name="Pipistrel Velis Electro battery pack (2 modules)", maker="Pipistrel / Textron eAviation", mass_kg=70.0,
    mass_note="per pack per Wikipedia; another source gives 60 kg",
    ratings={"aircraft_total_kWh": 24.8, "packs_per_aircraft": 2, "cooling": "liquid",
             "pack_specific_energy_Wh_per_kg": "~177 (24.8 kWh / 140 kg, computed)"},
    price=P(25000, currency="EUR", unit="pack", type_="list",
            source="https://cdn.annexbusinessmedia.com/WG/etrending/2026/01/11/ANXCD251218058-mail.html",
            note="Plus shipping and taxes (Jan 2026 article)."),
    sources=["https://en.wikipedia.org/wiki/Pipistrel_Velis_Electro",
             "https://cdn.annexbusinessmedia.com/WG/etrending/2026/01/11/ANXCD251218058-mail.html"],
    notes="Certified-aircraft pack, not sold for other airframes. Used as the benchmark for pack-level specific "
          "energy (~177 Wh/kg) and cost (~EUR 1,000/kWh).")

add(id="PACK-H55", category="pack", role=["battery"], status="reference",
    name="H55 certifiable propulsion battery modules", maker="H55 (CH)", mass_kg=None,
    ratings={"status": "EASA-witnessed module certification tests completed Dec 2025; CS-23 path; DOA+POA"},
    price=Q(basis="OEM supply only; no published price.", source="https://h55.ch/"),
    sources=["https://www.electrive.com/2026/02/03/h55-completes-certification-tests-for-propulsion-battery-modules-for-electric-aircraft",
             "https://www.flightglobal.com/aerospace/h55-hails-regulatory-milestone-after-completing-battery-of-easa-tests/166152.article"],
    notes="Reference for thermal-runaway containment practice; Electroflight: no current product data found.")

add(id="BMS-ORION2", category="bms", role=["battery"], status="shortlist",
    name="Orion BMS 2 (up to 180 cells in series)", maker="Ewert Energy Systems (US)", mass_kg=None,
    ratings={"cells_series_max": 180, "interface": "CAN, contactor/charger control"},
    price=P(1680.00, type_="list", source="https://www.orionbms.com/manuals/pdf/orionbms2_purchasing_guide.pdf",
            note="180-cell MSRP; 24-cell USD 820."),
    sources=["https://www.orionbms.com/manuals/pdf/orionbms2_purchasing_guide.pdf",
             "https://www.orionbms.com/downloads/documents/orionbms2_specifications.pdf"],
    notes="One unit per independent pack (2-4 per aircraft). Widely used in EV conversions with CAN DBC files.")

add(id="BMS-EMUS-G1", category="bms", role=["battery"], status="alternate",
    name="EMUS G1 BMS control unit + per-cell-group modules", maker="EMUS (LT)", mass_kg=None,
    ratings={"architecture": "distributed cell modules"},
    price=P(397.00, type_="retail", source="https://www.electricmotorsport.com/ev-parts/emus-bms-g1-control-unit-9-32v-dc-supply-voltage.html",
            note="Control unit with quick-start wiring; cell module USD 18.00 each; current sensor extra."),
    sources=["https://www.electricmotorsport.com/ev-parts/emus-bms-g1-control-unit-9-32v-dc-supply-voltage.html",
             "https://electricmotorsport.com/emus-g1-distributed-grouped-bms-kit-2.html"],
    notes="96 cell modules (USD 1,728) + controller per pack; more wiring points than Orion.")

add(id="BMS-ENNOID", category="bms", role=["battery"], status="reference",
    name="ENNOID-BMS HV (open source)", maker="ENNOID", mass_kg=None, ratings={},
    price=Q(basis="No price found."), sources=["https://sites.google.com/ennoid.me/2017/bms/gen-1"],
    notes="Open hardware; would need in-house validation.")

add(id="HV-EV200", category="hv", role=["battery"], status="shortlist",
    name="TE Kilovac EV200 main contactor (500 A, 900 VDC)", maker="TE Connectivity", mass_kg=None,
    ratings={"cont_current_A": 500, "voltage_VDC": 900},
    price=P(193.00, type_="retail", source="https://www.digikey.sg/en/product-highlight/t/te-connectivity-aerospace-defense-and-marine/kilovac-lightweight-dc-contactors",
            note="DigiKey range USD 193-345 by variant; Farnell EV200ADANA EUR 191.77."),
    sources=["https://nl.farnell.com/en-NL/kilovac-te-connectivity/ev200adana/contactor-spst-no-95v-500a-panel/dp/2581484"],
    notes="Two per pack (positive and negative) plus a precharge relay/resistor. LEV200 lighter variant exists.")

add(id="HV-FUSE", category="hv", role=["battery"], status="shortlist",
    name="EV pack fuse 1000 VDC 200 A class (Eaton Bussmann FWE-200A / Mersen MEV100A200)", maker="Eaton / Mersen",
    mass_kg=None, ratings={"voltage_VDC": 1000, "current_A": 200, "Mersen_breaking": "20 kA at 1000 V, L/R <= 1 ms"},
    price=P(186.34, type_="reseller", source="https://www.electricautomationnetwork.com/en/eaton-moeller/fwe-200a-eaton-electric-electric-charger-fuses",
            note="RS NZ lists the same part at a much higher indicative price."),
    sources=["https://us.mersen.com/en/products/evpack-fuse-mev100a-1000-vdc-max-l-r-less-or-equal-1ms-50-300a-round-body-fuse"],
    notes="Rating to be set from the final bus current; one main fuse per pack plus per-inverter branch fuses.")

add(id="HV-CONN", category="hv", role=["battery"], status="shortlist",
    name="Amphenol SurLok Plus 8 mm HV connectors", maker="Amphenol", mass_kg=None,
    ratings={"family": "touch-safe single-pole HV, 8 mm"},
    price=P(13.13, type_="retail", source="https://www.digikey.com.br/en/products/detail/amphenol-industrial-operations/SLPIRBTPSO3/9444372",
            note="Receptacle, qty 1; plugs ~GBP 22."),
    sources=["https://www.digikey.co.uk/en/products/detail/amphenol-industrial-operations/SLPIPB35BSB0/9444330"],
    notes="Anderson SBS75X is rated 600 V / 110 A (USD ~7.6) - acceptable for a <=400 V bus only.")

add(id="HV-DCDC", category="hv", role=["avionics_power"], status="alternate",
    name="Isolated HV-to-28 V DC-DC (Vicor V375A28H600BL 600 W, 250-425 V in)", maker="Vicor", mass_kg=None,
    ratings={"input_V": "250-425", "output_V": 28, "power_W": 600},
    price=P(1178.29, currency="GBP", type_="retail",
            source="https://www.digikey.co.uk/en/products/detail/vicor-corporation/V375A28H600BL/3002341"),
    sources=["https://www.digikey.co.uk/en/products/detail/vicor-corporation/V375A28H600BL/3002341",
             "https://backoffice.recom-power.com/en/rec-p-RMOD4000-650-28SEW.html"],
    notes="Two units (one per HV bus) diode-ORed with a 28 V LiFePO4 backup battery. For an 800 V bus use "
          "Recom RMOD4000-650-28SEW (180-950 V in, 4 kW; listed 'coming soon').")

# =====================================================================================
# 5. BALLISTIC PARACHUTES
# =====================================================================================
MAG = "https://uflyit.com/Magnum%20Parachutes%202.htm"
add(id="CHUTE-MAG601", category="parachute", role=["recovery"], status="shortlist",
    name="Magnum 601 SP softpack (Stratos 07)", maker="Stratos 07 (CZ)", mass_kg=12.4,
    mass_note="27.3 lb system",
    ratings={"max_gross_lb": 1670, "max_gross_kg": 757, "max_deploy_mph": 199},
    price=P(7580.00, type_="dealer", source=MAG, note="US dealer list (U-Fly-It); bridles sold separately."),
    sources=[MAG],
    notes="Covers MTOW up to 757 kg. Dealer notes the column mapping on its page is inconsistent in places: "
          "confirm with Magnum.")

add(id="CHUTE-MAG901", category="parachute", role=["recovery"], status="shortlist",
    name="Magnum 901 SP softpack (Stratos 07)", maker="Stratos 07 (CZ)", mass_kg=17.6, mass_note="38.8 lb system",
    ratings={"max_gross_lb": 2094, "max_gross_kg": 950, "max_deploy_mph": 199},
    price=P(12005.00, type_="dealer", source=MAG),
    sources=[MAG], notes="Use if MTOW is 757-950 kg.")

add(id="CHUTE-GRS600", category="parachute", role=["recovery"], status="alternate",
    name="Galaxy GRS 6/600 SD Speedy 115 m2", maker="Galaxy GRS (CZ)", mass_kg=12.3,
    mass_note="11.5 kg unit / ~12.3 kg total packed",
    ratings={"mtow_kg": 600, "vne_kmh": "380 (400 high-speed variant)", "standard": "ASTM F2316-12"},
    price=Q(basis="No published price; quote from info@galaxysky.cz.", source="https://galaxysky.cz/grs-6-600-sd-speedy-ff-115-m2-p22-en"),
    sources=["https://galaxysky.cz/grs-6-600-sd-speedy-ff-115-m2-p22-en"], notes="")

add(id="CHUTE-GRS750", category="parachute", role=["recovery"], status="alternate",
    name="Galaxy GRS 6 650-700 SD Speedy / 750 SDS 140 m2", maker="Galaxy GRS (CZ)", mass_kg=14.8,
    mass_note="750 SDS/FF softpack ~14.8 kg",
    ratings={"mtow_kg": "650 / 700 / 750", "vne_kmh": "325 / 295 / 250", "descent_mps": "7.2 @700 kg, 7.6 @750 kg (1500 m)"},
    price=Q(basis="No published price.", source="https://galaxysky.cz/grs-6-750-sds-ff-140m2-p42-en"),
    sources=["https://galaxysky.cz/grs-6-650-700-sd-speedy-140m2-p40-en", "https://galaxysky.cz/grs-6-750-sds-ff-140m2-p42-en"],
    notes="")

add(id="CHUTE-GRS990", category="parachute", role=["recovery"], status="alternate",
    name="Galaxy GRS 6 800-990 SDS 175 m2", maker="Galaxy GRS (CZ)", mass_kg=21.7, mass_note="'total weight +/-4 %'",
    ratings={"mtow_kg": "800 / 900 / 1050", "vne_kmh": "380 / 350 / 315", "descent_mps": "7.1-7.9 at 1000 m",
             "canopy_m2": 175, "standard": "ASTM F2316-12"},
    price=Q(estimate=14000, basis="No published price. WP D estimate (sizing/data.py): Magnum 901 SP USD 12,005 (950 kg) + ~15 % for the larger 175 m2 canopy", source="https://galaxysky.cz/grs-6-800-990-sds-175m2-p43-en"),
    sources=["https://galaxysky.cz/grs-6-800-990-sds-175m2-p43-en"], notes="Galaxy also lists a multicopter range.")

add(id="CHUTE-BRS6", category="parachute", role=["recovery"], status="reference",
    name="BRS-6 (models 600-1800)", maker="BRS Aerospace (US)", mass_kg=18.1,
    mass_note="BRS6-1800 softpack ~40 lb (used-sale listing)",
    ratings={"models": "600, 800, 1050, 1350, 1350HS, 1600, 1800 (lb class)", "repack": "6 years; rocket 12 years"},
    price=P(9341.00, type_="retail", source="https://www.aircraftspruce.com/catalog/pspages/brs-parachutes-lsa.php",
            note="Typical installation-specific LSA softpack price; range USD 6,664-15,566."),
    sources=["https://www.aircraftspruce.com/catalog/pspages/brs-parachutes-lsa.php",
             "https://brsaerospace.com/wp-content/uploads/2020/06/020002-01-Rev.-A.pdf"],
    notes="BRS sells installation-specific systems; a custom eVTOL installation needs BRS engineering.")

# =====================================================================================
# 6. FLIGHT CONTROL AND AVIONICS
# =====================================================================================
add(id="FCC-VERONTE4X", category="avionics", role=["fcc"], status="shortlist",
    name="Embention Veronte Autopilot 4x (triple core + optional external 4th)", maker="Embention (ES)", mass_kg=0.75,
    ratings={"redundancy": "3 internal cores + optional external core, no single point of failure",
             "assurance": "DO-178C / DO-254 DAL B evidence (DAL A ongoing); DO-160G tested"},
    price=P(23500, currency="EUR", type_="reseller", source="https://avpay.aero/company/embention/product/professional-drone-autopilot-4x/",
            note="w/o DAA; ADS-B version EUR 27,000 (indicative reseller listing)."),
    sources=["https://www.embention.com/veronte-ecosystem/autopilots/4x-system-redundancy",
             "https://manuals.embention.com/4x/en/1.8/technical/index.html"],
    notes="Only COTS FCC found with published redundancy plus DO-178C/DO-254 evidence at a price a small team "
          "can afford. Under an experimental certificate this is engineering evidence, not certification credit.")

add(id="FCC-CUBE-ORANGEP", category="avionics", role=["fcc"], status="alternate",
    name="CubePilot Cube Orange+ Standard Set with ADS-B carrier", maker="CubePilot (AU)", mass_kg=None,
    ratings={"firmware": "ArduPilot / PX4", "imus": "triple redundant IMU", "adsb": "uAvionix 1090 MHz receiver"},
    price=P(350.00, type_="retail", source="https://irlock.com/products/cube-orange-plus-standard-set"),
    sources=["https://irlock.com/products/cube-orange-plus-standard-set"],
    notes="For unmanned flight-test and hardware-in-the-loop. Three independent Cubes with a voter would be an "
          "in-house redundancy design with no assurance pedigree; use for the uncrewed phase only.")

add(id="FCC-PIXHAWK6X", category="avionics", role=["fcc"], status="reference",
    name="Holybro Pixhawk 6X Standard v2A (PM02D)", maker="Holybro (CN)", mass_kg=0.105,
    ratings={"imus": "triple IMU"},
    price=P(422.99, type_="list", source="https://holybro.com/products/pixhawk-6x", note="Recorded 2026-11-09 (E8 ledger S09)."),
    sources=["https://holybro.com/products/pixhawk-6x"], notes="Same role as Cube; already used on the E8-S subscale.")

add(id="FCC-MICROPILOT", category="avionics", role=["fcc"], status="reference",
    name="MicroPilot MP2128 3X triple-redundant", maker="MicroPilot (CA)", mass_kg=None, ratings={},
    price=Q(basis="No current price or datasheet captured."), sources=["https://www.micropilot.com/"],
    notes="Listed for completeness.")

add(id="GNSS-HERE4", category="avionics", role=["gnss"], status="shortlist",
    name="CubePilot Here4 multiband RTK GNSS (x2)", maker="CubePilot", mass_kg=None, ratings={"bands": "multiband L1/L5"},
    price=P(225.00, type_="retail", source="https://irlock.com/products/here4-multiband-rtk-gnss"),
    sources=["https://irlock.com/products/here4-multiband-rtk-gnss"], notes="Two units for dissimilar placement.")

add(id="AIRSPEED-MS4525", category="avionics", role=["airdata"], status="shortlist",
    name="Digital airspeed sensor (MS4525DO) with pitot (x2)", maker="Holybro", mass_kg=0.02,
    ratings={}, price=P(49.99, source="https://holybro.com/collections/sensors"),
    sources=["https://holybro.com/collections/sensors"],
    notes="FCC airspeed; the pilot display (Dynon) has its own pitot-static ADAHRS.")

add(id="EFIS-DYNON-HDX7", category="avionics", role=["display"], status="shortlist",
    name="Dynon SkyView HDX 7-inch system (from)", maker="Dynon (US)", mass_kg=None,
    ratings={"includes": "configured system, starting configuration"},
    price=P(4909.00, type_="list", source="https://generalaviationnews.com/2026/07/28/the-evolution-of-the-skyview-hdx/",
            note="Starting price quoted for a Rotax iS configuration; eVTOL integration via CAN/serial needs Dynon support."),
    sources=["https://generalaviationnews.com/2026/07/28/the-evolution-of-the-skyview-hdx/", "https://www.dynonavionics.com/SkyView-HDX/"],
    notes="Independent ADAHRS for the pilot, separate from the FCC sensor set.")

add(id="EFIS-G5", category="avionics", role=["display"], status="alternate",
    name="Garmin G5 standby (experimental)", maker="Garmin", mass_kg=None, ratings={},
    price=P(1655.00, type_="list", source="https://www8.garmin.com/aviation/brochures/Experimental%20Pricing%20Sheet%202023.pdf",
            note="2023 list; MAP USD 1,495."),
    sources=["https://www8.garmin.com/aviation/brochures/Experimental%20Pricing%20Sheet%202023.pdf"],
    notes="Standby attitude/airspeed with own battery.")

add(id="XPDR-TAILBEACONX", category="avionics", role=["surveillance"], status="shortlist",
    name="uAvionix tailBeaconX (Mode S + 1090ES ADS-B Out)", maker="uAvionix", mass_kg=None, ratings={},
    price=P(2499.00, type_="list", source="https://uavionix.com/tailbeaconX", note="Sale USD 2,250 shown, undated."),
    sources=["https://uavionix.com/tailbeaconX", "https://aopa.org/news-and-media/all-news/2020/february/20/uavionix-launches-space-based-ads-b"],
    notes="Self-contained in a tail-light form factor: no separate antenna; fits the tail between the booms.")

add(id="XPDR-TT21", category="avionics", role=["surveillance"], status="alternate",
    name="Trig TT21 Mode S transponder", maker="Trig Avionics (UK)", mass_kg=None, ratings={},
    price=P(2186.67, currency="GBP", type_="dealer", source="https://g-tlac.com/?p=2180", note="+ VAT"),
    sources=["https://g-tlac.com/?p=2180"], notes="Needs a separate GPS source for ADS-B Out.")

add(id="COM-TY91", category="avionics", role=["radio"], status="shortlist",
    name="Trig TY91 VHF COM radio", maker="Trig Avionics (UK)", mass_kg=None, ratings={},
    price=P(1477.33, currency="GBP", type_="dealer", source="https://g-tlac.com/?p=2178", note="+ VAT"),
    sources=["https://g-tlac.com/?p=2178"], notes="")

# =====================================================================================
# 7. CABIN, LANDING GEAR
# =====================================================================================
add(id="CAB-HARNESS", category="cabin", role=["occupant"], status="shortlist",
    name="Hooker 4-point aircraft harness (per seat)", maker="Hooker Custom Harness (US)", mass_kg=None, ratings={},
    price=P(519.92, currency="EUR", type_="retail", source="https://www.aircraftspruce.eu/hooker-cessna-fixed-harness-ea.htm",
            note="Incl. 19 % VAT; a 2025 owner report gives USD 435/seat."),
    sources=["https://www.aircraftspruce.eu/airframe-parts/seat-belts---harnesses/multipoint-sets/hooker-custom-harnesses.html",
             "https://www.pilotsofamerica.com/community/threads/cessna-182.148553/"],
    notes="Custom-length 4-point; anchor to the seat/keel structure, not to skins.")

add(id="CAB-CONFOR", category="cabin", role=["occupant"], status="shortlist",
    name="CONFOR CF-45 (blue) energy-absorbing seat foam", maker="CONFOR / Aircraft Spruce", mass_kg=None,
    ratings={"size": "1 x 16 x 18 in"},
    price=P(43.95, source="https://aircraftspruce.com/catalog/pnpages/01-09310.php", note="P/N 01-09310; 1x18x40 in USD 90 (Cumulus Soaring)."),
    sources=["https://aircraftspruce.com/catalog/pnpages/01-09310.php", "https://cumulus-soaring.com/store/confor-foam-blue-1x18x40"],
    notes="Seat cushions in layered CF-45/CF-47 over a composite seat pan with a crushable honeycomb or foam "
          "stroke zone below; pan and stroke zone designed by WP F for the 3 g landing and crash cases.")

add(id="CAB-PC-SHEET", category="cabin", role=["canopy"], status="shortlist",
    name="Polycarbonate sheet 0.125 x 48 x 96 in (canopy/windows)", maker="Professional Plastics (via Zoro)", mass_kg=None,
    ratings={"thickness_mm": 3.2},
    price=P(239.99, source="https://zoro.com/professional-plastics-clear-gp-polycarbonate-9034-polycarbonate-sheet-0125-x-48-x-96-each-spccl125x48000x96000gp-polycarbonate/i/G000907887",
            note="+ USD 80 special delivery surcharge."),
    sources=["https://zoro.com/professional-plastics-clear-gp-polycarbonate-9034-polycarbonate-sheet-0125-x-48-x-96-each-spccl125x48000x96000gp-polycarbonate/i/G000907887"],
    notes="PC must be dried before thermoforming; better impact strength (bird/rotor debris) than PETG or acrylic.")

add(id="CAB-PETG-SHEET", category="cabin", role=["canopy"], status="alternate",
    name="PETG sheet 3 mm, 1250 x 2050 mm", maker="Ultraplast (LV)", mass_kg=None, ratings={},
    price=P(33.60, currency="EUR", source="https://www.ultraplast.lv/shop/petg/petg-3-mm"),
    sources=["https://www.ultraplast.lv/shop/petg/petg-3-mm"],
    notes="Supplier data: forms at ~170 C without pre-drying (orthopedix-france.fr/en/produits/petg-en/petg/) - easiest for in-house drape forming of side windows and test bubbles.")

add(id="LG-MATCO-W51LT", category="landing_gear", role=["gear"], status="alternate",
    name="Matco W51LT 5.00-5 wheel and brake kit (pair, no axle)", maker="Matco mfg (US)", mass_kg=4.17,
    mass_note="9.2 lb assembly",
    ratings={"tire": "5.00-5", "static_capacity_lb": 1420},
    price=P(1096.00, unit="pair", source="https://www.aircraftspruce.com/catalog/pnpages/06-00079.php",
            note="With axles (06-00568) USD 1,259-1,388."),
    sources=["https://www.aircraftspruce.com/catalog/pnpages/06-00079.php", "https://aircraftspruce.com/catalog/pnpages/06-00568.php"],
    notes="Only needed if a wheeled (rolling take-off/landing capable) gear is chosen; a VTOL-only skid gear is lighter "
          "and simpler. Small castoring ground-handling wheels can be clipped on for hangar moves.")

add(id="LG-SKID-REF", category="landing_gear", role=["gear"], status="reference",
    name="Helicopter skid tubes (6061-T6) - certified-helicopter reference", maker="DART Aerospace", mass_kg=None,
    ratings={"material": "6061-T6"},
    price=P(605.00, unit="skid tube", type_="retail", source="https://dartaerospace.com/collections/skidtubes-407/skidtubes-float-w-standard-wearplates.oembed",
            note="USD 605-1,175 per tube for turbine helicopters."),
    sources=["https://dartaerospace.com/collections/skidtubes-407/skidtubes-float-w-standard-wearplates.oembed"],
    notes="No COTS ultralight-helicopter skid kit with a published price was found; the skid gear is therefore a "
          "make item (straight 6061-T6 skid tubes + outsourced-bent cross tubes, see MANUFACTURING_METHODS.md).")

# =====================================================================================
# 8. RAW MATERIALS
# =====================================================================================
add(id="MAT-TUBE-DP-3x72", category="material", role=["boom", "spar"], status="shortlist",
    name="DragonPlate roll-wrapped twill carbon tube 3.0 in ID x 3.125 in OD x 72 in", maker="DragonPlate (US)", mass_kg=None,
    ratings={"id_mm": 76.2, "od_mm": 79.4, "wall_mm": 1.59, "length_mm": 1829},
    price=P(386.50, source="https://dragonplate.com/carbon-fiber-roll-wrapped-twill-tube-3-id-x-72-gloss-finish",
            note="96 in length USD 498.67; 24 in USD 134.67."),
    sources=["https://dragonplate.com/carbon-fiber-roll-wrapped-twill-tube-3-id-x-96-gloss-finish"],
    notes="Boom / spar tube candidate; laminate schedule (UD vs twill) to be confirmed for stiffness. Lead time 10-15 days for options.")

add(id="MAT-TUBE-DP-4x96", category="material", role=["boom", "spar"], status="shortlist",
    name="DragonPlate roll-wrapped twill carbon tube ~4 in ID x 96 in thin wall", maker="DragonPlate (US)", mass_kg=None,
    ratings={"id_mm": 101.6, "length_mm": 2438},
    price=P(645.00, source="https://dragonplate.com/carbon-fiber-roll-wrapped-twill-tube-4-id-x-96-thin-wall-gloss-finish"),
    sources=["https://dragonplate.com/carbon-fiber-roll-wrapped-twill-tube-4-id-x-96-thin-wall-gloss-finish"],
    notes="~100 mm boom. Wall must be thickened (in-house UD over-wrap) if FEA requires.")

add(id="MAT-TUBE-RW-4x72", category="material", role=["boom", "spar"], status="alternate",
    name="Rock West fabric carbon tube 4.000 x 4.060 x 72 in", maker="Rock West Composites (US)", mass_kg=None,
    ratings={"id_in": 4.0, "od_in": 4.06},
    price=P(396.99, source="https://www.rockwestcomposites.com/46324", note="qty 1-5"),
    sources=["https://www.rockwestcomposites.com/46324"], notes="Thin wall (0.03 in); stiffness to be checked.")

add(id="MAT-TUBE-RW-UD325", category="material", role=["spar"], status="alternate",
    name="Rock West unidirectional carbon tube 3.25 x 3.38 x 72 in", maker="Rock West Composites (US)", mass_kg=None,
    ratings={"id_in": 3.25, "od_in": 3.38},
    price=P(614.99, source="https://www.rockwestcomposites.com/45503.html", note="USD 464.79 each at 2-4 pcs"),
    sources=["https://www.rockwestcomposites.com/45503.html"], notes="High-bending-stiffness lay-up, spar candidate.")

add(id="MAT-TUBE-EC", category="material", role=["small tubes"], status="alternate",
    name="Easy Composites roll-wrapped carbon tubes, 5-60 mm OD", maker="Easy Composites (UK)", mass_kg=None,
    ratings={"od_range_mm": "5-60"},
    price=P(41.30, currency="EUR", source="https://www.easycomposites.eu/35mm-roll-wrapped-carbon-fibre-tube-metric",
            note="35 mm tube ex VAT; length per listing."),
    sources=["https://easycomposites.eu/roll-wrapped-carbon-fibre-tube", "https://www.easycomposites.eu/50mm-roll-wrapped-carbon-fibre-tube-metric"],
    notes="Struts, pylons, tail-boom bracing; does not cover 76-120 mm.")

add(id="MAT-CF-FABRIC", category="material", role=["laminate"], status="shortlist",
    name="Carbon fabric 3K 2x2 twill 5.7 oz (193 g/m2), 50 in wide", maker="US Composites", mass_kg=None,
    ratings={"areal_g_m2": 193},
    price=P(39.50, unit="yard", source="https://uscomposites.com/carbonpage.html", note="USD 28.50/yd for 20+ yd."),
    sources=["https://uscomposites.com/carbonpage.html", "https://fibreglast.com/product/3K_2_x_2_Twill_Weave_Carbon_Fiber_Fabric_01069"],
    notes="Skins and local reinforcements; buy UD carbon tape separately for spar caps (quote).")

add(id="MAT-RESIN-MGS", category="material", role=["laminate"], status="shortlist",
    name="MGS L285 laminating epoxy + H285F / H287S hardener", maker="Hexion/Westlake (via Aircraft Spruce)",
    mass_kg=None, ratings={"note": "aviation laminating system"},
    price=P(439.00, unit="gallon resin", type_="retail", source="https://www.aircraftspruce.com/catalog/cmpages/mgsresin.php",
            note="H285F fast hardener USD 97.75/qt; H287S slow USD 123.75/qt + hazmat fees."),
    sources=["https://www.aircraftspruce.com/catalog/cmpages/mgsresin.php"],
    notes="Primary laminating resin for structure; cure/post-cure schedule from the manufacturer TDS, recorded per batch.")

add(id="MAT-RESIN-WEST", category="material", role=["laminate", "tooling"], status="alternate",
    name="West System 105 resin + 206 slow hardener, 1.2 gal kit", maker="Gougeon Brothers (US)", mass_kg=None, ratings={},
    price=P(180.23, unit="1.2 gal kit", source="https://fiberglasssupply.com/epoxy/west-system/west-system-105-epoxy-resin/west-system-kits-105-epoxy-with-206-slow-hardener/"),
    sources=["https://www.westsystem.com/app/uploads/2023/06/2023.05_WS_Vacuum-Bagging-Techniques-Manual.pdf"],
    notes="Tooling, moulds, fillets and non-primary parts.")

add(id="MAT-FOAM-H80", category="material", role=["core"], status="shortlist",
    name="Divinycell H80 PVC foam (10 mm, 2440 x 1220 mm, grooved/perforated)", maker="Diab", mass_kg=None,
    ratings={"density_kg_m3": 80},
    price=P(109.00, currency="EUR", unit="sheet", source="https://www.castrocompositesshop.com/en/sandwich-cores/2558-pvc-foam-divinycell-h80-10-gpc2-grooved-perforated-10-mm-thickness.html",
            note="ex tax; 1/2 in plain 48x96 in USD 208.95 (Fiberglass Supply)."),
    sources=["https://fiberglasssupply.com/sheet-1-2-h-80-divinycell-plain-sheet-48-x-96/"],
    notes="Cabin floor, bulkheads, seat pans, tail panels. Epoxy-compatible, CNC-routable.")

add(id="MAT-FOAM-ROHACELL", category="material", role=["core"], status="alternate",
    name="Rohacell IG-F 31 PMI foam 48 x 96 x 0.460 in", maker="Evonik (via Rock West)", mass_kg=None,
    ratings={"density_kg_m3": 31},
    price=P(566.99, unit="sheet", source="https://www.rockwestcomposites.com/roh-igf31-0460-d.html", note="freight crate extra"),
    sources=["https://www.rockwestcomposites.com/roh-igf31-0460-d.html",
             "https://performance-foams.evonik.com/en/products-and-solutions/rohacell/rohacell-ig-f-170038.html"],
    notes="Lighter, higher temperature (post-cure friendly) but ~3x cost of PVC; for weight-critical panels only.")

add(id="MAT-ADH-EA9394", category="material", role=["bonding"], status="shortlist",
    name="Loctite EA 9394 AERO structural paste adhesive, quart kit", maker="Henkel", mass_kg=None, ratings={},
    price=P(353.10, unit="quart kit", source="https://skygeek.com/henkel-hysol-ea-9394-high-temperature-filled-paste-quart-system-as9277016.html"),
    sources=["https://skygeek.com/henkel-hysol-ea-9394-high-temperature-filled-paste-quart-system-as9277016.html"],
    notes="Metal-to-composite fittings (boom clamps, motor mounts). Plexus MA530: no published price found - quote.")

add(id="MAT-AL-6061-SHEET", category="material", role=["fittings", "battery box"], status="shortlist",
    name="Aluminium 6061-T6 sheet 0.063 x 24 x 36 in", maker="Online Metals (via Zoro)", mass_kg=None, ratings={},
    price=P(62.75, source="https://zoro.com/onlinemetals-0063-aluminum-sheet-6061-t6-1242/i/G307151068"),
    sources=["https://zoro.com/onlinemetals-0063-aluminum-sheet-6061-t6-1242/i/G307151068",
             "https://aircraftspruce.com/catalog/mepages/6061t6.php"],
    notes="Plate (6.35-25 mm) for motor mounts and boom clamps: quote by cut size from Online Metals/Metals Depot.")

add(id="MAT-4130", category="material", role=["cage", "gear"], status="alternate",
    name="4130 steel tube (Aircraft Spruce, pre-cut lengths)", maker="Aircraft Spruce", mass_kg=None,
    ratings={"example": "1 x 1 x 0.049 in square, 0.6337 lb/ft"},
    price=P(22.50, unit="see note", source="https://www.aircraftspruce.com/catalog/pnpages/03-13500.php",
            note="Listing price; unit (per ft or per piece) not stated on the page."),
    sources=["https://www.aircraftspruce.com/catalog/pnpages/03-13500.php", "https://www.aircraftspruce.com/pdf/2026Individual/2026_ME.pdf"],
    notes="Only if the outsourced welded cabin cage option is taken.")

add(id="MAT-FASTENERS", category="material", role=["hardware"], status="shortlist",
    name="AN/MS hardware (AN4 bolts, MS21042 nuts, CherryMAX rivets)", maker="various", mass_kg=None, ratings={},
    price=P(1.06, unit="AN4-5 bolt", source="https://www.airpowerinc.com/an4-5",
            note="MS21042-3 USD 0.32, -4 USD 0.48; CherryMAX CR3212-4-3 USD 0.81 (Van's store)."),
    sources=["https://www.airpowerinc.com/an4-5",
             "https://store.vansaircraft.com/kits-components/rv-12-kit/fuselage-11/rv-12-12is-fuselage/hardware-259.html?p=3"],
    notes="Budget per aircraft set in pass 2 from the CAD fastener count.")


# =====================================================================================
# 9. PASS-2 ADDITIONS (final design, iteration 3; sources checked 2026-11-15)
# =====================================================================================
C2 = "2026-11-15"
add(id="CHUTE-GRS1190", category="parachute", role=["recovery"], status="shortlist", checked=C2,
    name="Galaxy GRS 6 990-1190 SDS/FF 245 m2", maker="Galaxy GRS (CZ)", mass_kg=28.9, mass_note="Soft B2 pack, total packed",
    ratings={"mtow_kg": "990 / 1190", "vne_kmh": "320 / 280", "opening_shock": "45.6 kN / 4.7 g at 990 kg; 48.8 kN / 4.2 g at 1190 kg",
             "descent_mps": "5.6-6.2 at 1000 m", "pack_cm": "B1 64x34x23; B2 63x38x21", "standard": "ASTM F2316-12"},
    price=Q(estimate=16000, basis="No published price; WP D estimate = GRS 6 800-990 estimate + ~15 % for the 245 m2 canopy (sizing/data.py)",
            source="https://galaxysky.cz/grs-6-990-1190-sds-ff-245m2-p44-en"),
    sources=["https://galaxysky.cz/grs-6-990-1190-sds-ff-245m2-p44-en"],
    notes="Use if MTOW grows above the 1,050 kg top variant of the GRS 6 800-990, or if Galaxy rates the 800-990 opening load "
          "too high at 1,043 kg. +7.2 kg vs the 800-990 system; lower descent rate.")

add(id="LG-OLEO", category="landing_gear", role=["gear"], status="shortlist", checked=C2,
    name="Air/oil (oleo-pneumatic) damper for the pivoting skid legs, 80 mm stroke, 517 mm eye-to-eye (x4)",
    maker="FOX Factory 2.0 Factory Series air shock class (or aircraft oleo strut by quote)", mass_kg=1.2, mass_note="CAD allowance (LG-DAMP)",
    ratings={"stroke_required_mm": 80, "eye_to_eye_extended_mm": 517, "peak_force_kN": 6.7,
             "reference_product": "FOX 2.0 Factory Series air shock, 1-1/4 in shaft, nitrogen air spring + oil damping"},
    price=Q(estimate=474.95, basis="Published FOX 2.0 Factory Series air shock prices USD 359.95-474.95 (9.35-16 in stroke versions); "
                                   "short-stroke/custom valving for 80 mm and 6.7 kN to be quoted. Aircraft oleo struts at Aircraft Spruce "
                                   "are USD 1,530-1,632 (Aeronca-type, not matched).",
            source="https://www.strutmasters.com/products/fox-factory-inc-980-02-236-fox-2-0-factory-series-air-shock"),
    sources=["https://www.strutmasters.com/products/fox-factory-inc-980-02-236-fox-2-0-factory-series-air-shock",
             "https://aircraftspruce.com/catalog/lgpages/oleoshockstrut.php"],
    notes="WP F phase 3: damper peak force 6.7 kN, 80 mm stroke (reserve drop uses 68 mm). Off-road shocks are not aviation "
          "parts: drop-test the gear with the chosen unit; spherical bearings at both eyes.")

add(id="HV-AL-CABLE", category="hv", role=["harness"], status="shortlist", checked=C2,
    name="Aluminium-conductor HV cable (single core, screened, 35 mm2 class) with bimetal lugs", maker="Coroplast / LEONI (quote)",
    mass_kg=None, ratings={"length_m": "~92 (design/selected_design.json hv_cable_length_m)", "voltage": ">= 1000 VDC rating required"},
    price=Q(estimate=20.3, unit="m", basis="No published price for aluminium HV cable; copper Coroplast 9-2611 35 mm2 screened HV cable "
                                           "GBP 15.99 (x1.27) used as an upper-bound reference",
            source="https://hilltop-products.co.uk//35mm-screened-automotive-high-voltage-electric-vehicle-cable-ev350-coroplast-9-2611.html"),
    sources=["https://hilltop-products.co.uk//35mm-screened-automotive-high-voltage-electric-vehicle-cable-ev350-coroplast-9-2611.html"],
    notes="WP D iteration 3 uses aluminium feeders (half the copper mass at equal resistance). Cross-section per run from WP D; "
          "REB 60 table asks for >= 25 mm2 copper. Termination with bimetal crimp lugs and contact grease; torque-seal.")

add(id="HV-DCDC-MW", category="hv", role=["avionics_power"], status="shortlist", checked=C2,
    name="Mean Well RSDH-300-24 DC-DC (250-1500 VDC in, 24 V 12.5 A, 300 W)", maker="Mean Well", mass_kg=None,
    ratings={"input_V": "250-1500 (800 nominal)", "output": "24 V / 12.5 A", "power_W": 300},
    price=P(136.89, source="https://www.digikey.sg/en/products/detail/mean-well-usa-inc/RSDH-300-24/18069326", type_="retail",
            note="DigiKey qty 1; Bravo Electro USD 99.80"),
    sources=["https://www.digikey.sg/en/products/detail/mean-well-usa-inc/RSDH-300-24/18069326", "https://bravoelectro.com/rsdh-300-24.html"],
    notes="Replaces HV-DCDC (Vicor, 250-425 V input) which does not cover the 148s bus (444-622 V). Two per HV bus side "
          "(4 total, 1.2 kW), diode-ORed with the 24 V LiFePO4 backup. Railway-type industrial unit: vibration and EMI test required.")

add(id="MAT-UD-CF", category="material", role=["laminate"], status="shortlist", checked=C2,
    name="Unidirectional carbon fabric 300 g/m2, 12k (Hyosung H2550), 50 in wide", maker="Composite Envisions", mass_kg=None,
    ratings={"areal_g_m2": 300, "width_in": 50},
    price=P(31.19, unit="yard", source="https://www.compositeenvisions.com/Carbon-Fiber-Fabric-Unidirectional-12k-8.8oz-300gsm-Hyosung-H2550",
            note="Listed range USD 4.16-31.19 by width/quantity; 50 in single-yard figure used (upper bound). ~303 yd in stock."),
    sources=["https://www.compositeenvisions.com/Carbon-Fiber-Fabric-Unidirectional-12k-8.8oz-300gsm-Hyosung-H2550"],
    notes="Spar caps, boom UD over-wrap, keel/frame straps (CAD settings call for UD 300 g/m2).")

add(id="MAT-GLASS-7781", category="material", role=["laminate"], status="shortlist", checked=C2,
    name="E-glass fabric style 7781, 8.95 oz/yd2 (303 g/m2), 50 in", maker="Aircraft Spruce (7781-50)", mass_kg=None,
    ratings={"areal_g_m2": 303},
    price=P(13.65, unit="yard", source="https://www.aircraftspruce.com/catalog/cmpages/7781.php"),
    sources=["https://www.aircraftspruce.com/catalog/cmpages/7781.php"], notes="Fuselage shell, fairings, hatches, tapes.")

add(id="MAT-FOAM-H45", category="material", role=["core"], status="shortlist", checked=C2,
    name="Divinycell H45 PVC foam (Aircraft Spruce sheets)", maker="Diab (via Aircraft Spruce)", mass_kg=None,
    ratings={"density_kg_m3": 48, "sheets": "2 in 48x96 USD 778.00 (01-12920); 5/8 in 32x48 USD 75.85 (01-12500)"},
    price=P(778.00, unit="2 in 48x96 sheet", source="https://aircraftspruce.com/catalog/cmpages/divinycellfoam.php"),
    sources=["https://aircraftspruce.com/catalog/cmpages/divinycellfoam.php"], notes="Main-spar box foam W-SPM-F, 15 mm strip W-SPM-S.")

add(id="MAT-FOAM-H100", category="material", role=["core"], status="shortlist", checked=C2,
    name="Divinycell H100 1 in x 42 x 85 in plain sheet", maker="Diab (via Bluewater Supply)", mass_kg=None,
    ratings={"density_kg_m3": 100},
    price=P(510.52, unit="sheet", source="https://bluewatersupply.com/resources/catalog/2025/13", type_="list", note="2025 catalog"),
    sources=["https://bluewatersupply.com/resources/catalog/2025/13"], notes="Seat crush blocks SEAT-EA (bonded layers).")

add(id="MAT-FOAM-H80-12", category="material", role=["core"], status="shortlist", checked=C2,
    name="Divinycell H80 1/2 in plain sheet 48 x 96 in", maker="Diab (via Fiberglass Supply)", mass_kg=None, ratings={"density_kg_m3": 80},
    price=P(208.95, unit="sheet", source="https://fiberglasssupply.com/sheet-1-2-h-80-divinycell-plain-sheet-48-x-96/"),
    sources=["https://fiberglasssupply.com/sheet-1-2-h-80-divinycell-plain-sheet-48-x-96/"], notes="Nose crush block NOSE-EA (stacked).")

add(id="MAT-XPS", category="material", role=["core", "tooling"], status="shortlist", checked=C2,
    name="XPS foam board Owens Corning FOAMULAR 250, 2 in x 4 x 8 ft", maker="Owens Corning", mass_kg=None, ratings={"thickness_mm": 50.8},
    price=P(57.08, unit="board", source="https://superarbor.io/products/1631292-owens-corningr-foamularr-250-25-psi-r-10-extruded-polystyrene-foam-board-insulation-2-x-4-x-8-scored-square-edge"),
    sources=["https://superarbor.io/products/1631292-owens-corningr-foamularr-250-25-psi-r-10-extruded-polystyrene-foam-board-insulation-2-x-4-x-8-scored-square-edge"],
    notes="Wing/tail/control-surface cores (epoxy only) and the moldless shell plugs (laminated blocks). Building-supply product: "
          "check density and adhesion on coupons.")

add(id="MAT-MDF", category="material", role=["tooling"], status="shortlist", checked=C2,
    name="MDF 3/4 in x 4 x 8 ft", maker="Home Depot (typical)", mass_kg=None, ratings={},
    price=P(48.98, unit="sheet", type_="estimate", source="https://www.thepricer.org/the-cost-of-plywood/",
            note="Price guide figure for Home Depot (reviewed Jan 2026); not verified on the retailer page."),
    sources=["https://www.thepricer.org/the-cost-of-plywood/"], notes="Cap jigs, hot-wire templates, cradles, canopy plug.")

add(id="MAT-G10", category="material", role=["battery"], status="shortlist", checked=C2,
    name="G10/FR4 sheet 3/16 in x 12 x 24 in", maker="USA Sealing (via Hanes Supply)", mass_kg=None, ratings={"thickness_mm": 4.76},
    price=P(34.85, unit="sheet", source="https://www.hanessupply.com/usasealing-bulk-cs-gfr4-30"),
    sources=["https://www.hanessupply.com/usasealing-bulk-cs-gfr4-30"],
    notes="Cell holder plates (CAD: 5 mm G10, waterjet-cut); 3/16 in is the nearest stock thickness - confirm with WP G.")

add(id="MAT-CU-STRIP", category="material", role=["battery"], status="alternate", checked=C2,
    name="Copper bus strip 0.2 x 31 mm for 21700 (per metre)", maker="eBay listing", mass_kg=None, ratings={},
    price=P(8.99, unit="m", source="https://www.ebay.com/itm/305567325562", note="retail single metre; bulk nickel-plated copper by quote"),
    sources=["https://www.ebay.com/itm/305567325562"], notes="CAD calls for nickel-plated copper laser-welded strips; buy plated stock in bulk by quote.")

add(id="MAT-AL-PLATE", category="material", role=["fittings"], status="shortlist", checked=C2,
    name="Aluminium 6061 plate 1/2 x 12 x 24 in (price basis for all 6061 plate/bar)", maker="Zoro", mass_kg=6.37,
    ratings={"usd_per_kg": 23.5},
    price=P(149.99, unit="plate", source="https://www.zoro.com/zoro-select-aluminum-plate-6061-24-in-overall-l-12501224/i/G205374453"),
    sources=["https://www.zoro.com/zoro-select-aluminum-plate-6061-24-in-overall-l-12501224/i/G205374453"],
    notes="USD/kg derived (149.99 / 6.37 kg) and applied to other 6061 plate and bar (estimate).")

add(id="MAT-AL7075-PLATE", category="material", role=["fittings"], status="shortlist", checked=C2,
    name="Aluminium 7075-T651 plate 1-1/2 x 12 x 12 in (price basis for 7075)", maker="Speedy Metals", mass_kg=9.9,
    ratings={"usd_per_kg": 27.3},
    price=P(269.97, unit="plate", source="https://www.speedymetals.com/p-2730-1-12-7075-t651-aluminum-plate.aspx"),
    sources=["https://www.speedymetals.com/p-2730-1-12-7075-t651-aluminum-plate.aspx"], notes="Wing-root lugs and seat fittings (12-14 mm plate by quote).")

add(id="MAT-AL-TUBE", category="material", role=["gear", "pylon"], status="shortlist", checked=C2,
    name="6061-T6 round tube (Aircraft Spruce, per ft)", maker="Aircraft Spruce", mass_kg=None,
    ratings={"2-1/4 x .125": "USD 21.70/ft (03-38310)", "3 x .065": "USD 23.75/ft (03-38340)"},
    price=P(21.70, unit="ft", source="https://www.aircraftspruce.com/catalog/mepages/alumtube_6061t6.php"),
    sources=["https://www.aircraftspruce.com/catalog/mepages/alumtube_6061t6.php", "https://speedymetals.com/p-4618-3-od-x-0125-wall-tube-6061-t6-aluminum.aspx"],
    notes="Skids (CAD 60 x 3.2 mm: nearest inch stock 2-1/4 x 0.125), gear legs (CAD 76 x 2.0: 3 x 0.083 by quote), pylons 100 x 1.6 by quote.")

add(id="MAT-SEAT-TRACK", category="material", role=["cabin"], status="shortlist", checked=C2,
    name="Brownline-style seat track extrusion (05-07172), per inch", maker="McFarlane via Aircraft Spruce", mass_kg=None, ratings={},
    price=P(4.65, unit="inch", source="https://www.aircraftspruce.com/catalog/pnpages/05-07172.php", note="+ USD 30 cut fee per order"),
    sources=["https://www.aircraftspruce.com/catalog/pnpages/05-07172.php"], notes="SR seat rails 4 x 600 mm.")

add(id="MAT-UHMW", category="material", role=["gear"], status="shortlist", checked=C2,
    name="UHMW-PE sheet 3/4 x 12 x 48 in", maker="USA Industrials (via Zoro)", mass_kg=None, ratings={},
    price=P(147.99, unit="sheet", source="https://www.zoro.com/usa-industrials-uhmw-polyethylene-48-l-x-12-w-x-34-thick-bulk-ps-uhmw-355/i/G300437510/"),
    sources=["https://www.zoro.com/usa-industrials-uhmw-polyethylene-48-l-x-12-w-x-34-thick-bulk-ps-uhmw-355/i/G300437510/"], notes="Skid shoes LG-SHOE, skid end plugs.")

add(id="MAT-4130-PLATE", category="material", role=["fittings"], status="shortlist", checked=C2,
    name="4130 alloy steel plate 1/2 in (annealed), size per order", maker="Online Metals", mass_kg=None, ratings={},
    price=P(306.33, unit="plate", source="https://www.onlinemetals.com/en/buy/alloy-steel-sheet-plate-4130-annealed",
            note="listing size not captured - confirm; parts need 12 mm, normalized after machining or ordered N"),
    sources=["https://www.onlinemetals.com/en/buy/alloy-steel-sheet-plate-4130-annealed"], notes="Parachute fittings W-CHUTE-FIT x2, CH-ATT-R.")

add(id="MAT-BAGGING", category="material", role=["consumable"], status="shortlist", checked=C2,
    name="Vacuum-bagging consumables (US Composites): nylon bag film 110 in, breather 4 oz 60 in, peel ply 60 in, perforated film 60 in, sealant tape",
    maker="US Composites", mass_kg=None,
    ratings={"bag_film": "USD 4.95/yd (25+)", "breather_4oz": "USD 4.30/yd (25+)", "peel_ply": "USD 5.55/yd (25+)",
             "perforated_film": "USD 6.50/yd (25+)", "sealant_tape": "USD 7.15/roll 25 ft (10+)"},
    price=P(5.55, unit="yard (peel ply)", source="https://uscomposites.com/vacuum.html"),
    sources=["https://uscomposites.com/vacuum.html"], notes="Quantities from the bagged laminate area (bom/build_bom.py).")


# =====================================================================================
# 10. ITERATION 3.3 (frozen design ALL_rpmfree; WP D additions of 2026-11-18 carried into this generator)
# =====================================================================================
def _upd(cid, **kw):
    for it in ITEMS:
        if it["id"] == cid:
            it.update(kw)
            return it
    raise KeyError(cid)


_upd("MOT-EMRAX268", role=["lift"], status="shortlist", checked="2026-11-18",
     name='EMRAX 268 MV (axial flux) - E8-200 lift motor (x8), iteration 3.3',
     price={'value': None, 'currency': 'USD', 'unit': 'each', 'type': 'quote_required', 'estimate': 12000, 'estimate_basis': 'No published price; EMRAX sells by quotation. WP D estimate scaled to the MGM REB 90 class mid (USD 8-14 k); quote required (manufacturing/QUOTES_TO_REQUEST.md)', 'source': 'https://emrax.com/get-a-quote/'},
     notes='Iteration 3.3 lift motor, direct drive at about 1,900 rpm hover; ratings used: 500 N m peak, 205 N m / 91 kW LC continuous (published datasheet). Winding for the 175-180s bus (525-756 V) to be confirmed with EMRAX; liquid cooled.' + " Each station needs a coolant loop (COOL-MOT) and the MP-EMX adapter plate. EMRAX states the 188-348 range is "
           "being replaced by a next-generation range with the same envelope: quote the successor.")
add(**{'id': 'CHUTE-GRS1390', 'category': 'parachute', 'role': ['recovery'], 'status': 'shortlist', 'checked': '2026-11-18', 'name': 'Galaxy GRS 6 1200-1390 SDS/FF 245 m2', 'maker': 'Galaxy GRS (CZ)', 'mass_kg': 28.9, 'mass_note': 'Soft B2 pack, total packed (+-4 %)', 'ratings': {'mtow_kg': '1200 / 1390', 'vne_kmh': '280 / 260', 'opening_shock': '48.8 kN / 4.2 g at 1200 kg; 57.4 kN / 4.2 g at 1390 kg; 57.8 kN at 250 km/h', 'max_load_kg': '1500 at 250 km/h', 'descent_mps': '6.3-6.7 at 1000 m AMSL; 6.5-6.9 at 1500 m (MTOW)', 'min_rescue_height_m': '150 at 95 km/h, horizontal flight', 'pack_cm': 'B1 64x34x23; B2 63x38x21'}, 'price': {'value': None, 'currency': 'USD', 'unit': 'each', 'type': 'quote_required', 'estimate': 17000, 'estimate_basis': 'No published price; WP D estimate = GRS 6 990-1190 estimate (same 245 m2 canopy) + about USD 1k for the heavier rigging (sizing/data.py)', 'source': 'https://galaxysky.cz/grs-6-1200-1390-sds-ff-245m2-p45-en'}, 'sources': ['https://galaxysky.cz/grs-6-1200-1390-sds-ff-245m2-p45-en'], 'notes': 'Iteration 3.3 recovery system (MTOW 1,350 kg on the 1,390 kg variant). Same canopy area and packed mass as the 990-1190; higher opening shock (57.4 kN) for the airframe attachment loads.'})
_upd("MOT-REB90", status="shortlist", role=["pusher"], name="MGM COMPRO REB 90 (80 kW) - E8-200 boom-tail pusher (x2)")
_upd("MOT-REB60", status="alternate", name="MGM COMPRO REB 60 (60 kW)")
_upd("CHUTE-GRS1190", status="alternate")

SHORTLIST = {
    "final_design_iteration3_3": {
        "lift": "8 x MOT-EMRAX268 (liquid cooled) + 8 x INV-HBCI400800 + 8 x PROP-EPROPS-UAV-ADJ 1.85 m 2-blade (4 CW + 4 CCW)",
        "pusher": "2 x MOT-REB90 + 2 x INV-HBCI400800 on the boom tails + 2 x PROP-EPROPS-UAV-ADJ 1.75 m 2-blade, same rotation (PROP-PCW)",
        "battery": "4 packs 175s5p CELL-P50B (3,500 cells, 63 kWh), BMS-ORION2 per pack, HV-EV200 + HV-FUSE, HV-AL-CABLE feeders",
        "parachute": "CHUTE-GRS1390 (MTOW 1,350 kg)",
        "fcc": "FCC-VERONTE4X with rotor rpm cap (FCC-CUBE-ORANGEP for the uncrewed phase)",
        "gear": "pivoting skid legs (3 x 0.095 in), 2-1/4 x 0.125 in skids, 4 x LG-OLEO",
        "bom": "bom/BOM.csv, bom/BOM.md",
    },
    "selection_rule": "From validation/parts/check_propulsion.py: 8 lift rotors of ~1.8-1.9 m. MTOW <= 700 kg -> REB 30 "
                      "+ HBCi 100400 on a 94s (~340 V nominal, 395 V max) bus; MTOW 700-900 kg -> REB 50 on a 180s "
                      "(~650 V) bus with an 800 V MGM inverter. Six rotors fail the one-motor-out torque check above "
                      "~600 kg with every motor screened.",
    "lift_motor": ["MOT-REB30 (MTOW <= 700 kg, 8 rotors)", "MOT-REB50 (MTOW 700-900 kg, 8 rotors)",
                   "alternates: MOT-MAD-M90C60 (power fits; no torque rating published), MOT-TM-S150 (data sparse)"],
    "lift_inverter": ["INV-HBCI100400 with REB 30", "INV-HBCI400800 with REB 50 (oversized; request a smaller 800 V unit)"],
    "lift_rotor": ["PROP-EPROPS-UAV-ADJ (matched CW/CCW to 1.90 m)", "PROP-SENSENICH-UAV (to 2.48 m)", "PROP-HELIX (to 2.8 m)"],
    "pusher": ["MOT-REB90 + INV-HBCI400800 when cruise shaft power is 30-60 kW continuous",
               "MOT-REB50 (same type as lift) if WP D shows <= 30 kW continuous cruise",
               "propeller: PROP-EPROPS-UAV-ADJ / PROP-SENSENICH-UAV / PROP-DUC-SWIRL, 1.6-1.9 m"],
    "cells": ["CELL-P50B (baseline)", "CELL-SAM50S (second source)", "CELL-AMPRIUS (growth)"],
    "bms": ["BMS-ORION2 one per pack"],
    "parachute": ["CHUTE-MAG601 if MTOW <= 757 kg", "CHUTE-MAG901 if MTOW <= 950 kg", "Galaxy GRS 6 equivalents by quote"],
    "fcc": ["FCC-VERONTE4X (crewed)", "FCC-CUBE-ORANGEP (uncrewed test phase / HIL)"],
    "not_viable_for_baseline": ["MOT-U15XXL kit: fails one-motor-out at 1000 m ISA+15 even at 500 kg (8 rotors)",
                                "EMRAX as direct-drive lift motor: continuous torque too low above ~600 kg",
                                "MOT-HW-P50M: 50 kgf per axis"],
}

CATEGORY_TITLES = [
    ("motor", "Lift and pusher motors"), ("inverter", "Inverters / ESCs"), ("propeller", "Propellers and rotors"),
    ("cell", "Battery cells"), ("pack", "Commercial packs (benchmarks)"), ("bms", "Battery management"),
    ("hv", "HV distribution and power conversion"), ("parachute", "Ballistic parachutes"),
    ("avionics", "Flight control and avionics"), ("cabin", "Cabin and canopy"), ("landing_gear", "Landing gear"),
    ("material", "Raw materials and hardware"),
]


def fmt_price(p):
    cur = {"USD": "USD ", "EUR": "EUR ", "GBP": "GBP "}.get(p.get("currency"), p.get("currency", "") + " ")
    if p["type"] == "quote_required":
        est = p.get("estimate")
        if est is None:
            return "quote required"
        if isinstance(est, list):
            return f"quote required (est. {cur}{est[0]:,}-{est[1]:,})"
        return f"quote required (ref. {cur}{est:,})"
    v = p["value"]
    s = f"{cur}{v:,.2f}" if isinstance(v, float) else f"{cur}{v:,}"
    unit = p.get("unit", "each")
    return s + ("" if unit == "each" else f" / {unit}")


def fmt_ratings(r):
    parts = []
    for k, v in r.items():
        parts.append(f"{k}: {v}")
    return "; ".join(parts)


def main():
    data = {
        "_meta": {
            "title": "E8-200 COTS component catalog (work package P, pass 1)",
            "checked": CHECKED,
            "conventions": "Numbers carry a source URL; price.type is list | retail | dealer | reseller | "
                           "quote_required | estimate. Currency as published, no FX conversion. "
                           "quote_required entries give the best published estimate and its basis.",
            "status_values": ["shortlist", "alternate", "reference", "not_recommended"],
            "generator": "bom/build_catalog.py",
            "export_control_note": "From 18 Nov 2026 China requires export licences for drone motors (>=48 V, >=3 kW, "
                                   ">=3 kW/kg, <=3000 rpm), matching ESCs and carbon blades > 30 in radius (MOFCOM "
                                   "announcement reported by DroneXL, " + EXPORT_RULE + "). Applies to all Chinese "
                                   "heavy-lift propulsion in this catalog.",
        },
        "shortlist": SHORTLIST,
        "items": ITEMS,
    }
    (HERE / "catalog.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    lines = []
    lines.append("# E8-200 COTS component catalog")
    lines.append("")
    lines.append(f"Work package P, pass 1. Sources checked {CHECKED}. Machine-readable data: "
                 "[catalog.json](catalog.json) (generated together with this page by "
                 "[build_catalog.py](build_catalog.py); edit the script, not the outputs).")
    lines.append("")
    lines.append("Every number has a source link in `catalog.json`. Prices are in the currency in which they were "
                 "published; *quote required* items show the nearest published figure and how it was derived. "
                 "Status: **shortlist** = baseline choice, *alternate* = qualified fallback, reference = benchmark only, "
                 "not recommended = screened out (kept for traceability).")
    lines.append("")
    lines.append("## Shortlist summary")
    lines.append("")
    lines.append(SUMMARY_MD.strip())
    lines.append("")
    for cat, title in CATEGORY_TITLES:
        rows = [i for i in ITEMS if i["category"] == cat]
        if not rows:
            continue
        lines.append(f"## {title}")
        lines.append("")
        lines.append("| ID | Status | Item | Mass (kg) | Key ratings | Price | Source |")
        lines.append("|---|---|---|---|---|---|---|")
        for i in rows:
            m = "-" if i.get("mass_kg") is None else f"{i['mass_kg']:g}"
            if i.get("mass_note"):
                m += f" ({i['mass_note']})"
            src = i["sources"][0] if i.get("sources") else (i["price"].get("source") or "")
            srcmd = f"[link]({src})" if src else "-"
            st = {"shortlist": "**shortlist**", "alternate": "alternate", "reference": "reference",
                  "not_recommended": "not recommended"}[i["status"]]
            rat = fmt_ratings(i.get("ratings", {})).replace("|", "/")
            lines.append(f"| {i['id']} | {st} | {i['name']} | {m} | {rat} | {fmt_price(i['price'])} | {srcmd} |")
        lines.append("")
        for i in rows:
            if i.get("notes"):
                lines.append(f"- **{i['id']}**: {i['notes']}")
        lines.append("")
    lines.append(TAIL_MD.strip())
    lines.append("")
    (HERE / "CATALOG.md").write_text("\n".join(lines))
    print(f"wrote {len(ITEMS)} items to catalog.json and CATALOG.md")


SUMMARY_MD = """
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
"""

TAIL_MD = """
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
"""

if __name__ == "__main__":
    main()
