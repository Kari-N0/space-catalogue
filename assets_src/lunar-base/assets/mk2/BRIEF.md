# BRIEF — Asset 002: Blue Moon Mk2 (crewed HLS, Artemis V) — GATE

Status: **brief for Kari's approval before drafting** (ASSETS.md row 002).
Sources: SCENE-BIBLE.md §3 row 3 + `ref/` NASA PDFs. blueorigin.com re-fetch
**still blocked** (429 direct, archive unreachable from this environment) — the
load-bearing numbers below are NASA-sourced; if you want Blue Origin's own
marketing specs cross-checked, a browser visit is the remaining option.

## Role in scene

- **On the landing pad** (D8), 1.5 km from the habitat cluster, inside the berm.
- Era 2032: Artemis V (NET ~2030) has flown; this airframe is a recent arrival —
  clean hull, light dust on legs/skirt only.
- **Grade: hero-capable exterior.** It's mid-distance in the hero splat, but
  poster P3 is a pad-ops close-up of this exact vehicle. No interior; windows
  read as lit via emissive glass (bible's "interior lights in windows" set
  dressing) — confirm below.

## Dimensions (model targets)

| Parameter | Value | Confidence / source |
|---|---|---|
| Overall height | **16.0 m** | NASA IAC comparison slide (`ref/nasa-hls-iac-2025-creech.pdf`); BO exec said 15.3 m — see Q1 |
| Body diameter | **≤7 m** (propose 6.4) | [UNCONFIRMED — derived] New Glenn 7 m fairing constraint |
| Crew cabin | lower ~third; mockup "over 15 ft (5 m) tall" | NASA JSC mockup article (May 2026) |
| Dry / launch mass | 16 t / >45 t | Wikipedia citing BO — context only, doesn't drive geometry |
| Engines | **3× BE-7**, ~10,000 lbf each, LH₂/LOX, deep-throttling | NASA NTRS + press |
| Legs | 4, splayed, round pads | official render (`ref/nasa-hls-one-pager-2025.pdf` p.1) |
| Surface access | **exterior ladder** (not elevator) | NASA JSC mockup article |
| Cargo variant context | same bus delivers a surface habitat NET 2033 | NTRS IAC PDF; one-pager p.2 has the cargo render |

## Geometry breakdown (draft build order)

1. **Legs ×4** — splayed struts, round pads, dust shields.
2. **Base crew cabin** (~5 m tall) — boxy equipment modules ringing a cylinder,
   windows on two faces, EVA hatch + ladder run, handrails.
3. **Mid section** — LOX tanks, corrugated/panelled skin (kit `GN_panel_array`).
4. **Upper LH₂ tank** — big dome crown with NASA meatball, **4 large radiator
   panels** around it (solar-powered 20 K boiloff control justifies them).
5. **Engine skirt** — 3 BE-7 bells, heat-shielded recess.
6. **Top hatch/docking** ring, antennas, small steerable dish.
7. Surface finish: metallic silver-grey overall (official render), MLI foil in
   recesses (kit `GN_mli_wrap`), decals (NASA meatball, Blue Origin feather).

Asset frame: pad-contact plane = Z0, origin at footprint center; +Y = ladder/
EVA face (will face the berm corridor when placed). `AST_mk2` collection,
`mk2_*` objects, `M_mk2_*` materials; validator spec `[7, 7, 16]` tol 15%.

## Known unknowns (modeled from renders, logged [UNCONFIRMED] in provenance)

Exact body diameter, leg span, engine bell diameter, window count/layout,
radiator panel dimensions, ladder detail. Primary visual references: the two
`ref/` PDFs (crew render p.1, cargo render p.2, IAC comparison slide).

## LOD plan (delivered at approval per ASSET-SPEC)

- LOD0 hero — P3 poster distance (~10–50 m).
- LOD1 mid — hero-splat distance (1.5 km): silhouette + large forms.
- LOD2 far — proxy-grade.

## Questions for Kari (gate)

1. **Height datum:** model to NASA's 16.0 m or BO's 15.3 m? Propose **16.0**
   (matches the official comparison graphic the fact layer will cite).
2. **Windows:** emissive lit glass, no interior — OK?
3. Any part you want left deliberately rough for your art pass rather than
   scripted (e.g., ladder/handrail detailing, decal placement)?
