"""illum_classify.py — turn illumination-sweep EXR frames into PSR / lit-% products.

Runs in the `terrain` conda env. Inputs are the run_illum_sweep.py outputs:
  <root>/<cam>_psr/f*.exr   best-season sweep, point sun at +1.806 deg (limb test)
  <root>/<cam>_lit/f*.exr   worst-season sweep, point sun at -1.54 deg (center test)
  <root>/<cam>_beauty/f000.exr  one presentational frame for preview backdrops

Products per camera (written to --out):
  <cam>_psr_mask.png      binary PSR (never lit across the best-season sweep)
  <cam>_lit_pct.png       16-bit grayscale, worst-season lit fraction 0..1
  <cam>_stats.json        areas, histograms, threshold table
  <cam>_preview.png       styled overlay: PSR blue + lit warm bands over backdrop

Classification is a float threshold on scene-linear EXR values (no bounces,
black world -> shadowed pixels are exactly zero); LIT_TAU only guards against
float dust. Importable functions + thin argparse main (repo convention).
"""

from __future__ import annotations

import argparse
import glob
import json
import os

import numpy as np

LIT_TAU = 1e-6

# brand accents (BRAND.md chip triads): PSR = blue family, lit = warm/orange
PSR_RGB = (96, 165, 250)     # #60A5FA
LIT_RGB = (251, 146, 60)     # #FB923C

# footprints implied by Kari's cameras (ortho AUTO fit on 2048x2560 portrait:
# ortho_scale = vertical extent; width = ortho * 2048/2560)
FOOTPRINTS_M = {
    "A": {"center": (-25020.0, 5010.0), "w": 230000.0 * 2048 / 2560, "h": 230000.0},
    "B": {"center": (-4321.5, -15461.1), "w": 58252.19921875 * 2048 / 2560, "h": 58252.19921875},
}
DE_GERLACHE_M = (-45429.4, 2301.4)  # IAU center in map coords
DE_GERLACHE_R_M = 16500.0           # crater radius envelope for the km^2 stat


def read_exr_gray(path: str) -> np.ndarray:
    import Imath
    import OpenEXR

    f = OpenEXR.InputFile(path)
    header = f.header()
    dw = header["dataWindow"]
    w, h = dw.max.x - dw.min.x + 1, dw.max.y - dw.min.y + 1
    channels = list(header["channels"].keys())
    # BW EXRs may store the single channel under different names
    for name in ("Y", "V", "R", "A"):
        if name in channels:
            pt = Imath.PixelType(Imath.PixelType.FLOAT)
            arr = np.frombuffer(f.channel(name, pt), dtype=np.float32)
            return arr.reshape(h, w).copy()
    raise ValueError(f"{path}: no known gray channel in {channels}")


def load_sweep(dirpath: str) -> np.ndarray:
    paths = sorted(glob.glob(os.path.join(dirpath, "f*.exr")))
    if not paths:
        raise FileNotFoundError(f"no frames in {dirpath}")
    stack = np.stack([read_exr_gray(p) for p in paths])
    return stack


def classify(cam: str, root: str, out_dir: str, band_thresholds=(0.7, 0.8, 0.9)) -> dict:
    from PIL import Image

    os.makedirs(out_dir, exist_ok=True)
    psr_stack = load_sweep(os.path.join(root, f"{cam}_psr"))
    lit_stack = load_sweep(os.path.join(root, f"{cam}_lit"))

    psr = (psr_stack.max(axis=0) <= LIT_TAU)          # never lit, best case
    lit_pct = (lit_stack > LIT_TAU).mean(axis=0)      # share of worst-case sweep

    # annual illumination: equal-time quadrature over the seasonal cycle —
    # mean lit share across the <cam>_ann_k* sweeps (each 150 equal-time
    # hour-angle samples at subsolar latitude 1.54*sin(theta_k))
    ann_dirs = sorted(glob.glob(os.path.join(root, f"{cam}_ann_k*")))
    annual = None
    if ann_dirs:
        acc = np.zeros_like(lit_pct, dtype=np.float64)
        for d in ann_dirs:
            stack = load_sweep(d)
            acc += (stack > LIT_TAU).mean(axis=0)
        annual = (acc / len(ann_dirs)).astype(np.float32)

    fp = FOOTPRINTS_M[cam]
    h_px, w_px = psr.shape
    px_m = fp["h"] / h_px  # square pixels: vertical extent / vertical px
    px_km2 = (px_m / 1000.0) ** 2

    # de Gerlache PSR area (only meaningful where the crater is in frame)
    yy, xx = np.mgrid[0:h_px, 0:w_px]
    x_m = fp["center"][0] - fp["w"] / 2 + (xx + 0.5) * (fp["w"] / w_px)
    y_m = fp["center"][1] + fp["h"] / 2 - (yy + 0.5) * (fp["h"] / h_px)
    dg = (x_m - DE_GERLACHE_M[0]) ** 2 + (y_m - DE_GERLACHE_M[1]) ** 2 <= DE_GERLACHE_R_M ** 2
    dg_in_frame = float(dg.mean())
    dg_psr_km2 = float((psr & dg).sum() * px_km2)

    hist_src = annual if annual is not None else lit_pct
    hist, edges = np.histogram(hist_src, bins=20, range=(0, 1))
    stats = {
        "camera": cam,
        "frames": {"psr": int(psr_stack.shape[0]), "lit": int(lit_stack.shape[0])},
        "resolution": [w_px, h_px],
        "pixel_m": px_m,
        "psr_area_km2": float(psr.sum() * px_km2),
        "psr_share": float(psr.mean()),
        "de_gerlache": {
            "circle_in_frame_share": dg_in_frame,
            "psr_km2_within_circle": dg_psr_km2,
            "note": "v001 reference: 381-396 km2 (threshold-stable range)",
        },
        "worst_season_lit_max": float(lit_pct.max()),
        "annual_sweeps": len(ann_dirs),
        "annual_lit_max": float(annual.max()) if annual is not None else None,
        "annual_histogram": {"edges": edges.tolist(), "counts": hist.tolist()},
        "annual_share_at": {str(t): float((annual >= t).mean()) for t in
                            (0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 1.0)} if annual is not None else None,
        "annual_area_km2_at": {str(t): float((annual >= t).sum() * px_km2) for t in
                               (0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 1.0)} if annual is not None else None,
        "worst_season_share_at": {str(t): float((lit_pct >= t).mean()) for t in
                                  (0.3, 0.4, 0.5, 0.6)},
    }

    Image.fromarray((psr * 255).astype(np.uint8)).save(os.path.join(out_dir, f"{cam}_psr_mask.png"))
    Image.fromarray((lit_pct * 65535).astype(np.uint16)).save(os.path.join(out_dir, f"{cam}_lit_pct.png"))
    if annual is not None:
        Image.fromarray((annual * 65535).astype(np.uint16)).save(os.path.join(out_dir, f"{cam}_annual_pct.png"))

    # styled preview: tonemapped beauty backdrop + PSR blue + warm lit bands
    beauty_paths = sorted(glob.glob(os.path.join(root, f"{cam}_beauty", "f*.exr")))
    if beauty_paths:
        b = read_exr_gray(beauty_paths[0])
        p99 = np.percentile(b[b > 0], 99) if (b > 0).any() else 1.0
        base = np.clip(b / max(p99, 1e-9), 0, 1) ** (1 / 2.2)
        rgb = np.stack([base, base, base], axis=-1)
    else:
        rgb = np.zeros((h_px, w_px, 3), dtype=np.float32)

    def blend(mask: np.ndarray, color, alpha: float) -> None:
        c = np.array(color, dtype=np.float32) / 255.0
        m = mask.astype(np.float32)[..., None] * alpha
        rgb[:] = rgb * (1 - m) + c * m

    blend(psr, PSR_RGB, 0.5)
    lit_layer = annual if annual is not None else lit_pct
    for i, t in enumerate(band_thresholds):
        blend(lit_layer >= t, LIT_RGB, 0.25 + 0.2 * i)
    Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8)).save(
        os.path.join(out_dir, f"{cam}_preview.png"))

    with open(os.path.join(out_dir, f"{cam}_stats.json"), "w") as fh:
        json.dump(stats, fh, indent=2)
    return stats


