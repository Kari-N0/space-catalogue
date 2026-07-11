#!/usr/bin/env python
"""select_base_site.py — pick the base anchor + element layout inside a site DEM tile.

D2 layout blockout (SCENE-BIBLE.md §4, LAYOUT.md): turns the chosen site's
height + slope rasters into a defensible base position and a full element
layout JSON for pipeline/blender/blockout_lunar_base.py, plus an annotated
overview map for gate review.

Runs in the `terrain` conda env:
    ~/miniconda3/envs/terrain/bin/python pipeline/terrain/select_base_site.py \
        --height Site11_final_adj_5mpp_surf.tif --slope Site11_final_adj_5mpp_slp.tif \
        --out-json site11.layout.json --out-map site11_layout_map.png

Habitat-anchor criteria (scored on an 80 m grid, all weights documented):
  1. buildable: mean slope in a 250 m window < 3 deg AND fraction of
     slope<5 deg pixels in a 500 m window (habitat cluster + margins)
  2. illumination proxy: elevation percentile (no illumination raster at 5 m/px;
     bible §6.4's Mazarico rasters refine this at look-dev)
  3. backdrop: distance to the "void" (>=500 m below tile median) in a
     1.5-4 km sweet spot — visible drama, safe ground

Element placement (bible §3 visual notes + published siting logic):
  pad 1.0 km from habitat on the flattest bearing; FSP 1.0 km on the
  flattest bearing >=60 deg away, shadow shield toward base; HLS off-pad
  1.8 km out beyond the pad (D8); VSAT on the local high point <=400 m;
  ISRU vignette 150 m; rovers by the habitat; comms mast at the cluster.
Local frame = tile center origin, +X east, +Y north, Z meters above tile min
(identical to the audition EXR/blends).
"""

from __future__ import annotations

import argparse
import json
import math
import os

import numpy as np
import rasterio
from PIL import Image, ImageDraw, ImageFont
from pyproj import CRS, Transformer

GRID_STEP_PX = 16          # score every 80 m
BUILD_WIN_M = 500.0        # buildable-fraction window (cluster + margins)
SMOOTH_WIN_M = 250.0       # mean-slope window
MAX_MEAN_SLOPE = 3.0       # deg — habitat cluster ground
MAX_LOCAL_SLOPE = 5.0      # deg — per-pixel buildable
ELEV_PCT_MIN = 60.0        # illumination proxy floor
VOID_DEPTH_M = 500.0       # below tile median = "void"
BACKDROP_MIN_M, BACKDROP_MAX_M = 1500.0, 4000.0
W_BUILD, W_ELEV, W_BACKDROP = 0.45, 0.30, 0.25


def _box_mean(a: np.ndarray, win_px: int) -> np.ndarray:
    """Box filter via integral image (no scipy in the terrain env)."""
    pad = win_px // 2
    p = np.pad(a.astype(np.float64), pad + 1, mode="edge")
    ii = p.cumsum(0).cumsum(1)
    w = 2 * pad + 1
    out = (ii[w:, w:] - ii[:-w, w:] - ii[w:, :-w] + ii[:-w, :-w]) / (w * w)
    return out[: a.shape[0], : a.shape[1]]


