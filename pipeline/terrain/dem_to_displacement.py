#!/usr/bin/env python
"""dem_to_displacement.py — lunar DEM GeoTIFF -> 32-bit EXR displacement map + meta.json.

Runs in the `terrain` conda env:
    ~/miniconda3/envs/terrain/bin/python pipeline/terrain/dem_to_displacement.py \
        <dem.tif> --out-dir assets_src/lunar-base/terrain

Importable API (M2 convention — the CLI is a thin wrapper):
    from dem_to_displacement import dem_to_displacement
    meta = dem_to_displacement("site.tif", out_dir="…")

================================================================================
HOW TO EXPORT A DEM FROM NASA MOON TREK (for Kari)
================================================================================
1. Open https://trek.nasa.gov/moon/ and switch the projection to SOUTH POLE
   (globe/projection control, lower left — polar stereographic).
2. Layers: search for the LOLA DEM layer covering the site. For South Pole work
   prefer the high-res polar products, e.g. "LRO LOLA DEM 87S 20m" / site
   mosaics, over the 118 m global DEM. (Layer names drift as Trek updates —
   pick the finest LOLA DEM that covers the box.)
3. Draw the export region: Tools > Export (or the download icon), rectangle
   select around the site. Keep it modest — a few km per side at 5–20 m/px;
   Trek caps export sizes, and Blender does not need more than ~8k×8k.
4. Format: GeoTIFF. Projection: keep the polar stereographic default (meters!)
   — do NOT pick an equirectangular/degrees projection at the pole.
5. Download and drop the .tif into assets_src/lunar-base/terrain/, then run
   this script on it.

PREFERRED for production (verified 2026-07-10): NASA GSFC PGDA LOLA polar DEMs
— cloud-optimized GeoTIFFs, south polar stereographic (meters), consumed by
this script unchanged. Moon Trek's south-pole DEM basis is only ~100 m/px, so
use Trek for scouting and PGDA for production:
  5 m/px site tiles (~41 MB each, product page /products/78):
    Connecting Ridge  https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/Site01/Site01_final_adj_5mpp_surf.tif
    Shackleton rim    https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/Site04/Site04_final_adj_5mpp_surf.tif
    de Gerlache rim   https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/Site11/Site11_final_adj_5mpp_surf.tif
  10 m/px context (5.1 GB COG — crop a window, don't download it all):
    gdal_translate -projwin <ulx uly lrx lry> \
      /vsicurl/https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LDEM_83S_10MPP_ADJ.TIF ctx.tif
LOLA/PDS data is US-government public domain (attribution requested — cite
Barker et al. 2021/2023); log the product URL in provenance either way.
================================================================================

Output (written next to each other in --out-dir):
  <stem>.exr        single-channel ('Y') float32, elevation in METERS above the
                    tile minimum (offset recorded in meta). Blender: use as
                    displacement with Strength 1.0 and the plane sized to
                    suggested_plane_size_m for true 1:1 scale.
  <stem>.meta.json  resolution, meters/pixel, elevation min/max/range, offset,
                    suggested Blender plane size, CRS, source hash.

Blender setup (Cycles true displacement):
  plane size X/Y = suggested_plane_size_m, subdivide adaptively;
  Image Texture (the EXR, Non-Color, extension Extend) -> Displacement node
  with Scale 1.0, Midlevel 0.0.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import date

import Imath
import numpy as np
import OpenEXR
import rasterio

MOON_RADIUS_M = 1_737_400.0


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def dem_to_displacement(dem_path: str, out_dir: str, stem: str | None = None) -> dict:
    """Convert a DEM GeoTIFF to a float32 EXR displacement map + meta.json.

    Returns the meta dict (also written to <stem>.meta.json).
    """
    os.makedirs(out_dir, exist_ok=True)
    stem = stem or os.path.splitext(os.path.basename(dem_path))[0]

    with rasterio.open(dem_path) as src:
        elev = src.read(1).astype(np.float64)
        transform = src.transform
        crs = src.crs
        nodata = src.nodata
        bounds = src.bounds  # projected meters; row 0 = bounds.top

        # meters/pixel from the affine transform; geographic (degrees) CRS is
        # converted at the Moon's mean radius but flagged — polar work should
        # always arrive in a projected (meters) CRS.
        px_x, px_y = abs(transform.a), abs(transform.e)
        geographic = bool(crs and crs.is_geographic)
        if geographic:
            deg_to_m = np.pi / 180.0 * MOON_RADIUS_M
            px_x *= deg_to_m
            px_y *= deg_to_m

    mask = ~np.isfinite(elev)
    if nodata is not None:
        mask |= elev == nodata
    nodata_count = int(mask.sum())
    if nodata_count:
        # fill holes with the valid minimum — flat pits beat NaN spikes in a
        # displacement map; large gaps should be re-exported, see meta warning
        elev[mask] = elev[~mask].min()

    emin, emax = float(elev.min()), float(elev.max())
    rel = (elev - emin).astype(np.float32)
    h, w = rel.shape

    exr_path = os.path.join(out_dir, f"{stem}.exr")
    header = OpenEXR.Header(w, h)
    header["channels"] = {"Y": Imath.Channel(Imath.PixelType(Imath.PixelType.FLOAT))}
    header["compression"] = Imath.Compression(Imath.Compression.ZIP_COMPRESSION)
    exr = OpenEXR.OutputFile(exr_path, header)
    exr.writePixels({"Y": rel.tobytes()})
    exr.close()

    meta = {
        "source_file": os.path.basename(dem_path),
        "source_sha256": _sha256(dem_path),
        "generated": date.today().isoformat(),
        "width_px": w,
        "height_px": h,
        "meters_per_pixel": {"x": round(px_x, 6), "y": round(px_y, 6)},
        "meters_per_pixel_note": (
            "[UNCONFIRMED] derived from a geographic (degrees) CRS at Moon mean "
            "radius — re-export in polar stereographic for exact scale"
            if geographic
            else "from projected CRS (meters)"
        ),
        "crs": str(crs) if crs else "[UNCONFIRMED] no CRS in file",
        "projected_bounds_m": {
            "left": bounds.left, "bottom": bounds.bottom,
            "right": bounds.right, "top": bounds.top,
            "note": "pixel (0,0) is the (left, top) corner; Blender plane center = bounds center",
        },
        "elevation_min_m": emin,
        "elevation_max_m": emax,
        "elevation_range_m": emax - emin,
        "exr_offset_m": emin,
        "exr_channel": "Y (float32, meters above elevation_min_m)",
        "nodata_pixels_filled": nodata_count,
        "suggested_plane_size_m": {"x": round(w * px_x, 3), "y": round(h * px_y, 3)},
        "blender": "plane = suggested_plane_size_m; displacement Scale 1.0, Midlevel 0.0, Non-Color",
    }
    meta_path = os.path.join(out_dir, f"{stem}.meta.json")
    with open(meta_path, "w") as fh:
        json.dump(meta, fh, indent=2)
    return meta


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("dem", help="input DEM GeoTIFF (Moon Trek / PGDA export)")
    ap.add_argument("--out-dir", default=".", help="output directory (default: cwd)")
    ap.add_argument("--stem", default=None, help="output basename (default: input stem)")
    args = ap.parse_args()
    meta = dem_to_displacement(args.dem, args.out_dir, args.stem)
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
