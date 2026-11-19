"""Material property and design-allowable database for the E8-200 structure -> fea/materials.json.

    ~/tools/cadenv/bin/python fea/materials.py          # regenerate fea/materials.json

Every entry keeps the 'typical' (mean / datasheet) values, the knock-down factors applied and the
resulting 'design' (ultimate, per-ply or per-material) allowables, with the sources.  Design allowables
are compared with ULTIMATE stresses (limit load x 1.5) multiplied by the highest pertinent special factor
(fitting 1.15, bearing, bonded-joint, seat-attachment), see POLICY below and fea/README.md.

Status flags:  'datasheet' (value read from the linked source), 'handbook' (MIL-HDBK-5J / MMPDS-style
design value), 'estimate' (engineering estimate from fibre/matrix data and handbook ranges; to be replaced
by the coupon programme listed in POLICY['coupon_programme']).
All values SI: Pa, kg/m^3.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
KSI = 6.894757e6
MSI = 6.894757e9

SRC = {
    "cmh17_v1": "https://www.cmh17.org/ (CMH-17-1G Vol. 1, ch. 8: statistical B-basis; Vol. 3: design guidance)",
    "cmh17_v2_wetlayup": "https://www.wichita.edu/industry_and_defense/NIAR/Documents/Vol-2-TOC.pdf (CMH-17 Vol. 2 contents: "
                         "carbon/epoxy wet lay-up fabric data, HTA 5131 3k / Epocast A/B)",
    "agate_t700": "https://thyme.ornl.gov/CFCrush/materials/cmh17/wp3.3-033051-134.pdf (AGATE WP3.3-033051-134: T700SC 12K PW "
                  "/ #2510 B-basis allowables - prepreg upper bound for the wet lay-up estimates)",
    "faa_ar0319": "https://www.tc.faa.gov/its/worldpac/techrpt/ar03-19.pdf (DOT/FAA/AR-03/19 material qualification and "
                  "equivalency for polymer matrix composites)",
    "ac20_107b": "https://www.faa.gov/documentLibrary/media/Advisory_Circular/AC_20-107B.pdf (composite aircraft structure: "
                 "environment, variability, damage tolerance)",
    "toray_t700s": "https://www.toraycma.com/wp-content/uploads/T700S-Technical-Data-Sheet-1.pdf.pdf (T700S fibre: 4900 MPa, 230 GPa)",
    "rockwest_ud_tube": "https://www.rockwestcomposites.com/45625 (roll-wrapped unidirectional tube: E 15.4 Msi, Ftu 143 ksi, Tg 238 F)",
    "rockwest_rollwrapped": "https://www.rockwestcomposites.com/tubing/round-tubing/round-carbon-fiber-tubing/roll-wrapped-carbon-fiber-tubing",
    "rockwest_pw_hm": "https://sfccdev.rockwestcomposites.com/45162-hm.html (plain-weave tube: tensile modulus 16.15 Msi listing)",
    "dragonplate_tube": "https://DragonPlate.com/Images/uploaded/Weights%20and%20Specs/DPSpecRoundTube.pdf (DragonPlate round tube spec)",
    "dragonplate_rollwrapped": "https://dragonplate.com/carbon-fiber-roll-wrapped-uni-tube-1125-id-x-72-gloss-finish-2 (33 Msi SM fibre, Tg 250 F)",
    "dragonplate_pultruded": "https://tools.dragonplate.com/category/pultruded-carbon-fiber-tube",
    "divinycell_h80": "https://www.r-g.de/en/art/5800H80 (Divinycell H80: compression 1.4/1.15 MPa, modulus 90/80, shear 1.15/0.95, G 27/23 MPa nominal/min)",
    "divinycell_h_ds": "https://www.boatbuildercentral.com/MSDS/Diab-Divinycell-H-June-2020-rev19-SI.pdf (Diab Divinycell H data sheet, SI)",
    "divinycell_h100": "https://DragonPlate.com/Images/uploaded/Weights%20and%20Specs/divinycell.pdf (H100: compression 2.0, modulus 135, shear 1.6, G 35 MPa)",
    "rohacell_wf": "https://products.evonik.com/assets/23/50/ROHACELL_WF_and_WF_HT_May_2026_EN_Asset_4252350.pdf (ROHACELL WF / WF-HT)",
    "rohacell_71wf_alt": "https://mychem.ir/uploads/tds/16740.pdf (71 WF: shear 1.3 MPa, G 42 MPa, compression 1.7 MPa)",
    "milhdbk5j": "https://everyspec.com/MIL-HDBK/MIL-HDBK-0001-0099/MIL_HDBK_5J_139/ (MIL-HDBK-5J, 2003 = MMPDS-01 basis)",
    "adm": "Aluminum Association, Aluminum Design Manual (2020), Table A.3.4: welded 6061-T6 Ftuw 24 ksi, Ftyw 15 ksi",
    "ea9394": "https://dm.henkel-dam.com/is/content/henkel/EA-9394-Aero (LOCTITE EA 9394 AERO TDS: lap shear 28.9 MPa at 25 C, "
              "20.7 MPa at 82 C, 2024-T3 PAA, ASTM D1002)",
    "ma530": "https://itwperformancepolymers.com/wp-content/uploads/Plexus-MA530-TDS-_de-DE.pdf ; "
             "https://www.chemical-concepts.com/wp-content/uploads/2023/02/Plexus-ma530-TDS.pdf (Plexus MA530 TDS rev 14: lap shear "
             "cohesive 11.7-17.2 MPa, tensile 17-24 MPa, elongation 90-160 %, -40 to 82 C)",
    "xps_ravago": "https://ravagobuildingsolutions.com/industry/wp-content/uploads/sites/24/2025/06/2-tds-rt-xps-lb-gv-en-250528.pdf "
                  "(Ravago XPS technical sheets: compressive modulus 10-15 MPa (EN 826), shear modulus 7-8 MPa (EN 12090), typical)",
    "xps_styrofoam": "https://images.greenbuildingadvisor.com/app/uploads/2021/08/28121913/XPS-spec.pdf (XPS compressive modulus by grade, "
                     "900 psi = 6.2 MPa for ASTM C578 Type IV up to 25.5 MPa)",
    "cs23": "https://www.easa.europa.eu/en/document-library/certification-specifications/cs-23-amendment-4 (CS-23 Amdt 4: "
            "23.303, 23.619, 23.623, 23.625, 23.657, 23.693, 23.785)",
}

POLICY = {
    "ultimate_factor": 1.5,
    "special_factors": {
        "fitting": {"value": 1.15, "ref": "CS-23.625 (Amdt 4); also applied to rotor-motor mounts, boom-wing saddles, wing root fittings, "
                                           "landing-gear and parachute hard points, up to the point where the section becomes typical of the member"},
        "seat_harness_attachment": {"value": 1.33, "ref": "CS-23.785(f): seat, berth and safety-belt/harness attachments to structure"},
        "bearing_relative_motion": {"value": 2.0, "ref": "CS-23.623(a) requires a bearing factor 'large enough' for joints with clearance "
                                                        "under pounding or vibration; team value 2.0 on the ultimate bearing strength"},
        "control_system_joint": {"value": 3.33, "ref": "CS-23.693: joints in push-pull systems subject to angular motion (except ball/roller bearings)"},
        "control_surface_hinge": {"value": 6.67, "ref": "CS-23.657 via 23.623(b): plain-bearing hinges, on the ultimate bearing strength of the softest material"},
        "bonded_joint": {"value": 1.5, "ref": "team rule for structural adhesive joints until joint-level tests exist (not a CS-23 number)"},
        "combination": "CS-23.619: only the highest pertinent special factor is applied (factors are not multiplied together); "
                       "the fitting factor is not combined with a larger bearing factor (CS-23.625(b)).",
    },
    "composite_knockdowns": {
        "k_B_fibre": {"value": 0.85, "basis": "B-basis estimate = mean x (1 - k_B CV), CV 8 %, k_B ~1.8 (normal, n ~ 15-18), CMH-17-1G ch. 8"},
        "k_B_matrix": {"value": 0.80, "basis": "as above with CV 10-11 % typical of wet lay-up matrix-dominated properties"},
        "k_env_tension": {"value": 0.95, "basis": "hot/wet (60 C, moisture-saturated) for room-temperature-cure laminating epoxy, "
                                                  "post-cured 16 h at 60-80 C, Tg(wet) >= 80 C (AC 20-107B, MCT = Tg(wet) - 28 C rule)"},
        "k_env_compression": {"value": 0.80, "basis": "hot/wet, fibre-microbuckling is matrix-supported"},
        "k_env_matrix": {"value": 0.75, "basis": "hot/wet in-plane shear, transverse and interlaminar strengths"},
        "k_env_modulus_matrix": {"value": 0.90, "basis": "E2, G12 at hot/wet; fibre-direction modulus unchanged"},
        "k_process": {"value": 0.90, "basis": "wet lay-up part versus coupon: porosity, thickness/Vf scatter, fibre waviness; "
                                              "removed only with coupons cut from production witness panels"},
        "damage_tolerance_strain_cutoff": {"tension": 0.0050, "compression": 0.0040, "shear": 0.0080,
                                           "basis": "ultimate design strain cut-off covering barely visible impact damage and open "
                                                    "holes / fasteners (typical general-aviation practice, AC 20-107B sec. 8); the design "
                                                    "allowable is the lower of the strength product and E x cut-off"},
        "design_strength": "F_design = F_mean x k_B x k_env x k_process (then capped by the strain cut-off)",
        "temperature_limit": "white or light-grey paint on all composite primary structure; max structure temperature 60 C",
    },
    "metal_basis": "A-basis (or S-basis where only S is tabulated) for single-load-path parts, B-basis for redundant structure "
                   "(CS-23.613). Values from MIL-HDBK-5J; check against the current MMPDS before the final design review.",
    "printed_parts": "FDM parts are not used in primary structure or any load path whose failure is hazardous: tooling, jigs, "
                     "fairings, cable guides only. Values below are for jig/fixture sizing.",
    "coupon_programme": [
        "ASTM D3039 tension 0 deg and [0/90] (n >= 6 per condition, RTD and ETW 60 C saturated)",
        "ASTM D6641 combined-loading compression, same conditions",
        "ASTM D3518 +/-45 in-plane shear; ASTM D2344 short-beam shear on witness panels of each lay-up session",
        "ASTM D5766 open-hole tension / D6484 open-hole compression; ASTM D5961 bearing (bolted fittings)",
        "ASTM D7136/D7137 compression after impact for the BVID strain cut-off",
        "ASTM D5868 / D1002 lap shear of the chosen adhesive on the actual adherends (carbon/aluminium, abraded + primed)",
        "ASTM C273 core shear, C393/D7249 sandwich beam flexure, D7250 sandwich flexural/shear stiffness",
        "tube 4-point bending and torsion on 3 samples of each COTS tube batch (incoming inspection)",
        "burn-off / acid digestion (ASTM D3171) for fibre volume fraction of every witness panel",
    ],
}


def comp(mean, kB, kenv, kproc=POLICY["composite_knockdowns"]["k_process"]["value"]):
    return mean * kB * kenv * kproc


def build():
    K = POLICY["composite_knockdowns"]
    kBf, kBm = K["k_B_fibre"]["value"], K["k_B_matrix"]["value"]
    kt, kc, km, kEm = (K["k_env_tension"]["value"], K["k_env_compression"]["value"], K["k_env_matrix"]["value"],
                       K["k_env_modulus_matrix"]["value"])
    cut = K["damage_tolerance_strain_cutoff"]
    M = {}

    def lamina(key, name, typ, t_ply, Vf, rho, src, status, note):
        d = dict(Xt=min(comp(typ["Xt"], kBf, kt), cut["tension"] * typ["E1"]),
                 Xc=min(comp(typ["Xc"], kBf, kc), cut["compression"] * typ["E1"]),
                 Yt=comp(typ["Yt"], kBm, km), Yc=comp(typ["Yc"], kBm, km), S=min(comp(typ["S"], kBm, km), cut["shear"] * typ["G12"]),
                 E1=typ["E1"], E2=typ["E2"] * kEm, G12=typ["G12"] * kEm, nu12=typ["nu12"],
                 eps_t=cut["tension"], eps_c=cut["compression"], gamma=cut["shear"])
        if typ.get("ILSS"):
            d["ILSS"] = comp(typ["ILSS"], kBm, km)
        M[key] = dict(name=name, kind="lamina", process="wet lay-up, vacuum bag (>= 0.8 bar), RT cure + post-cure",
                      t_ply_m=t_ply, Vf=Vf, rho=rho, typical=typ, design=d, status=status, sources=src, note=note,
                      knockdowns=dict(fibre_tension=kBf * kt * K["k_process"]["value"], fibre_compression=kBf * kc * K["k_process"]["value"],
                                      matrix=kBm * km * K["k_process"]["value"], strain_cutoff=cut))

    lamina("cf_ud_wet", "Carbon UD (T700-class 12K, 300 g/m2 stitched UD) / laminating epoxy", dict(
        E1=115e9, E2=7.5e9, G12=3.8e9, nu12=0.30, Xt=1600e6, Xc=850e6, Yt=35e6, Yc=120e6, S=55e6, ILSS=45e6),
        0.30e-3, 0.50, 1500.0, ["toray_t700s", "cmh17_v2_wetlayup", "agate_t700", "faa_ar0319"], "estimate",
        "E1 by rule of mixtures (Vf 0.50, fibre 230 GPa); Xt = 0.65 x Vf x 4900 MPa translation for wet lay-up; Xc, matrix values "
        "from the CMH-17 Vol. 2 wet lay-up range. Used for spar caps and boom doublers.")
    lamina("cf_fabric_wet", "Carbon fabric 0/90 (3K 2x2 twill 200-245 g/m2, or 12K 400 g/m2) / laminating epoxy", dict(
        E1=52e9, E2=52e9, G12=3.8e9, nu12=0.05, Xt=550e6, Xc=450e6, Yt=550e6, Yc=450e6, S=75e6, ILSS=40e6),
        0.25e-3, 0.45, 1450.0, ["cmh17_v2_wetlayup", "agate_t700", "faa_ar0319"], "estimate",
        "Ply of balanced fabric treated as an orthotropic lamina (1 = warp). S is the +/-45 in-plane shear strength. Skins, webs, "
        "fittings, ribs (as +/-45 or 0/90 plies).")
    lamina("eglass_fabric_wet", "E-glass fabric (7781-style 300 g/m2 satin) / laminating epoxy", dict(
        E1=20e9, E2=20e9, G12=3.5e9, nu12=0.13, Xt=300e6, Xc=280e6, Yt=300e6, Yc=280e6, S=60e6, ILSS=35e6),
        0.25e-3, 0.40, 1800.0, ["cmh17_v2_wetlayup", "faa_ar0319"], "estimate",
        "Fairings, cabin shell secondary areas, galvanic isolation ply between carbon and aluminium.")

    # ---------------------------------------------------------------- COTS carbon tubes
    def tube(key, name, typ, rho, src, status, note, kc_extra=1.0):
        d = dict(E=typ["E"], G=typ["G"] * kEm,
                 Ft=min(typ["Ft"] * kBf * kt, cut["tension"] * typ["E"]),
                 Fc=min(typ["Fc"] * kBf * kc * kc_extra, cut["compression"] * typ["E"]),
                 Fs=min(typ["Fs"] * kBm * km, cut["shear"] * typ["G"]),
                 eps_t=cut["tension"], eps_c=cut["compression"])
        M[key] = dict(name=name, kind="tube", rho=rho, typical=typ, design=d, status=status, sources=src, note=note,
                      knockdowns=dict(tension=kBf * kt, compression=kBf * kc * kc_extra, shear=kBm * km, strain_cutoff=cut,
                                      process="none (autoclave/oven-cured prepreg by the supplier); incoming bend test per batch"))

    tube("cf_tube_rollwrapped_ud", "Roll-wrapped carbon tube, UD-dominated (Rock West 'unidirectional' / DragonPlate uni roll-wrapped)",
         dict(E=106e9, G=5.0e9, Ft=986e6, Fc=600e6, Fs=60e6, hoop="0/90 or +/-45 outer wraps (~15 % of wall)"),
         1550.0, ["rockwest_ud_tube", "rockwest_rollwrapped", "dragonplate_rollwrapped"], "datasheet (E, Ft) / estimate (Fc, G, Fs)",
         "E 15.4 Msi, Ftu 143 ksi from the Rock West listing; compression taken as 0.6 Ftu; G and torsional shear strength low "
         "(UD-dominated wall) - torsion-critical members use the twill or +/-45 tube. Booms and wing spar tubes.")
    tube("cf_tube_rollwrapped_twill", "Roll-wrapped carbon tube, 0/90 twill + UD (standard modulus)",
         dict(E=62e9, G=8.0e9, Ft=550e6, Fc=420e6, Fs=90e6),
         1550.0, ["rockwest_rollwrapped", "rockwest_pw_hm", "dragonplate_tube"], "estimate",
         "Typical 8-10 Msi axial modulus for twill/UD roll-wrapped tube; preferred where torsion or crushing at clamps matters.")
    tube("cf_tube_pultruded", "Pultruded carbon tube (UD, standard modulus)",
         dict(E=125e9, G=4.5e9, Ft=1400e6, Fc=900e6, Fs=40e6),
         1550.0, ["dragonplate_pultruded"], "estimate (no public strength data; vendor values to be obtained)",
         "Very weak in hoop/torsion and prone to splitting at clamps and holes: only for pin-ended struts and stiffeners with "
         "bonded sleeves; never drilled without an overwrapped insert.", kc_extra=0.9)

    # ---------------------------------------------------------------- cores
    def core(key, name, typ_min, rho, src, note, k_env=0.80):
        d = dict(E=typ_min["E_min"] * k_env, G=typ_min["G_min"] * k_env, Fs=typ_min["Fs_min"] * k_env, Fc=typ_min["Fc_min"] * k_env)
        M[key] = dict(name=name, kind="core", rho=rho, typical=typ_min, design=d, status="datasheet (minimum values)",
                      sources=src, note=note, knockdowns=dict(env_60C=k_env, basis="datasheet minimum values x 0.80 for 60 C "
                                                                                   "(PVC and PMI stiffness/strength loss) and moisture"))
    core("pvc_h80", "Divinycell H80 PVC foam (80 kg/m3)",
         dict(E_nom=90e6, E_min=80e6, G_nom=27e6, G_min=23e6, Fs_nom=1.15e6, Fs_min=0.95e6, Fc_nom=1.4e6, Fc_min=1.15e6, nu=0.32),
         80.0, ["divinycell_h80", "divinycell_h_ds"], "Skin and floor panels, ribs. Check face wrinkling (0.5 (Ef Ec Gc)^(1/3)) and core shear.")
    core("pvc_h100", "Divinycell H100 PVC foam (100 kg/m3)",
         dict(E_nom=135e6, E_min=115e6, G_nom=35e6, G_min=28e6, Fs_nom=1.6e6, Fs_min=1.4e6, Fc_nom=2.0e6, Fc_min=1.65e6, nu=0.32),
         100.0, ["divinycell_h100", "divinycell_h_ds"], "Spar webs, seat pan, battery tray, around inserts (potted).")
    core("pvc_h45", "Divinycell H45 PVC foam (48 kg/m3)",
         dict(E_nom=50e6, E_min=45e6, G_nom=15e6, G_min=12e6, Fs_nom=0.56e6, Fs_min=0.46e6, Fc_nom=0.6e6, Fc_min=0.5e6, nu=0.32),
         48.0, ["divinycell_h_ds"], "Main-spar box foam (iteration 3): stabilises the +-45 webs. Values from the Diab H table, to be "
         "confirmed against the current data-sheet revision.")
    core("xps_foam", "Extruded polystyrene (XPS) board, 30-35 kg/m3 (wing cores)",
         dict(E_nom=12e6, E_min=10e6, G_nom=7e6, G_min=6e6, Fs_nom=0.25e6, Fs_min=0.2e6, Fc_nom=0.3e6, Fc_min=0.25e6, nu=0.1),
         33.0, ["xps_ravago", "xps_styrofoam"], "Hot-wire cut wing cores; typical EN 826 / EN 12090 values (no design data): "
         "minimum assumed 0.85 x typical; visco-elastic (creep), keep sustained core stresses low.", k_env=0.8)
    core("pmi_71wf", "ROHACELL 71 WF PMI foam (75 kg/m3)",
         dict(E_nom=105e6, E_min=95e6, G_nom=42e6, G_min=29e6, Fs_nom=1.3e6, Fs_min=1.1e6, Fc_nom=1.7e6, Fc_min=1.5e6, nu=0.3),
         75.0, ["rohacell_wf", "rohacell_71wf_alt"], "Alternative where heat (post-cure up to 130 C) or creep matters; minimum values "
         "taken as 0.85-0.9 x nominal where the sheet gives nominal only (to confirm with Evonik).")

    # ---------------------------------------------------------------- metals (handbook S/A/B values)
    def metal(key, name, E, G, nu, rho, A, B, src, note, status="handbook"):
        M[key] = dict(name=name, kind="isotropic", E=E, G=G, nu=nu, rho=rho, A_basis=A, B_basis=B, design=dict(A, E=E, G=G, nu=nu),
                      status=status, sources=src, note=note,
                      knockdowns=dict(basis="A/S-basis for single load path, B-basis for redundant; temperature <= 60 C: no reduction"))
    metal("al6061_t6_sheet", "Aluminium 6061-T6 sheet (AMS 4027), 0.25-6 mm", 68.3e9, 26.2e9, 0.33, 2700.0,
          dict(Ftu=42 * KSI, Fty=36 * KSI, Fsu=27 * KSI, Fbru_eD2=88 * KSI, Fbry_eD2=58 * KSI),
          dict(Ftu=44 * KSI, Fty=38 * KSI, Fsu=28 * KSI, Fbru_eD2=92 * KSI, Fbry_eD2=61 * KSI),
          ["milhdbk5j"], "S-basis tabulated as A; B estimated +5 %. Brackets, ribs, doublers, flat waterjet parts.")
    metal("al6061_t6_extr", "Aluminium 6061-T6/T6511 extrusion (AMS-QQ-A-200/8)", 68.3e9, 26.2e9, 0.33, 2700.0,
          dict(Ftu=38 * KSI, Fty=35 * KSI, Fsu=24 * KSI, Fbru_eD2=80 * KSI, Fbry_eD2=56 * KSI),
          dict(Ftu=40 * KSI, Fty=37 * KSI, Fsu=25 * KSI, Fbru_eD2=84 * KSI, Fbry_eD2=59 * KSI),
          ["milhdbk5j"], "Angles, channels, tubes for the cabin frame, gear cross-tubes.")
    metal("al6061_t6_welded", "Aluminium 6061-T6, as-welded (heat-affected zone)", 68.3e9, 26.2e9, 0.33, 2700.0,
          dict(Ftu=24 * KSI, Fty=15 * KSI, Fsu=15 * KSI), dict(Ftu=24 * KSI, Fty=15 * KSI, Fsu=15 * KSI),
          ["adm"], "Within 25 mm of a weld. Welded aluminium is avoided in primary structure.")
    metal("al7075_t6_sheet", "Aluminium 7075-T6 sheet (QQ-A-250/12), 1.0-3.2 mm", 71.0e9, 26.9e9, 0.33, 2800.0,
          dict(Ftu=78 * KSI, Fty=69 * KSI, Fsu=47 * KSI, Fbru_eD2=148 * KSI, Fbry_eD2=111 * KSI),
          dict(Ftu=80 * KSI, Fty=71 * KSI, Fsu=48 * KSI, Fbru_eD2=152 * KSI, Fbry_eD2=114 * KSI),
          ["milhdbk5j"], "Machined fittings from plate use the plate table (lower ST values); no welding; notch-sensitive in fatigue.")
    metal("steel_4130_n", "4130 steel, normalized tube/sheet (MIL-T-6736 / AMS 6350), t <= 4.8 mm", 200e9, 75.8e9, 0.32, 7850.0,
          dict(Ftu=95 * KSI, Fty=75 * KSI, Fsu=57 * KSI, Fbru_eD2=200 * KSI, Fbry_eD2=129 * KSI),
          dict(Ftu=95 * KSI, Fty=75 * KSI, Fsu=57 * KSI, Fbru_eD2=200 * KSI, Fbry_eD2=129 * KSI),
          ["milhdbk5j"], "S-basis. Outsourced welded tube structure (cabin cage / gear) only if justified.")
    metal("steel_4130_welded", "4130 steel, fusion welded, not heat-treated after welding", 200e9, 75.8e9, 0.32, 7850.0,
          dict(Ftu=80 * KSI, Fty=60 * KSI, Fsu=48 * KSI), dict(Ftu=80 * KSI, Fty=60 * KSI, Fsu=48 * KSI),
          ["milhdbk5j"], "Joint allowable for welded clusters (MIL-HDBK-5J welded-joint section); Fty and Fsu estimated in "
          "proportion. To be confirmed before use.", status="handbook (Ftu) / estimate (Fty, Fsu)")
    metal("steel_an_bolt", "AN/NAS alloy steel bolt (125 ksi Ftu, 75 ksi Fsu)", 200e9, 77e9, 0.3, 7850.0,
          dict(Ftu=125 * KSI, Fsu=75 * KSI), dict(Ftu=125 * KSI, Fsu=75 * KSI), ["milhdbk5j"],
          "Shear on the shank area; bearing checked on the softer joint member.")

    # composite bearing (bolted fittings, quasi-isotropic carbon fabric)
    M["cf_fabric_wet_bearing"] = dict(name="Bolted bearing, quasi-isotropic carbon fabric wet lay-up, e/D >= 3, W/D >= 5, finger-tight + washers",
                                      kind="bearing", typical=dict(Fbru=600e6, Fbry_2pct=420e6), design=dict(Fbru=comp(600e6, kBm, km), Fbry=comp(420e6, kBm, km)),
                                      status="estimate", sources=["cmh17_v1", "faa_ar0319"],
                                      note="ASTM D5961 to be run. Bearing in wet lay-up laminates uses 2 % offset strength for limit and "
                                           "ultimate bearing x knock-downs for ultimate; bonded metal inserts preferred for rotor mounts.",
                                      knockdowns=dict(factor=kBm * km * POLICY["composite_knockdowns"]["k_process"]["value"]))

    # ---------------------------------------------------------------- adhesives
    def adhesive(key, name, typ, design_tau, src, note):
        M[key] = dict(name=name, kind="adhesive", typical=typ, design=dict(tau_avg=design_tau), status="datasheet / team rule",
                      sources=src, note=note, knockdowns=dict(
                          rule="tau_design = lap-shear at the max service temperature x 0.8 (scatter / surface preparation) x 0.5 "
                               "(average-to-peak stress for short, stiff overlaps; peel controlled with tapered ends and fillets); "
                               "the bonded-joint special factor 1.5 is then applied to the ultimate load"))
    adhesive("ea9394", "LOCTITE EA 9394 AERO epoxy paste", dict(lap_shear_25C=28.9e6, lap_shear_82C=20.7e6, lap_shear_m55C=22.7e6,
                                                                 tpeel_N_per_mm=0.88, service_C=177),
             20.7e6 * 0.8 * 0.5, ["ea9394"], "Structural joints: spar-cap to web, rotor-mount inserts, boom sleeves. Abrade + solvent wipe composite; "
             "aluminium phosphoric-acid anodize or sol-gel.")
    adhesive("ma530", "Plexus MA530 methacrylate", dict(lap_shear_cohesive_low=11.7e6, lap_shear_cohesive_high=17.2e6, tensile=17.2e6,
                                                        elongation=0.9, service_C=82),
             11.7e6 * 0.7 * 0.8 * 0.5, ["ma530"], "Secondary bonds and large-gap (to 18 mm) joints: skins to ribs, fairings, cable "
             "trays. Extra 0.7 factor for strength at 60 C (no elevated-temperature data on the TDS).")

    # ---------------------------------------------------------------- printed (non-structural)
    for key, name, E, Fxy in (("pla", "PLA (FDM)", 3.0e9, 50e6), ("petg", "PETG (FDM)", 2.0e9, 45e6), ("asa", "ASA (FDM)", 2.0e9, 40e6),
                              ("pa_cf", "PA6-CF (FDM, dried)", 3.5e9, 70e6)):
        M[key] = dict(name=name, kind="printed", E=E, typical=dict(F_xy=Fxy), design=dict(F=0.3 * Fxy, E=0.8 * E),
                      status="estimate", sources=[], note="NON-STRUCTURAL ONLY (jigs, moulds, fairings, ducts). 0.3 x XY strength "
                      "covers layer adhesion (Z), creep, temperature and moisture.", knockdowns=dict(factor=0.3))
    return M


def load(path=HERE / "materials.json"):
    return json.loads(Path(path).read_text())


def main():
    db = dict(_about="E8-200 structural material properties and design allowables (SI). Generated by fea/materials.py; "
                     "edit the script, not this file.", policy=POLICY, sources=SRC, materials=build())
    (HERE / "materials.json").write_text(json.dumps(db, indent=1))
    for k, v in db["materials"].items():
        d = v["design"]
        print(f"{k:28s} " + ", ".join(f"{kk}={vv / 1e6:.0f}" for kk, vv in d.items() if isinstance(vv, float) and vv > 1e5))


if __name__ == "__main__":
    main()