def select_base_site(height_tif: str, slope_tif: str) -> dict:
    with rasterio.open(height_tif) as hsrc:
        H = hsrc.read(1).astype(np.float64)
        b = hsrc.bounds
        px = abs(hsrc.transform.a)
        crs = CRS.from_wkt(hsrc.crs.to_wkt())
        to_geo = Transformer.from_crs(crs, crs.geodetic_crs, always_xy=True)
    with rasterio.open(slope_tif) as ssrc:
        S = ssrc.read(1).astype(np.float64)
    assert H.shape == S.shape, "height/slope raster mismatch"
    n = H.shape[0]
    cx, cy = (b.left + b.right) / 2, (b.bottom + b.top) / 2
    hmin = float(np.nanmin(H))

    def rc_to_local(r, c):
        return ((c + 0.5) * px + b.left - cx, b.top - (r + 0.5) * px - cy)

    def local_to_rc(x, y):
        r = int(np.clip((b.top - (y + cy)) / px, 0, n - 1))
        c = int(np.clip(((x + cx) - b.left) / px, 0, n - 1))
        return r, c

    def z_at(x, y):
        return float(H[local_to_rc(x, y)] - hmin)

    # --- scoring rasters -----------------------------------------------------
    mean_slope = _box_mean(S, int(SMOOTH_WIN_M / px) | 1)
    build_frac = _box_mean((S < MAX_LOCAL_SLOPE).astype(float), int(BUILD_WIN_M / px) | 1)
    elev_pct = (H.argsort(axis=None).argsort(axis=None).reshape(H.shape) + 1) / H.size * 100.0

    void = H < (np.nanmedian(H) - VOID_DEPTH_M)
    # distance-to-void on a coarse grid (80 m) — plenty for a siting band.
    # Everything here is in COARSE-cell units until the final *step*px scaling.
    step = GRID_STEP_PX
    void_coarse = void[::step, ::step]
    vr, vc = np.nonzero(void_coarse)
    grid_r, grid_c = np.mgrid[0 : void_coarse.shape[0], 0 : void_coarse.shape[1]]
    if len(vr):
        d2 = (
            (grid_r[..., None] - vr[None, None, :]) ** 2
            + (grid_c[..., None] - vc[None, None, :]) ** 2
        )
        void_dist_m = np.sqrt(d2.min(axis=-1)) * step * px
    else:
        void_dist_m = np.full(grid_r.shape, np.inf)

    gs = (slice(None, None, step), slice(None, None, step))
    backdrop = np.clip(1 - np.abs(void_dist_m - (BACKDROP_MIN_M + BACKDROP_MAX_M) / 2)
                       / ((BACKDROP_MAX_M - BACKDROP_MIN_M) / 2), 0, 1)
    score = (
        W_BUILD * build_frac[gs]
        + W_ELEV * (elev_pct[gs] / 100.0)
        + W_BACKDROP * backdrop
    )
    score[mean_slope[gs] > MAX_MEAN_SLOPE] = -1
    score[elev_pct[gs] < ELEV_PCT_MIN] = -1
    # keep the cluster >=2 km inside the tile so the 1.8 km HLS spur fits
    margin = int(2000 / (step * px))
    score[:margin, :] = score[-margin:, :] = score[:, :margin] = score[:, -margin:] = -1

    # --- horizon-based illumination pass over the top candidates --------------
    # A point is sunlit when no terrain along the sun azimuth subtends more
    # than the sun's elevation. Sun elevation oscillates within ~±1.5°, so the
    # fraction of azimuths with horizon angle < 1.0° is a robust proxy for
    # annual illumination (full Mazarico rasters refine this at look-dev).
    def illum_frac(r, c, n_az=48, max_dist=8000.0, step_m=40.0):
        z0 = H[r, c] + 2.0  # 2 m mast height, as in the published site tables
        dists = np.arange(50.0, max_dist, step_m)
        lit = 0
        for az_ in np.linspace(0, 2 * math.pi, n_az, endpoint=False):
            rr = np.clip((r - dists * math.cos(az_) / px).astype(int), 0, n - 1)
            cc = np.clip((c + dists * math.sin(az_) / px).astype(int), 0, n - 1)
            horizon = np.max(np.arctan2(H[rr, cc] - z0, dists))
            lit += horizon < math.radians(1.0)
        return lit / n_az

    flat_idx = np.argsort(score, axis=None)[::-1][:400]
    ranked = []
    for fi in flat_idx:
        gr_, gc_ = np.unravel_index(fi, score.shape)
        if score[gr_, gc_] < 0:
            break
        f = illum_frac(gr_ * step, gc_ * step)
        # illumination is the polar siting driver, but buildable acreage gets
        # its own term — a 2% illum edge must not beat a 20% flat-ground edge
        val = 0.5 * f + 0.3 * build_frac[gr_ * step, gc_ * step] + 0.2 * score[gr_, gc_]
        ranked.append((val, f, gr_, gc_))
    ranked.sort(reverse=True)
    print("top candidates (val, illum, build_frac, mean_slope, void_km):")
    for val, f, gr_, gc_ in ranked[:8]:
        print(f"  {val:.3f}  illum {f:.2f}  build {build_frac[gr_ * step, gc_ * step]:.2f}  "
              f"slope {mean_slope[gr_ * step, gc_ * step]:.2f}  void {void_dist_m[gr_, gc_] / 1000:.1f}")
    _, best_illum, gr, gc = ranked[0]
    hab_r, hab_c = gr * step, gc * step
    hab_x, hab_y = rc_to_local(hab_r, hab_c)

    # --- pad / FSP / HLS spots: flat DESTINATION first, passable path second --
    def spot_slope(x, y, win_m=100.0):
        r, c = local_to_rc(x, y)
        w = int(win_m / px / 2)
        return float(np.mean(S[max(0, r - w) : r + w, max(0, c - w) : c + w]))

    def path_mean_slope(bear_deg, dist_m):
        th = math.radians(bear_deg)
        return float(np.mean([
            S[local_to_rc(hab_x + math.sin(th) * d, hab_y + math.cos(th) * d)]
            for d in np.linspace(100, dist_m, 12)
        ]))

    def xy(bear_deg, dist_m):
        th = math.radians(bear_deg)
        return hab_x + math.sin(th) * dist_m, hab_y + math.cos(th) * dist_m

    def best_spot(bear_range, dist_range, max_path_slope=6.0):
        cands = []
        for bd in bear_range:
            for dm in dist_range:
                s = spot_slope(*xy(bd, dm))
                p = path_mean_slope(bd, dm)
                if p <= max_path_slope:
                    cands.append((s, p, bd, dm))
        cands.sort()
        return cands[0]  # (spot_slope, path_slope, bearing, dist)

    def candidates(bear_range, dist_range, max_path_slope=6.0):
        out = []
        for bd in bear_range:
            for dm in dist_range:
                s = spot_slope(*xy(bd, dm))
                if path_mean_slope(bd, dm) <= max_path_slope:
                    out.append((s, bd, dm))
        return sorted(out)

    # pad + FSP assigned JOINTLY (>=60 deg apart; pad slope weighted 2x — it's
    # the landing surface), from the top candidates of each search
    # 45 deg keeps the reactor out of the pad approach corridor while letting
    # both share the (only) flat sector; FSP may sit out to 1.5 km
    pad_c = candidates(range(0, 360, 15), range(900, 1800, 100))[:20]
    fsp_c = candidates(range(0, 360, 15), range(900, 1600, 100))[:30]
    pad_s, pad_bear, pad_dist, fsp_s, fsp_bear, fsp_dist = min(
        (
            (ps, pb, pd, fs, fb, fd)
            for ps, pb, pd in pad_c
            for fs, fb, fd in fsp_c
            if abs((fb - pb + 180) % 360 - 180) >= 45
        ),
        key=lambda t: 2 * t[0] + t[3],
    )
    # HLS lands, it doesn't drive — no path constraint, wide bearing fan
    hls_bears = [(pad_bear + d) % 360 for d in range(-60, 61, 15)]
    hls_s, hls_bear, hls_dist = candidates(hls_bears, range(1600, 2700, 150), max_path_slope=99.0)[0]

    def along(bear_deg, dist_m, dz=0.0):
        x, y = xy(bear_deg, dist_m)
        return [round(x, 1), round(y, 1), round(z_at(x, y) + dz, 1)]

    # VSAT: local max elevation within 400 m of the habitat
    rr = int(400 / px)
    r0, r1 = max(0, hab_r - rr), min(n, hab_r + rr)
    c0, c1 = max(0, hab_c - rr), min(n, hab_c + rr)
    vr_, vc_ = np.unravel_index(np.argmax(H[r0:r1, c0:c1]), H[r0:r1, c0:c1].shape)
    vsat_x, vsat_y = rc_to_local(r0 + vr_, c0 + vc_)

    # hero camera: opposite side from the void so the frame looks across the
    # cluster into the backdrop
    if len(vr):
        vd2 = (vr - hab_r / step) ** 2 + (vc - hab_c / step) ** 2
        nvr, nvc = vr[np.argmin(vd2)] * step, vc[np.argmin(vd2)] * step
        void_x, void_y = rc_to_local(nvr, nvc)
        void_bear = math.degrees(math.atan2(void_x - hab_x, void_y - hab_y)) % 360
    else:
        void_bear = (pad_bear + 180) % 360
    cam_bear = (void_bear + 180) % 360

    lon, lat = to_geo.transform(hab_x + cx, hab_y + cy)
    hab = [round(hab_x, 1), round(hab_y, 1), round(z_at(hab_x, hab_y), 1)]
    layout = {
        "site": "site11 — de Gerlache Rim 2 (D2)",
        "frame": "local: tile center origin, +X east, +Y north, Z above tile min (= audition EXR frame)",
        "habitat_anchor": {
            "local_m": hab,
            "lat_lon": [round(lat, 5), round(lon, 5)],
            "stats": {
                "mean_slope_250m_deg": round(float(mean_slope[hab_r, hab_c]), 2),
                "buildable_frac_500m": round(float(build_frac[hab_r, hab_c]), 3),
                "elevation_percentile": round(float(elev_pct[hab_r, hab_c]), 1),
                "void_distance_m": round(float(void_dist_m[gr, gc]), 0),
                "illum_frac_horizon_proxy_2m": round(float(best_illum), 3),
            },
        },
        "bearings_deg": {"pad": pad_bear, "fsp": fsp_bear, "void": round(void_bear), "hero_cam": round(cam_bear)},
        "elements": {
            "fsh_habitat": {"local_m": hab, "note": "anchor"},
            "lunar_cruiser": {"local_m": along((pad_bear + 300) % 360, 25), "note": "docked at FSH suitport side"},
            "ltv_pegasus": {"local_m": along((pad_bear + 330) % 360, 40), "note": "hero foreground rover (D6)"},
            "ltv_clv1": {"local_m": along(fsp_bear, 150), "note": "parked at ISRU vignette (D6)"},
            "isru_vignette": {"local_m": along(fsp_bear, 165), "note": "drill + O2 plant"},
            "vsat_a": {"local_m": [round(vsat_x, 1), round(vsat_y, 1), round(z_at(vsat_x, vsat_y), 1)], "note": "local high point"},
            "vsat_b": {"local_m": along(math.degrees(math.atan2(vsat_x - hab_x, vsat_y - hab_y)) % 360, 60, 0), "note": "60 m toward cluster from VSAT-A"},
            "comms_mast": {"local_m": along((pad_bear + 180) % 360, 35), "note": "cluster edge"},
            "landing_pad": {"local_m": along(pad_bear, pad_dist), "slope_100m_deg": round(pad_s, 2), "note": f"{pad_dist} m out (>=1 km per published siting logic, bible §2), flattest destination in search"},
            "blue_moon_mk2": {"local_m": along(pad_bear, pad_dist), "note": "ON the pad (D8)"},
            "starship_hls": {"local_m": along(hls_bear, hls_dist), "slope_100m_deg": round(hls_s, 2), "note": f"off-pad {hls_dist} m out, bearing {hls_bear} deg (D8); own ejecta streaks"},
            "fsp_reactor": {"local_m": along(fsp_bear, fsp_dist), "slope_100m_deg": round(fsp_s, 2), "note": "shadow shield toward base (bearing back = %d deg)" % ((fsp_bear + 180) % 360)},
        },
        "hero_camera_suggestion": {
            "local_m": along(cam_bear, 250, 12.0),
            "look_at": along(void_bear, 200, 5.0),
            "note": "250 m out on the anti-void side, 12 m up, looking across the cluster into the void backdrop; envelope authored at look-dev (ADDON.md §3)",
        },
    }
    return layout


