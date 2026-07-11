# Base layout blockout — de Gerlache Rim 2 (D2) — GATE: checkpoint 3

Deliverable 2 after D2: the actual base position inside the Site11 tile plus a
true-dimension proxy blockout. **Status: awaiting Kari's layout review.**
Method + parameters: `pipeline/terrain/select_base_site.py` (all criteria and
weights documented in-file); proxies: `pipeline/blender/blockout_lunar_base.py`.

## Habitat anchor — 88.9197°S, 72.0103°W

| Criterion | Value | Meaning |
|---|---|---|
| Mean slope (250 m window) | **2.88°** | cluster ground |
| Buildable fraction (500 m window, <5° px) | **0.741** | acreage for cluster + margins |
| Horizon-based illumination proxy (2 m, <1° horizon) | **0.562** | fraction of azimuth circle open to a grazing sun — the polar siting driver |
| Void (de Gerlache interior) distance | **3.5 km** at bearing 221° | backdrop in the 1.5–4 km band |

Chosen from a 400-candidate trade-space (printed by the script). The two
instructive rejects: the flattest candidate (build 0.87) sat in a basin that a
**render sweep proved black at every sun azimuth** — which is why the horizon
criterion exists; the highest-illumination candidate (0.58) had only 0.54
buildable. The pick trades 0.02 illumination for +0.20 buildable ground.
Illumination proxy is horizon geometry at one height — the Mazarico rasters
(bible §6.4) refine this at look-dev.

## Element positions (bearings/distances from habitat; local Z = m above tile min)

| Element | Bearing | Distance | Ground slope | Note |
|---|---|---|---|---|
| FSH habitat (anchor) | — | 0 | 2.88° (250 m mean) | Cruiser 25 m, Pegasus 40 m, comms 35 m, VSAT-B 60 m around it |
| ISRU vignette + CLV-1 | 315° | 150–165 m | ~3.5° | toward FSP side, per D6 |
| VSAT-A | ~41° | 452 m | — | local high point (search box corner >400 m; fine) |
| Landing pad + Blue Moon Mk2 | **165°** | **1,500 m** | **3.33°** | flattest destination ≥900 m with drivable path; ≥1 km separation per published siting logic |
| Starship HLS | **~165° fan** | **2,350 m** | **3.37°** | off-pad (D8), no path constraint — landers land |
| FSP reactor | **315°** | **1,200 m** | **5.1°** | flattest outside the pad approach corridor (≥45°); reactor is emplaced/leveled hardware — REVIEW ITEM, nudge if it bothers |

## Cameras in the blend (`terrain/blockout_site11_v001.blend`)

- `CAM_hero` — 250 m at bearing 41°, 12 m up, 50 mm, looking across the cluster
  toward the void. **Sun az 135° (tile frame), provisional** — chosen from an
  8-azimuth sweep from this camera (`D:\renders\lunar-base\blockout\hero_az_sweep.png`); D7 decides finally.
- `CAM_top` — 4.5 km ortho overhead.
- `CAM_eye` — 80 m out on the hero line, 2.5 m boom, aimed at the pad.

## Review materials

- `D:\renders\lunar-base\blockout\site11_layout_map.png` — annotated hillshade map (1/2 km rings)
- `blockout_{hero,top,eye}.png`, `hero_az_sweep.png` — same folder
- Fly `blockout_site11_v001.blend` (Blockout collection; proxies named `BLK_*`)

## Composition note for the gate

Pad/HLS sit at bearing 165° (the flat sector); the void backdrop is at 221°.
From CAM_hero both landers are ~45–56° off the void axis — a 50 mm frame holds
cluster+void OR cluster+landers, not all three. Options: (a) wider hero lens
(24–35 mm) catches all three at reduced lander scale; (b) accept landers
entering frame in the camera envelope's swing rather than every frame; (c)
move the pad to the 221° sector at the cost of rougher pad ground. The bible
shot list's "both landers always in frame" was a draft — Kari rules at this gate.

## Known blockout limitations (deliberate)

- Proxies are primitives at published dimensions (bible §3); no berm corridor
  gap, no cables, no ejecta decals — those are set-dressing passes.
- Terrain is the audition mesh (7.8 m/vertex); production adds the 10 m/px
  context skirt beyond the tile edge (bible §6.2).
- Eye-camera Z comes from a viewport-subdiv ray cast (±2 m vs render mesh).
