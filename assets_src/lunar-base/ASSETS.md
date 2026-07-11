# ASSETS.md — lunar-base asset production (Phase 5)

Loop per asset: **Claude drafts → Kari art pass in Blender → Claude runs
validator + janitor pass (LODs, naming, provenance) → approved here.**
Per CLAUDE.md art-direction boundaries: Claude never re-touches a .blend Kari
has edited without asking — post-art-pass janitor work lands in a new version
file. The validator gate (`pipeline/blender/validate_asset.py`) must pass
before any row reads `approved`.

## Build order & status

| # | Asset | Bible row | Status | Files | Notes |
|---|---|---|---|---|---|
| 001 | GN kit (truss, panel array, MLI wrap, scaffold, regolith berm, disturbance scatter) | §4.2 kit | **APPROVED** (Kari, 2026-07-13; v003) | `assets/gn_kit/gn_kit_v003.blend` | LOD policy N/A (generator library — LODs come per consuming asset). | v001 feedback applied: truss braces on all 4 faces + chord-connected; berm = cosine-bell pile, tapered closed ends (`End Taper`), `Ground` shrinkwrap; scatter = rock-collection instancing (`Rocks`/`Scale Min/Max`/`Yaw`/`Tilt Random`) + `gn_kit_rocks` demo set. v003: End Taper fixed — Blender 5.x Curve-to-Mesh takes an explicit Scale input, radius attribute is ignored. Validator 8/8; turnarounds `D:\renders\lunar-base\assets\gn_kit_v003\` |
| 001b | Landing pad + berm (on real terrain @ approved location) | 11 | **APPROVED** (Kari art pass on v002, 2026-07-13; janitor v003) | `assets/pad/pad_v003.blend` | v003 = copy of Kari's v002 + berm relinked to kit v003 (End Taper fix) + LOD1/LOD2 collections (2.2k/0.5k tris). Validator 8/8 |
| 002 | Blue Moon Mk2 | 3 | **brief — at gate** | `assets/mk2/BRIEF.md` | blueorigin.com re-fetch still blocked (429 + archive unreachable) — NASA-sourced dims stand; browser check optional |
| 003 | Foundation Surface Habitat | 1 | queued | — | inspect-model grade (D9 — Class B centerpiece) |
| 004 | Starship HLS | 2 | queued | — | mid detail (distant per D8) |
| 005 | Lunar Cruiser | 6 | queued | — | |
| 006 | LTV Pegasus | 4 | queued | — | no published dims — model from renders, log [UNCONFIRMED] |
| 007 | LTV CLV-1 | 5 | queued | — | FLEX-derived dims [UNCONFIRMED] |
| 008 | VSAT pair | 7 | queued | — | |
| 009 | FSP reactor | 8 | queued | — | **gated on D5 re-check** (award status) — run the news check when this row reaches the front, not before |
| 010 | ISRU vignette | 9 | queued | — | |
| 011 | Comms set | 10 | queued | — | |
| 012 | Props pass (TRELLIS intake: cargo, tanks, clutter) | §4.3 | queued | — | trellis1 env; mesh+radiance_field ONLY; provenance per prop |

Statuses: `brief` → `draft` (Claude, validator-clean) → `art-pass` (Kari) → `approved` (validator re-run + janitor + this table updated).
D7 (Earth phase/azimuth) is scheduled for **look-dev**, after the structure assets exist.

## ASSET-SPEC (applies to every row)

- **Scale:** 1:1 real meters, dimensions from the bible §3 element table (with
  its [UNCONFIRMED] flags carried into the asset's provenance entry).
- **Files:** one `.blend` per asset at `assets_src/lunar-base/assets/<slug>/<slug>_v###.blend`;
  versions never overwrite (v001 = Claude draft, art pass may save in place or
  bump — Kari's call; Claude's post-art-pass work always bumps).
- **Structure:** one linkable collection `AST_<slug>` holding the deliverable;
  optional `CTX_<slug>` collection for non-linkable context (terrain patches,
  reference scale figures). Objects `<slug>_<part>`, materials `M_<slug>_<part>`,
  GN groups `GN_<name>`.
- **Origin:** asset footprint centered on world origin, grounded at Z=0
  (terrain-integrated assets: the nominal ground plane at the element's site).
- **Transforms:** applied (scale = 1,1,1) on every mesh object at validation.
- **Materials:** Cycles PBR (Principled), no Eevee-only tricks; every mesh has
  ≥1 material slot; UVs required unless the material is fully procedural
  (flag `procedural_ok` custom prop on the object).
- **LOD policy:** `hero` (full detail, splat-scene near-field), `mid`
  (silhouette + large forms, ≥200 m), `far` (proxy-grade, ≥1 km). Delivered as
  suffixed collections `AST_<slug>_LOD{0,1,2}` when the asset graduates to
  approved; drafts may ship LOD0 only.
- **Provenance:** one JSON per asset in `pipeline/provenance/lunar-base/assets/`
  (schema per provenance README; script-generated assets log tool + script +
  repo commit; AI-assisted assets log the full generation chain).
- **Review renders:** neutral turnarounds only (fixed default cameras/lighting,
  documented in `render_asset_turnaround.py`) — composition-free by design.
