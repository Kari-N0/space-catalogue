"""Build composite DEM EXRs for the polar illumination simulation v002.

Two products (both float32 single-channel EXR, absolute meters relative to the
1737.4 km sphere, row 0 = north/top edge like the source rasters):

  grid A (wide):  the FIG_01 LOLA 60 m crop as-is             -> illum_A_dem.exr
  grid B (fine):  the 20 m regional DEM footprint, nodata and
                  gaps filled from the 60 m crop resampled     -> illum_B_dem.exr

Each EXR gets a sibling .meta.json with bounds/pixel size/stats so the Blender
build script never guesses geometry. Importable functions + thin argparse main
(repo convention). Runs in the `terrain` conda env (rasterio, OpenEXR, numpy).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np


R_MOON_M = 1_737_400.0  # sphere radius shared by every DEM product we use

FIG01_DEM = "assets_src/lunar-base/figures/fig01/dem/fig01_dem60.tif"
REGIONAL_DEM = "assets_src/lunar-base/terrain/site11_regional_20mpp.tif"


def _write_exr(path: Path, arr: np.ndarray) -> None:
    import Imath
    import OpenEXR

    h, w = arr.shape
    header = OpenEXR.Header(w, h)
    header["channels"] = {"Y": Imath.Channel(Imath.PixelType(Imath.PixelType.FLOAT))}
    out = OpenEXR.OutputFile(str(path), header)
    out.writePixels({"Y": arr.astype(np.float32).tobytes()})
    out.close()


def _meta(path: Path, arr: np.ndarray, bounds, px: float, note: str) -> dict:
    meta = {
        "exr": path.name,
        "channel": "Y",
        "units": "meters relative to the 1737.4 km sphere (absolute, no tile offset)",
        "row0": "north/top edge (y = bounds.top)",
        "bounds_m": {"left": bounds[0], "bottom": bounds[1], "right": bounds[2], "top": bounds[3]},
        "pixel_m": px,
        "shape_hw": list(arr.shape),
        "min_m": float(np.nanmin(arr)),
        "max_m": float(np.nanmax(arr)),
        "note": note,
    }
    path.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2))
    return meta


def build_grid_a(repo: Path, out_dir: Path) -> dict:
    """Wide grid: the FIG_01 60 m crop, converted to a single-channel EXR."""
    import rasterio

    with rasterio.open(repo / FIG01_DEM) as src:
        arr = src.read(1).astype(np.float32)
        bounds = (src.bounds.left, src.bounds.bottom, src.bounds.right, src.bounds.top)
        px = src.res[0]
    # LDEM crop has no nodata; guard anyway (fill with the minimum, flagged in meta)
    holes = ~np.isfinite(arr)
    if holes.any():
        arr[holes] = np.nanmin(arr[np.isfinite(arr)])
    out = out_dir / "illum_A_dem.exr"
    _write_exr(out, arr)
    return _meta(out, arr, bounds, px, f"fig01_dem60.tif verbatim; {int(holes.sum())} non-finite px filled with min")


def build_grid_b(repo: Path, out_dir: Path) -> dict:
    """Fine grid: 20 m regional footprint, gaps filled from the 60 m crop."""
    import rasterio
    from rasterio.warp import Resampling, reproject

    with rasterio.open(repo / REGIONAL_DEM) as reg:
        fine = reg.read(1).astype(np.float32)
        transform = reg.transform
        crs = reg.crs
        bounds = (reg.bounds.left, reg.bounds.bottom, reg.bounds.right, reg.bounds.top)
        px = reg.res[0]

    # resample the 60 m crop onto the same 20 m grid to fill regional nodata
    with rasterio.open(repo / FIG01_DEM) as base:
        fill = np.full_like(fine, np.nan, dtype=np.float32)
        reproject(
            source=rasterio.band(base, 1),
            destination=fill,
            src_transform=base.transform,
            src_crs=base.crs if base.crs else crs,
            dst_transform=transform,
            dst_crs=crs,
            resampling=Resampling.cubic,
        )

    invalid = ~np.isfinite(fine)
    n_fill = int(invalid.sum())
    fine[invalid] = fill[invalid]
    still = ~np.isfinite(fine)
    if still.any():  # outside both products (shouldn't happen: 60 m covers footprint)
        fine[still] = np.nanmin(fine[np.isfinite(fine)])

    # seam feather: blend the outer margin toward the 60 m surface so the
    # inset plane meets the surrounding band planes without an elevation step
    # (an unfeathered seam casts a visible false shadow line at grazing sun)
    margin_px = 40  # 800 m at 20 m/px
    h, w = fine.shape
    yy, xx = np.mgrid[0:h, 0:w]
    edge_dist = np.minimum(np.minimum(xx, w - 1 - xx), np.minimum(yy, h - 1 - yy))
    wgt = np.clip(edge_dist / margin_px, 0.0, 1.0).astype(np.float32)
    ok = np.isfinite(fill)
    fine[ok] = wgt[ok] * fine[ok] + (1.0 - wgt[ok]) * fill[ok]

    # seam QA: 60 m vs 20 m difference over the valid overlap (inter-product datum check)
    both = np.isfinite(fill) & ~invalid
    diff = (fine - fill)[both]
    qa = {
        "filled_from_60m_px": n_fill,
        "unfilled_px": int(still.sum()),
        "overlap_diff_mean_m": float(diff.mean()),
        "overlap_diff_std_m": float(diff.std()),
        "overlap_diff_p99_abs_m": float(np.percentile(np.abs(diff), 99)),
    }
    out = out_dir / "illum_B_dem.exr"
    _write_exr(out, fine)
    meta = _meta(out, fine, bounds, px,
                 "site11_regional_20mpp.tif with nodata filled from fig01_dem60.tif (cubic); "
                 "both products referenced to the same sphere so values merge without datum shifts")
    meta["seam_qa"] = qa
    (out.with_suffix(".meta.json")).write_text(json.dumps(meta, indent=2))
    return meta


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", default=".", help="repo root")
    ap.add_argument("--out", default="assets_src/lunar-base/figures/illum_v002", help="output dir")
    args = ap.parse_args()
    repo = Path(args.repo).resolve()
    out_dir = (repo / args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    a = build_grid_a(repo, out_dir)
    b = build_grid_b(repo, out_dir)
    print(json.dumps({"A": a, "B": b}, indent=2))


if __name__ == "__main__":
    main()
