#!/usr/bin/env python
"""audition_vantage.py — compute the audition camera vantage for a site DEM tile.

Terrain-audition methodology (D2, SCENE-BIBLE.md §4/§8): per site, ONE vantage —
camera at the most plausible base location, aimed at the strongest terrain
feature. This script turns published coordinates (or documented proxies) into
local Blender coordinates and writes a per-site vantage JSON consumed by
pipeline/blender/build_terrain_audition.py.

Runs in the `terrain` conda env:
    ~/miniconda3/envs/terrain/bin/python pipeline/terrain/audition_vantage.py \
        --site site01 --dem Site01_final_adj_5mpp_surf.tif --out site01.vantage.json

Local frame convention (must match dem_to_displacement.py + the EXR):
  plane centered at the tile's projected-bounds center, +X = projected east,
  +Y = projected north (row 0 = top = bounds.top), Z = meters above tile min.
"""

from __future__ import annotations

import argparse
import json
import math
import os

import numpy as np
import rasterio
from pyproj import CRS, Transformer

CAMERA_HEIGHT_M = 10.0   # above local terrain — grounded but reads the landforms
MAX_TARGET_DIST_M = 6000.0  # clamp look-at inside the 16 km tile

# Vantage definitions. lat south-negative, lon degrees east (−180..180).
SITES = {
    "site01": {
        "name": "Connecting Ridge (Site 001)",
        "camera": {"lat": -89.45, "lon": 222.69 - 360.0},
        "camera_basis": "Mazarico et al. 2011 Point 001 — highest documented illumination on the Moon (89.0% surface avg); crest slopes <10 deg (SCENE-BIBLE.md §4)",
        "target": {"mode": "deepest_within", "radius_m": 6000.0},
        "target_basis": "deepest depression within 6 km — PSR-candidate void; the bible's ISRU adjacency story and the strongest local relief (Shackleton itself is ~20 km away, outside this tile)",
    },
    "site04": {
        "name": "Shackleton rim",
        "camera": {"lat": -89.6866, "lon": 197.19 - 360.0},
        "camera_basis": "Glaeser et al. 2018 best 2 m-mast spot on the rim (85.5% avg illumination, longest darkness 66 h)",
        "target": {"mode": "latlon", "lat": -89.66, "lon": 129.78},
        "target_basis": "into the crater void toward Shackleton's center — 21 km diameter, 4.2 km deep PSR; the most iconic single feature of the three sites",
    },
    "site11": {
        "name": "de Gerlache rim (Rim 2 region)",
        "camera": {"mode": "max_elevation"},
        "camera_basis": "[UNCONFIRMED] no published station coordinates for de Gerlache Rim 2 — using the tile's highest crest point as the illumination proxy (elevation correlates with polar illumination)",
        "target": {"mode": "latlon", "lat": -88.5, "lon": -87.1},
        "target_basis": "into the de Gerlache void (32.4 km crater, PSR floor) — the site's defining negative space",
    },
}


def compute_vantage(site: str, dem_path: str) -> dict:
    cfg = SITES[site]
    with rasterio.open(dem_path) as src:
        elev = src.read(1).astype(np.float64)
        if src.nodata is not None:
            elev = np.where(elev == src.nodata, np.nan, elev)
        crs = CRS.from_wkt(src.crs.to_wkt())
        to_proj = Transformer.from_crs(crs.geodetic_crs, crs, always_xy=True)
        b = src.bounds
        cx, cy = (b.left + b.right) / 2, (b.bottom + b.top) / 2
        emin = float(np.nanmin(elev))

        def latlon_to_local(lat, lon):
            x, y = to_proj.transform(lon, lat)
            return x - cx, y - cy

        def local_to_rowcol(xl, yl):
            row, col = src.index(xl + cx, yl + cy)
            return int(np.clip(row, 0, elev.shape[0] - 1)), int(np.clip(col, 0, elev.shape[1] - 1))

        def z_at(xl, yl):
            r, c = local_to_rowcol(xl, yl)
            v = elev[r, c]
            return float((np.nanmin(elev) if np.isnan(v) else v) - emin)

        # camera position
        if cfg["camera"].get("mode") == "max_elevation":
            r, c = np.unravel_index(np.nanargmax(elev), elev.shape)
            px_x, px_y = abs(src.transform.a), abs(src.transform.e)
            cam_x = (c + 0.5) * px_x + b.left - cx
            cam_y = b.top - (r + 0.5) * px_y - cy
            cam_note = f"auto max-elevation pixel (row {r}, col {c})"
        else:
            cam_x, cam_y = latlon_to_local(cfg["camera"]["lat"], cfg["camera"]["lon"])
            cam_note = f"published coordinates {cfg['camera']['lat']:.4f}, {cfg['camera']['lon']:.2f}"
        cam_z = z_at(cam_x, cam_y) + CAMERA_HEIGHT_M

        # target
        t = cfg["target"]
        if t["mode"] == "deepest_within":
            px_x, px_y = abs(src.transform.a), abs(src.transform.e)
            rows, cols = np.mgrid[0 : elev.shape[0], 0 : elev.shape[1]]
            xs = (cols + 0.5) * px_x + b.left - cx
            ys = b.top - (rows + 0.5) * px_y - cy
            dist = np.hypot(xs - cam_x, ys - cam_y)
            masked = np.where(dist <= t["radius_m"], elev, np.nan)
            r, c = np.unravel_index(np.nanargmin(masked), elev.shape)
            tgt_x, tgt_y = xs[r, c], ys[r, c]
        else:
            tgt_x, tgt_y = latlon_to_local(t["lat"], t["lon"])
        # clamp look-at inside the tile so the frame is terrain, not void-beyond-edge
        d = math.hypot(tgt_x - cam_x, tgt_y - cam_y)
        if d > MAX_TARGET_DIST_M:
            s = MAX_TARGET_DIST_M / d
            tgt_x, tgt_y = cam_x + (tgt_x - cam_x) * s, cam_y + (tgt_y - cam_y) * s
        tgt_z = z_at(tgt_x, tgt_y)

    return {
        "site": site,
        "name": cfg["name"],
        "camera_local_m": [round(cam_x, 2), round(cam_y, 2), round(cam_z, 2)],
        "camera_note": cam_note,
        "camera_basis": cfg["camera_basis"],
        "camera_height_above_terrain_m": CAMERA_HEIGHT_M,
        "target_local_m": [round(tgt_x, 2), round(tgt_y, 2), round(tgt_z, 2)],
        "target_basis": cfg["target_basis"],
        "target_distance_m": round(math.hypot(tgt_x - cam_x, tgt_y - cam_y), 1),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--site", required=True, choices=sorted(SITES))
    ap.add_argument("--dem", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    v = compute_vantage(args.site, args.dem)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w") as fh:
        json.dump(v, fh, indent=2)
    print(json.dumps(v, indent=2))


if __name__ == "__main__":
    main()
