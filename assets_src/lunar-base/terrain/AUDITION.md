# D2 Terrain Audition — three candidate sites, identical methodology

> **OUTCOME (checkpoint 2, Kari 2026-07-11): D2 = site11 — de Gerlache Rim 2.**
> site01/site04 assets stay on disk as comparison record; production continues
> on Site11 only. This document is the audition record.

Purpose: Kari rules on **D2 (base site)** at **checkpoint 2** by comparing three
contact sheets and flying three .blends. Everything except the terrain data and
the vantage is identical by construction (same scripts, same parameters).
SCENE-BIBLE.md §4 holds the site facts; §8 logs the decision.

## Methodology (identical across sites)

- **Data:** PGDA 5 m/px LOLA site DEMs (Barker et al. 2021), 3200² px = 16×16 km
  tiles, converted 1:1 via `pipeline/terrain/dem_to_displacement.py` (32-bit EXR,
  meters). Provenance: `pipeline/provenance/lunar-base/terrain-dems.json`.
- **Mesh:** 16 km plane, simple subdivision 2048² at render (≈7.8 m/vertex vs
  5 m/px data — slight undersampling, fine for v001), 512² in viewport, smooth
  shaded, Displace strength 1.0.
- **Material:** placeholder regolith — Principled, albedo 0.13, roughness 1.0.
  (No back-scatter/opposition tweak yet; up-sun frames read darker than reality.)
- **Lighting (bible §5):** Sun 1361 W/m², angular size 0.53°, elevation **+1.5°**
  fixed; world pure black; no earthshine fill — shadow = terrain bounce only.
- **Exposure:** AgX @ **−4.5 EV** — a legibility choice, not physics: flat ground
  under a 1.5° sun sits dark-but-readable, sun-facing slopes roll off in AgX's
  shoulder. Sun strength itself is physical.
- **Render:** Cycles/OptiX, 64 samples + denoise, 1280×720, ~7 s/frame.
- **Sun study:** 24 azimuths × 15° at fixed elevation. **Azimuths are tile-frame**
  (0° = projected north of the polar-stereographic tile), not true lunar solar
  azimuth — for comparing terrain response, choose the hero azimuth later (D7).
- **Camera:** 24 mm full-frame, 10 m above local terrain, one vantage per site
  (below), clip 100 km.

## Vantages (one per site — position from published data where it exists)

| | site01 — Connecting Ridge (Site 001) | site04 — Shackleton rim | site11 — de Gerlache rim (Rim 2 region) |
|---|---|---|---|
| Camera | **89.45°S 222.69°E** — Mazarico Point 001, highest documented illumination on the Moon (89.0% surface avg); crest slopes <10° | **89.6866°S 197.19°E** — Gläser 2018 best 2 m-mast spot (85.5% avg, longest darkness 66 h) | **auto: tile's highest crest point** (row 1615, col 1466) — [UNCONFIRMED] no published Rim 2 station coords; elevation used as illumination proxy |
| Aimed at | deepest depression within 6 km (PSR-candidate void, 1,237 m below camera) — strongest local relief; Shackleton itself lies ~20 km away, outside the tile | into the crater void toward Shackleton's center — 21 km wide, 4.2 km deep PSR, the most iconic single feature of the three | into the de Gerlache void (32.4 km crater, PSR floor) — the site's defining negative space |
| Local relief in tile | 2,483 m | **4,653 m** | 2,621 m |
| Camera local (x, y, z m) | −308, −259, 2488 | −1809, −2079, 4588 | −668, −78, 2631 |

## Files

- Blends (fly these): `terrain_site{01,04,11}_v001.blend` (this directory).
  Viewport is 512² for navigation; render subdiv is 2048².
- Frames: `D:\renders\lunar-base\audition\site{01,04,11}\az_###.png`
- Contact sheets: `D:\renders\lunar-base\audition\site{01,04,11}_contact.png`
- EXR + meta + vantage JSONs alongside the blends.

## Review checklist for D2

1. **Buildable flat ground** — is there believable acreage for the base cluster
   (habitat + pad ≥1 km apart) near the vantage?
2. **Illumination behavior** — across the 24 azimuths, how much of the year does
   the near-field stay lit? (Contact-sheet frames where the foreground goes dark
   ≈ sun azimuths where the real site is in terrain shadow.)
3. **Feature drama** — does the signature feature (PSR void / crater wall / ridge
   fall-off) carry a hero splat's camera envelope?
4. **Envelope potential** — can a 200–400 m playable envelope hug interesting
   terrain without falling off the good ground?

## Known limitations (v001, deliberate)

- 7.8 m mesh under 5 m data; no meter-scale detail (rocks/micro-relief are a
  later procedural pass — bible §6.3).
- Placeholder Lambert regolith; no opposition surge, so up-sun frames underlight.
- No earthshine fill (bible says ~10⁻⁴ of sun — negligible at this exposure).
- Terrain ends at the 16 km tile edge; horizon beyond is black (production adds
  the 10 m/px context skirt, bible §6.2).
- Tile-frame azimuth ≠ true solar azimuth; elevation +1.5° is the summer-max
  case only. Site-accurate sun geometry comes with the Mazarico illumination
  rasters at look-dev (bible §5/§6.4).
