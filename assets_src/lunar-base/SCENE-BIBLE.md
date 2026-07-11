# SCENE BIBLE — Artemis Lunar Base

Concept: `lunar-base` · Era: **post-Artemis-IV buildout — scene pinned to 2032 (D4)** · Site: **de Gerlache Rim 2 (D2)** · Status: **all gate decisions in except D5/D7 — pre-production**
Research compiled 2026-07-10 from current NASA / ESA / JAXA / contractor sources (per-fact URLs below; full list in `pipeline/provenance/lunar-base/references.json`). Facts marked **[UNCONFIRMED]** are concept-level, render-derived, or analyst figures — never treat them as specs.

---

## 1. Premise & era statement

An early **Artemis Base Camp** at the lunar South Pole in the first half of the 2030s: not a colony, a construction site becoming an outpost. The scene sits a few years after Artemis IV (first crewed landing, early 2028 per the Feb 2026 replan) in the buildout window defined by current policy — EO 14369 and NASA's 2026 replan target "initial elements of a permanent lunar outpost by 2030."

Era anchors (all current, mid-2026):

| Anchor | Date | Source |
|---|---|---|
| Artemis II crewed flyby — FLOWN | Apr 1–10, 2026 | https://www.nasa.gov/blogs/missions/2026/04/01/live-artemis-ii-launch-day-updates/ |
| Artemis III = crewed LEO demo w/ both landers (no landing) | late 2027 | https://www.nasa.gov/missions/artemis/artemis-3/nasa-outlines-preliminary-artemis-iii-mission-plans/ |
| Artemis IV = first crewed landing, south pole | early 2028 | https://spacenews.com/revised-artemis-lunar-lander-plans-take-shape/ |
| LTVs delivered to surface | 2028 | https://www.nasa.gov/news-release/nasa-provides-update-on-moon-base-rovers-landers-missions/ |
| JAXA/Toyota Lunar Cruiser launch | ~2029 | https://global.toyota/en/mobility/technology/lunarcruiser/index.html |
| Fission Surface Power launch-ready | end 2029 | https://www.nasa.gov/wp-content/uploads/2025/08/nasa-fsp-directive-aug42.pdf |
| Blue Moon Mk2 crewed (Artemis V) | NET ~Mar 2030 [fluid] | https://spaceflightnow.com/2025/10/28/blue-origin-details-lunar-exploration-progress-amid-artemis-3-contract-shakeup/ |
| SpaceX cargo Starship delivers JAXA pressurized rover | NET 2032 | https://ntrs.nasa.gov/api/citations/20250008728/downloads/25%2008%2026%20IAC_Creech%20BP-1.pdf |
| Blue Origin cargo Mk2 delivers surface habitat | NET 2033 | same NTRS PDF |
| Foundation Surface Habitat | early 2030s | https://ntrs.nasa.gov/citations/20220013669 |
| ESA Moonlight relay constellation full ops | ~2030 | https://www.esa.int/Applications/Connectivity_and_Secure_Communications/ESA_s_Moonlight_programme_Pioneering_the_path_for_lunar_exploration |