def draw_map(layout: dict, height_tif: str, out_png: str, sun_az_deg: float = 315.0) -> str:
    """Annotated overview: hillshade + element markers + separation rings."""
    with rasterio.open(height_tif) as src:
        H = src.read(1).astype(np.float64)
        px = abs(src.transform.a)
    n = H.shape[0]
    gy, gx = np.gradient(H, px)
    az, alt = math.radians(sun_az_deg), math.radians(8.0)
    sx, sy, sz = math.sin(az) * math.cos(alt), math.cos(az) * math.cos(alt), math.sin(alt)
    norm = np.sqrt(gx**2 + gy**2 + 1)
    shade = np.clip((-gx * sx - gy * sy + sz) / norm, 0, 1) ** 0.8
    img = Image.fromarray((shade * 235).astype(np.uint8)).convert("RGB")
    draw = ImageDraw.Draw(img)

    def to_px(x, y):
        return (x + n * px / 2) / px, (n * px / 2 - y) / px

    def font(sz):
        try:
            return ImageFont.truetype("DejaVuSans-Bold.ttf", sz)
        except OSError:
            return ImageFont.load_default()

    hx, hy, _ = layout["habitat_anchor"]["local_m"]
    for radius, lbl in ((1000, "1 km"), (2000, "2 km")):
        r_px = radius / px
        cxp, cyp = to_px(hx, hy)
        draw.ellipse([cxp - r_px, cyp - r_px, cxp + r_px, cyp + r_px], outline=(90, 140, 200), width=3)
        draw.text((cxp + r_px * 0.72, cyp - r_px * 0.72), lbl, fill=(90, 140, 200), font=font(36))

    colors = {"fsh": (255, 90, 60), "landing": (255, 200, 40), "blue": (255, 200, 40),
              "starship": (255, 140, 40), "fsp": (120, 255, 120), "vsat": (120, 200, 255),
              "hero": (255, 80, 200)}
    for name, el in {**layout["elements"], "hero_cam": layout["hero_camera_suggestion"]}.items():
        x, y, _ = el["local_m"]
        cxp, cyp = to_px(x, y)
        col = next((c for k, c in colors.items() if name.startswith(k)), (240, 240, 240))
        r = 10
        draw.ellipse([cxp - r, cyp - r, cxp + r, cyp + r], fill=col)
        draw.text((cxp + 12, cyp - 14), name, fill=col, font=font(30))
    draw.text((20, 14), f"{layout['site']} — layout blockout (hillshade az {sun_az_deg:.0f}°, 16×16 km tile)",
              fill=(255, 255, 255), font=font(44))
    os.makedirs(os.path.dirname(os.path.abspath(out_png)), exist_ok=True)
    img.save(out_png)
    return out_png


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--height", required=True)
    ap.add_argument("--slope", required=True)
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--out-map", default=None)
    args = ap.parse_args()
    layout = select_base_site(args.height, args.slope)
    with open(args.out_json, "w") as fh:
        json.dump(layout, fh, indent=2)
    print(json.dumps({"habitat_anchor": layout["habitat_anchor"], "bearings_deg": layout["bearings_deg"]}, indent=2))
    if args.out_map:
        print("MAP:", draw_map(layout, args.height, args.out_map))


if __name__ == "__main__":
    main()