def finalize(cam: str, root: str, out_dir: str, label: str) -> dict:
    """Final deliverable layers at render resolution, registered to the camera:
    <label>_psr_mask_full.png, <label>_psr_mask_major.png (components >=
    0.05 km^2, v001 convention), <label>_psr_sdf.png (8-bit signed distance,
    0.5 = boundary, clamped +-32 px mapped to 0.5 +- 0.5), and
    <label>_annual_pct.png (16-bit, share of the year in direct sun)."""
    from PIL import Image
    from scipy import ndimage

    stats = classify(cam, root, out_dir)
    psr = np.array(Image.open(os.path.join(out_dir, f"{cam}_psr_mask.png"))) > 127
    fp = FOOTPRINTS_M[cam]
    px_m = fp["h"] / psr.shape[0]
    px_km2 = (px_m / 1000.0) ** 2

    lab, n = ndimage.label(psr)
    keep = np.zeros(n + 1, dtype=bool)
    sizes = ndimage.sum_labels(np.ones_like(lab), lab, index=range(1, n + 1))
    for i, sz in enumerate(sizes, start=1):
        keep[i] = sz * px_km2 >= 0.05
    major = keep[lab]

    inside = ndimage.distance_transform_edt(psr)
    outside = ndimage.distance_transform_edt(~psr)
    signed = np.where(psr, inside, -outside)  # positive inside PSR
    sdf = np.clip(0.5 + signed / 64.0, 0.0, 1.0)

    Image.fromarray((psr * 255).astype(np.uint8)).save(os.path.join(out_dir, f"{label}_psr_mask_full.png"))
    Image.fromarray((major * 255).astype(np.uint8)).save(os.path.join(out_dir, f"{label}_psr_mask_major.png"))
    Image.fromarray((sdf * 255).astype(np.uint8)).save(os.path.join(out_dir, f"{label}_psr_sdf.png"))
    ann_src = os.path.join(out_dir, f"{cam}_annual_pct.png")
    if os.path.exists(ann_src):
        Image.open(ann_src).save(os.path.join(out_dir, f"{label}_annual_pct.png"))
    stats["major_components"] = int(keep.sum())
    stats["major_area_km2"] = float(major.sum() * px_km2)
    stats["sdf_convention"] = "8-bit, 0.5 = PSR boundary, +-32 px linear range, positive inside; 1 px = %.3f m" % px_m
    stats["label"] = label
    with open(os.path.join(out_dir, f"{label}_stats.json"), "w") as fh:
        json.dump(stats, fh, indent=2)
    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", required=True, help="dir containing <cam>_psr/<cam>_lit/<cam>_beauty")
    ap.add_argument("--out", required=True)
    ap.add_argument("--cams", default="A,B")
    ap.add_argument("--final", action="store_true", help="write deliverable layers (SDF, major mask)")
    args = ap.parse_args()
    labels = {"A": "illum_v002_wide", "B": "illum_v002_closeup"}
    for cam in args.cams.split(","):
        if args.final:
            stats = finalize(cam, args.root, args.out, labels[cam])
        else:
            stats = classify(cam, args.root, args.out)
        print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