**Implication for set dressing (at the 2032 pin, D4):** LTVs are ~4 years old (dusty, patched, most-weathered items on site); Lunar Cruiser is freshly delivered (clean, NET-2032 anchor); the reactor is in commissioning ~1 km out; **FSH is mid-commissioning — cables still being routed, some MLI covers on** (its NET-2033 delivery anchor is stretched ~1 yr by the pin; logged under the fiction contract's "invent" column and reinforces the construction-site premise); the landing pad is semi-improved (sintered center, built berm) rather than pristine; Moonlight satellites are overhead (comms dishes track slowly).

## 2. Fiction contract

What the scene **holds real** (breaks here = bugs):
- Every element's dimensions come from the table in §3; where only [UNCONFIRMED] figures exist, we model to them but log the uncertainty in provenance.
- Lighting physics: sun ≤ ~1.5° elevation, 1361 W/m², vacuum (no atmospheric scattering, pitch-black shadows lifted only by regolith bounce and earthshine), Earth fixed in azimuth near the horizon.
- Terrain from real LOLA DEM of the chosen site at 1:1 scale (§6).
- Hardware set is era-consistent per §1 — nothing that couldn't plausibly be there by ~2032–2035.

What we **invent** (and say so on the site's "sources & methods" page):
- The exact base layout — no official site plan exists; ours is a plausible composite following published siting logic (pad ≥1 km from habitat, reactor ~1 km with shadow shield toward base, VSAT on the illumination high point).
- **Both landers present simultaneously** (DECIDED — Kari, 2026-07-10): defensible (NASA plans cargo variants of both delivering base elements NET 2032/2033) but no mission puts them side-by-side on a schedule.
- Combining elements from programs that may not all survive to 2035 in this form (FSH design pre-decisional; FSP provider TBD).
- Weathering, cable routing, regolith disturbance patterns, interior lights in windows.

Public status label (PLAN.md §7): `in-development` with "artist's impression based on published NASA/ESA/JAXA sources" phrasing in the summary.

## 3. Element table

Dimensions in meters. **Bold** = official/published; [UNCONFIRMED] = concept/render/analyst-derived. One primary source per row here; secondary URLs in §10.

| # | Element | Key dimensions | Status (mid-2026) | Primary source |
|---|---|---|---|---|
| 1 | **Foundation Surface Habitat** (FSH) | Vertical 3-level stack; metallic base ~4 dia + inflatable upper ~6.5 dia, ~127 m³, <12 t — all [UNCONFIRMED, NASA concept] ; crew 2→4, **8.2 psi / 34% O₂** | Pre-formulation, no prime; early-2030s target | https://ntrs.nasa.gov/citations/20220013669 |
| 2 | **Starship HLS** (SpaceX) | **H 52** (NASA), **dia 9**, ~614 m³ (NASA est.), 4 legs [UNCONFIRMED], crew cabin/elevator ~30 m up [UNCONFIRMED]; 6 Raptor + mid-body GOX/GCH₄ landing thrusters | Uncrewed demo expected 2027; Artemis IV competitor | https://ntrs.nasa.gov/api/citations/20250008728/downloads/25%2008%2026%20IAC_Creech%20BP-1.pdf |
| 3 | **Blue Moon Mk2** (Blue Origin) | **H ~16** (NASA slide; 15.3 per BO exec), dia <7 [derived from New Glenn fairing, UNCONFIRMED], dry ~16 t, crew cabin ~5 at base, ladder (not elevator), 3× BE-7 LH₂/LOX | Mk2 uncrewed demo ~2027, crewed Artemis V NET ~2030; Mk1 not yet flown (New Glenn delays) | https://www.nasa.gov/directorates/esdmd/artemis-campaign-development-division/human-landing-system-program/industry-moon-lander-training-cabin-lands-at-nasa-for-artemis/ |
| 4 | **LTV "Pegasus"** (Lunar Outpost) | No published L/W/H [UNCONFIRMED — model from renders]; 2 crew side-by-side, >14.5 km/h, ~900 km range [UNCONFIRMED], survives lunar night | **Awarded May 26, 2026** ($220M), surface by 2028 | https://www.nasa.gov/news-release/nasa-provides-update-on-moon-base-rovers-landers-missions/ |
| 5 | **LTV "CLV-1"** (Astrolab) | ~907 kg (NASA); FLEX heritage: ~4.0 × 2.3 × 2.6 [UNCONFIRMED for CLV-1 — FLEX figures]; arm 25 kg @ 2 m | **Awarded May 26, 2026** ($219M), surface by 2028 | https://www.astrolab.space/flex-rover/ |
| 6 | **Pressurized rover "Lunar Cruiser"** (JAXA/Toyota) | **6.0 × 5.2 × 3.8**, cabin 13 m³, crew 2 (4 emergency), ~10 t [UNCONFIRMED], 6 wheels, H₂ fuel cell, aft suitports | In development; launch ~2029 (NASA launches, likely cargo Starship NET 2032) | https://global.toyota/en/mobility/technology/lunarcruiser/index.html |
| 7 | **VSAT solar arrays** | Baseline: mast ~**10** (32 ft req.), ~10 kW, relocatable. VSAT-XL: **~30 tall, 2× 20 m wings, 50 kW**, blankets start >10 m up; rotates ~360°/lunar day tracking the horizon-circling sun | Prototypes (Astrobotic/Honeybee/Lockheed); LunaGrid service "end of decade" | https://www.nasa.gov/news-release/three-companies-to-help-nasa-advance-solar-array-technology-for-moon/ |
| 8 | **Fission Surface Power** | **≥100 kWe**, total ≤**15 t**, closed Brayton, ≥10 yr; old 40 kW packaging (4 dia × 6 cylinder) [UNCONFIRMED for 100 kW — do not scale blindly]; dominant visual = tens-of-meters radiator wings; sited ~1 km out | Aug 2025 directive; RFP early 2026, **provider award unannounced as of 2026-07 — re-verify before art lock** | https://www.nasa.gov/wp-content/uploads/2025/08/nasa-fsp-directive-aug42.pdf |
| 9 | **ISRU demo** | TRIDENT drill: 1 m class, ~20 kg + 5.4 kg avionics, 200 N WOB, cuttings pile. O₂ pilot (Sierra COPR / NASA CaRD): no flight dims [UNCONFIRMED — depict reactor drum + gas manifold + small O₂ tanks + concentrator mirror] | TRIDENT flew IM-2 (Mar 2025) but lander tipped — drilling undemonstrated; COPR passed dirty-TVAC 2024 | https://www.nasa.gov/missions/artemis/nasas-lunar-drill-technology-passes-tests-on-the-moon/ |
| 10 | **Comms** | Nokia LTE "network in a box": shoebox-scale [UNCONFIRMED], lander-mounted; per-element steerable Ka dish 0.5–1 [UNCONFIRMED, concept]; LunaNet-conformant terminals; Moonlight = 4 relay sats (Thales Alenia), south-pole priority | LTE flew IM-2 (25 min, no surface call); Lunar Pathfinder NET Nov 2026; Moonlight full ops ~2030 | https://www.nokia.com/about-us/newsroom/articles/inside-look-at-nokia-moon-mission/ |
| 11 | **Landing pad + berm** | Pad **25–100** dia (accuracy-dependent; use ~40): sintered glassy center + compacted apron; berm ~2–3 high at ≥30 radius [study figures, not specs] with corridor gap; ejecta streaks radiate outside | Research only (NTRS 2025, FAST/NIAC, PISCES demo) — "semi-improved" fits the era | https://www.sciencedirect.com/science/article/abs/pii/S0094576525008434 |

**Scale ladder for composition:** astronaut 1.8 → FSH ~10 [UNCONFIRMED] → Blue Moon Mk2 16 → Starship HLS **52** (13× the habitat; a 15-story tower). Apollo LM was 7 m — even Mk2 doubles it. HLS is the vertical exclamation mark of every wide shot; Mk2's crew cabin sits at habitat eye-line. Official comparison graphic: NTRS IAC PDF above (local copy: `ref/nasa-hls-iac-2025-creech.pdf`; official renders of both landers: `ref/nasa-hls-one-pager-2025.pdf`).

### Per-element visual notes (modeling cues)

1. **FSH** — hard metallic Level-1 (airlock + dust porch) under a wider soft-goods inflatable barrel: visible gore seams/straps, off-white MMOD blanket, small L2 window, external radiators + ECLSS plumbing, on legs or offloaded.
2. **HLS** — white hull, **black engine skirt and legs**, red NASA worm mid-body, ring of small dark windows at the nose, elevator rail track down one flank where a solar-panel slot is omitted [UNCONFIRMED]; on the surface the ~18 m solar panels rest vertically against the hull [UNCONFIRMED]; no flaps/tiles.
3. **Mk2** — metallic silver stepped cylinder: domed LH₂ tank crown with 4 large radiator panels around it, LOX tanks mid, boxy windowed crew cabin at the base, 4 splayed legs with round pads, exterior ladder.
4. **Pegasus** — low open cockpit, 2 crew side-by-side, rear cargo bed, robotic arm, Goodyear airless mesh wheels, gold MLI boxes, mast antenna.
5. **CLV-1/FLEX** — flat modular pallet chassis on 4 wheel arms, payload slung under deck, two rear standing crew stations (T-handles), deployable solar panel.
6. **Lunar Cruiser** — boxy white cab, huge wraparound front glazing, 6 wheels on outrigger arms (5.2 width is mostly track), aft suitports, roof radiators + fold-out solar, JAXA/Toyota livery; 2025 restyle is rounded.
7. **VSAT** — squat self-leveling base w/ outriggers, slender coilable mast, vertical banner-like blanket; slow yaw is the only motion in the scene (splats are frozen — pose matters).
8. **FSP** — core at grade or bermed-in, shadow-shield cone **toward** the base, Brayton block, big vertical radiator fin field; keep-out markers, long cable run snaking to base.
9. **ISRU vignette** — TRIDENT-style mast drill (~1.5–2 deployed) with bright auger + cuttings cone; O₂ plant: reactor drum, manifold, small spherical tanks, heliostat mirror [UNCONFIRMED].
10. **Comms** — gold-MLI boxes, patch/whip antennas, one slowly-tracking Ka dish per major element; **no blinking LEDs** (not a thing on vacuum hardware) — detail via radiator paint and connector panels.
11. **Pad** — dark vitrified bluish center ring → lighter compacted apron → berm with corridor gap; scorch fan + radial ejecta streaks; nav reflector posts.

## 4. Site comparison — **D2 DECIDED (Kari, 2026-07-11): de Gerlache Rim 2 (site11)**

Chosen after the three-site terrain audition (`terrain/AUDITION.md`, checkpoint 2): broadest buildable ground of the three, lit through most of the azimuth circle, and the only candidate inside a current official Artemis III landing region. Production terrain = PGDA Site11 5 m/px tile + 10 m/px context skirt (§6). The audition vantage was an illumination proxy — the actual base position within the tile is chosen at layout blockout. Comparison table kept below for the fact layer / sources page.

Artemis III context first: of the original 13 candidate regions (Aug 2022), NASA's Oct 2024 down-select to nine **dropped all Shackleton-adjacent regions** (Peak Near Shackleton, Connecting Ridge, Connecting Ridge Extension, de Gerlache Rim 1) but **kept de Gerlache Rim 2**. NASA's LPSC 2026 abstract stresses the drop reflects Artemis-III-specific constraints (slope variability in the ellipse, DTE comms, illumination robustness) and "does not imply that removed regions are unsuitable for future exploration" — and JSC scientists have separately called the Shackleton–de Gerlache ridge "a strong candidate for the location of a lunar field station." A *base* on Connecting Ridge is therefore fully defensible; de Gerlache Rim 2 is the strict-Artemis-III-fidelity pick.
(Sources: https://www.nasa.gov/news-release/nasa-provides-update-on-artemis-iii-moon-landing-regions/ · https://www.hou.usra.edu/meetings/lpsc2026/pdf/1901.pdf · https://www.hou.usra.edu/meetings/lunarsurface2020/pdf/5082.pdf)

| | **Shackleton rim** | **Connecting Ridge ("Site 001")** | **de Gerlache rim (Rim 2 region)** |
|---|---|---|---|
| Location | crater 89.66°S 129.78°E; 21 km dia, 4.2 km deep PSR interior | ridge Shackleton→de Gerlache, ~15 km crest; Site 001 at **89.45°S 222.69°E** | crater 88.5°S 87.1°W; 32.4 km dia, PSR floor |
| Illumination (surface) | best spots **81.0–86.7%** avg | **89.0%** avg — highest known on the Moon | high patches; per-point table not published [UNCONFIRMED] |
| At 2 m mast | **85.5%**, longest darkness **66 h** | **~88%, 92% sunlit**, longest darkness **~4.6 d**, longest continuous light **234 d** | — [UNCONFIRMED] |
| At 10 m mast | — | up to **95.7%** sunlit, darkness **3.1 d**, light **262 d** | — |
| Longest shadow (surface) | **221 h** (~9.2 d) at best spot | **141 h** (~5.9 d) | — |
| Earth visibility | ~half-disk on horizon, ~50% | **~60%**, half-disk regime (mean Earth-center elev ≈ −0.4° [derived]) | worst of the three — Earth rides lower at 87°W [inference, UNCONFIRMED] |
| Terrain | narrow rugged crest, rim plane tilted ~1.5°, flat area scarce (why it fell out of Artemis III) | crest slopes mostly **<10°** (flanks <20°); small PSRs within 10 km — ISRU story adjacency; boulder fields ~2 km from 001 | broader, gentler terrain (why Rim 2 survived the down-select) |
| Artemis III status | dropped Oct 2024 | dropped Oct 2024 (as landing region) | **retained (Rim 2)** |
| DEM available | PGDA Site04, 5 m/px | PGDA Site01, 5 m/px | PGDA Site11, 5 m/px |

(Key sources: Gläser et al. 2018 via https://ntrs.nasa.gov/api/citations/20170007365/downloads/20170007365.pdf · Gläser et al. 2014 https://elib.dlr.de/94242/1/EPSC2014-136-1.pdf · Mazarico et al. 2011 https://ntrs.nasa.gov/citations/20120010094 · https://en.wikipedia.org/wiki/Shackleton_(crater) · https://www.sciencedirect.com/science/article/pii/S2589004223019302 · https://www.sciencedirect.com/science/article/abs/pii/S0019103524000460 · https://ntrs.nasa.gov/api/citations/20210026537/downloads/Umansky_dGC-LPSC2022-Abstract_V5.pdf)

**Recommendation: Connecting Ridge / Site 001.** It is the best-documented base site in the literature (highest illumination on the Moon, published slope and PSR-distance numbers, named NASA field-station advocacy), its 2 m/10 m illumination numbers directly justify the VSAT masts in-scene, nearby small PSRs justify the ISRU vignette, and the ridge gives natural elevated camera positions with both crater voids as negative space. Runner-up: de Gerlache Rim 2 if you want the scene to sit inside a current official Artemis III region.

## 5. Lighting spec

- **Sun:** lunar axial tilt to the ecliptic is **1.5424°**, so at ~89.5°S the sun's elevation stays within roughly **−2°…+2°** (tilt + co-latitude) — permanent grazing light, km-long shadows that sweep like clock hands. Angular diameter **0.53°** (Cycles sun `angle`). Irradiance **1361 W/m²** (IAU nominal TSI). The sun circles the full 360° of azimuth once per **29.53-day** synodic day; at the best sites this produces ~230–260 days of continuous summer light and winter nights of only ~3–5 days. Azimuth = art direction; elevation = physics. Darkness often means sun *behind terrain*, not below horizon.
  (https://en.wikipedia.org/wiki/Moon · https://elib.dlr.de/94242/1/EPSC2014-136-1.pdf · https://svs.gsfc.nasa.gov/5228/ · https://en.wikipedia.org/wiki/Solar_constant)
- **Sky:** black, zero scattering. Shadow fill = regolith bounce + earthshine only.
- **Regolith:** albedo **0.11–0.14** (Moon geometric 0.136, "comparable to asphalt"; polar highlands brighter than maria; NSSDC canonical 0.12 [UNCONFIRMED today — site unreachable]). Regolith is strongly **back-scattering** (opposition surge) — a pure Lambert BRDF will underlight up-sun views; consider a retro-reflective tweak for hero shots.
- **Earth:** fixed in azimuth (toward ~0° lunar longitude), "bobbing" with libration **±7.9° lon / ±6.68° lat** (~27-day periods). From Connecting Ridge the mean Earth-center elevation ≈ **−0.4°** — Earth sits *half-set on the horizon* (that's the money composition, and it's physically true). Angular size **1.8–2.0°** (~3.7× the sun). Phase is art direction (D7).
  (https://amt.copernicus.org/articles/16/1527/2023/ · https://www.sciencedirect.com/science/article/pii/S2589004223019302)
- **Earthshine:** near-full-Earth irradiance at the surface ≈ **0.15 W/m² ≈ 10⁻⁴ of sunlight** (~13 lux vs ~130 klux [derived]) — cool blue-white fill; the reason polar shadows are *not* pitch black. (https://arxiv.org/pdf/1904.00236)
- **Star policy — DECIDED (D3, Kari 2026-07-11): stars OFF everywhere** — physically correct at daylight exposure; the fact layer explains why the sky is black. Applies to hero splat, all posters including P7.
- **Cycles rig:** single Sun light, `angle 0.53°`, energy per irradiance above; world = pure black; no atmosphere/volumetrics; validation: the Mazarico LOLA illumination rasters (§6) give per-pixel ground truth to sanity-check sun azimuth/elevation choices against the real terrain self-shadowing.

## 6. Terrain & DEM plan

Pipeline built and tested: `pipeline/terrain/dem_to_displacement.py` (GeoTIFF → 32-bit EXR + meta.json, 1:1 meters). **Production data comes straight from NASA GSFC PGDA** — cloud-optimized GeoTIFFs, south polar stereographic, meters XY, no reprojection needed. Moon Trek's polar DEM basis turns out to be only 100 m/px — use Trek for scouting, PGDA for production.

**Two-LOD displacement setup (maps directly onto the data):**
1. **Site tile** — 5 m/px landing-site DEM, one ~41 MB GeoTIFF per candidate (RMS height error 0.30–0.50 m):
   - Connecting Ridge: https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/Site01/Site01_final_adj_5mpp_surf.tif
   - Shackleton rim: https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/Site04/Site04_final_adj_5mpp_surf.tif
   - de Gerlache rim: https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/Site11/Site11_final_adj_5mpp_surf.tif
   - (companion `*_slp.tif` slope maps for validating base placement; product page https://pgda.gsfc.nasa.gov/products/78)
2. **Context skirt** — windowed crop from `LDEM_83S_10MPP_ADJ.TIF` (10 m/px, 83°S–90°S, 5.1 GB COG — crop via `gdal_translate -projwin … /vsicurl/https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LDEM_83S_10MPP_ADJ.TIF` without downloading it; product page https://pgda.gsfc.nasa.gov/products/90) for the horizon out to ~tens of km.
3. Meter-scale detail (rocks, micro-relief) is procedural on top — no 1 m LOLA DEMs exist; 1 m SfS products for these exact sites are [UNCONFIRMED].
4. **Lighting validation:** Mazarico et al. 2011 illumination + Earth-visibility rasters (same frame): https://pgda.gsfc.nasa.gov/products/69

**License:** NASA PDS/PGDA data are US-Government works — public domain, free/unrestricted use, attribution requested; cite Barker et al. 2021/2023 (DEMs) and Mazarico et al. 2011 (illumination). Fully compatible with this project's commercial EU use. (https://pds.nasa.gov/policy/index.shtml)

Terrain outputs land in `assets_src/lunar-base/terrain/`; every DEM download gets a provenance entry (product URL + citation + license line).

## 7. Shot list — DRAFT (both landers per Kari's decision)

**Class A hero splat (one bounded vista, ~200–400 m playable envelope):**
The central cluster from a shallow arc: FSH + Lunar Cruiser docked at suitport + one LTV in foreground; VSAT masts catching sun mid-ground; **Blue Moon Mk2 on the pad ~400 m out; Starship HLS further out (~800 m+), off-pad on compacted regolith** — both landers always in frame as the scale backdrop. Camera envelope hugs the cluster (splat quality lives here); landers are set dressing at distance, never approached. Sun azimuth chosen so HLS backlights with a km-long shadow crossing the scene. Envelope authored per ADDON.md §3 once terrain is in.

**Class C posters/stills (Cycles, same set):**
- P1 — Wide establishing from a rise: full base, Earth low on horizon, HLS + Mk2 silhouettes.
- P2 — FSH + Lunar Cruiser at suitport, astronaut for scale, LTV passing.
- P3 — Pad ops: Mk2 on the sintered pad inside the berm, ejecta streaks, corridor gap toward camera.
- P4 — HLS vertical: from near a leg, up the 52 m hull, elevator platform mid-descent; astronaut + Pegasus at the base for the scale punch.
- P5 — FSP at ~1 km: radiator fins backlit, cable run leading the eye back to base.
- P6 — ISRU vignette: drill + O₂ plant + excavator, close quarters, grazing light.
- P7 — [optional] Earthrise-style: Earth + comms dish, base bokeh'd behind.

**Class B inspect model:** FSH as the hotspot-annotated centerpiece [proposal — confirm at gate], with LTV/Lunar Cruiser as candidates for a second model later.

## 8. Decisions log

| ID | Decision | Status |
|---|---|---|
| D1 | Both landers (HLS + Mk2) appear in the scene | **DECIDED** (Kari, 2026-07-10) |
| D2 | Site | **DECIDED** (Kari, 2026-07-11, after 3-site terrain audition — checkpoint 2): **de Gerlache Rim 2 (site11)**. Base position within the tile chosen at layout blockout; audition vantage was an illumination proxy |
| D3 | Star policy | **DECIDED** (Kari, 2026-07-11): **stars OFF everywhere** (physically correct) |
| D4 | Era pin | **DECIDED** (Kari, 2026-07-11): **2032** — note FSH's NET-2033 anchor stretches ~1 yr; depicted mid-commissioning (fiction contract "invent" column) |
| D5 | FSP design basis (Lockheed concept vs generic 100 kW) — award unannounced | **OPEN** — re-verify news before FSP modeling |
| D6 | Foreground LTV | **DECIDED** (Claude, per Kari's delegation, 2026-07-11): **both** — both under contract for 2028 delivery so both era-consistent by 2032; Pegasus = crewed hero foreground (open cockpit, Apollo cues), CLV-1 = robotic workhorse parked at the ISRU vignette (arm + pallet) |
| D7 | Earth phase + azimuth composition | **OPEN** — art direction during look-dev |
| D8 | Lander placement | **DECIDED** (Kari, 2026-07-11): **Mk2 on the improved pad; Starship HLS distant, off-pad** (HLS predates the pad — explains the ejecta streaks) |
| D9 | Class B inspect model | **DECIDED** (Kari, 2026-07-11): **FSH** |

## 9. Production notes

- Scale honesty per PLAN.md §7: bounded vista only; true megastructure scale conveyed by the fact layer and scale-comparison widget, not one continuous scene.
- HLS/Mk2 modeling from official renders (`ref/*.pdf`) — log every [UNCONFIRMED]-derived dimension in the provenance JSON of the resulting .blend.
- blueorigin.com was rate-limiting during research (429) — re-fetch official Mk2 numbers before final Mk2 modeling pass.
- Everything here feeds `content/concepts/lunar-base.json` (stats, sources, summary) at pack time.

## 10. Source list

See `pipeline/provenance/lunar-base/references.json` (machine-readable, with access dates and usage terms). Headline primary sources: NTRS 20220013669 (FSH), NTRS 20250008728 (HLS program, official lander dimensions), nasa.gov HLS reference + one-pager, NASA FSP directive PDF, NASA LTV award release, Toyota Lunar Cruiser pages, Astrolab FLEX, NASA/Nokia IM-2 coverage, ESA Moonlight, NTRS/ScienceDirect landing-pad studies.
