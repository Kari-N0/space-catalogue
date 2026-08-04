"""Generate tyre-track decal variants from the original Rover_trace_decal set.

Keeps the original's photoreal regolith background on every map, removes the
original chevron tread band (patched with neighbouring ground), and stamps a
new procedural tread pattern. Emits the full 8-file set per variant with the
original naming scheme, so every variant drops into the same Blender shader:

    <Prefix>_GREY_color.jpg  <Prefix>_RED_color.jpg  <Prefix>_alpha.jpg
    <Prefix>_mask.jpg        <Prefix>_height.exr     <Prefix>_height.jpg
    <Prefix>_normal.jpg      <Prefix>_rough.jpg

Importable: generate_variant(name, pattern, seed, src, dst). Thin argparse main.
Runs in the `terrain` conda env (pillow + OpenEXR).
"""
import argparse
import os

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

SRC_DEFAULT = "/mnt/d/renders/rover_trace_gn/Rover_trace_decal"
DST_DEFAULT = "/mnt/d/renders/rover_trace_gn"
ORIG = "Rover_trace_decal"

# tread geometry (px; canvas 2048 x 8192 = 2.723 m x 10.893 m -> 752 px/m)
HALF_W = 190          # tread half-width
FILL_HALF = 240       # how much of the old band gets patched
FILL_FEATHER = 70
ROLL = 460            # patch source offset (columns)
DEPTH = 0.10          # tread relief amplitude in height.jpg units


# ---------------------------------------------------------------- helpers
def _load(src, name, mode=None):
    im = Image.open(os.path.join(src, f"{ORIG}_{name}"))
    if mode:
        im = im.convert(mode)
    return np.asarray(im, dtype=np.float32) / 255.0


def _save_jpg(dst, prefix, name, arr, mode="L"):
    a = np.clip(arr * 255.0 + 0.5, 0, 255).astype(np.uint8)
    Image.fromarray(a, mode=mode).save(os.path.join(dst, f"{prefix}_{name}.jpg"), quality=92)


def _read_exr(path):
    import Imath
    import OpenEXR
    f = OpenEXR.InputFile(path)
    dw = f.header()["dataWindow"]
    w, h = dw.max.x - dw.min.x + 1, dw.max.y - dw.min.y + 1
    raw = f.channel("R", Imath.PixelType(Imath.PixelType.HALF))
    return np.frombuffer(raw, dtype=np.float16).reshape(h, w).astype(np.float32)


def _write_exr(path, arr):
    import Imath
    import OpenEXR
    h, w = arr.shape
    hd = OpenEXR.Header(w, h)
    half = Imath.Channel(Imath.PixelType(Imath.PixelType.HALF))
    hd["channels"] = {c: half for c in "RGB"}
    out = OpenEXR.OutputFile(path, hd)
    b = arr.astype(np.float16).tobytes()
    out.writePixels({"R": b, "G": b, "B": b})
    out.close()


def _blur1d(a, sigma, axis):
    """Cheap gaussian-ish blur: 3 box passes, wraps along the tiling axis (0)."""
    if sigma <= 0:
        return a
    r = max(1, int(sigma))
    k = 2 * r + 1
    for _ in range(3):
        pad = np.take(a, range(-r, a.shape[axis] + r), axis=axis, mode="wrap" if axis == 0 else "clip")
        c = np.cumsum(pad, axis=axis, dtype=np.float32)
        lead = np.take(c, range(k - 1, k - 1 + a.shape[axis]), axis=axis)
        lag = np.concatenate([np.zeros_like(np.take(c, [0], axis=axis)),
                              np.take(c, range(0, a.shape[axis] - 1), axis=axis)], axis=axis)
        a = (lead - lag) / k
    return a


def _blur(a, sigma):
    return _blur1d(_blur1d(a, sigma, 0), sigma, 1)


def _tri(x):
    """Periodic triangle wave of x (period 1) in 0..1."""
    f = np.mod(x, 1.0)
    return 1.0 - np.abs(2.0 * f - 1.0)


# ---------------------------------------------------------------- patterns
def _pattern(name, xr, y, rng, H):
    """Return tread relief in -1..1 (negative digs in). xr: px from tread center."""
    W = float(HALF_W)
    inside = np.clip(1.0 - (np.abs(xr) / W) ** 6, 0.0, 1.0)          # across-tread envelope
    trough = -0.38 * np.clip(1.0 - (xr / (0.9 * W)) ** 4, 0.0, 1.0)  # compacted depression
    pitch = 92.0
    if name == "ladder":
        bars = (_tri(y / pitch) > 0.62).astype(np.float32)
        rel = -0.95 * bars + 0.22 * (1.0 - bars)
    elif name == "blocks":
        L, gap = 118.0, 30.0
        rel = np.zeros_like(xr)
        for i, cx in enumerate((-0.62 * W, 0.0, 0.62 * W)):
            col = np.clip(1.0 - np.abs((xr - cx) / (0.30 * W)) ** 6, 0.0, 1.0)
            ph = 0.5 * (L + gap) * (i % 2)
            on = (np.mod(y + ph, L + gap) < L).astype(np.float32)
            rel = rel + col * (0.30 * on - 0.85 * (1.0 - on))
        rel = np.clip(rel, -1.0, 0.35)
    elif name == "zigzag":
        diag = _tri(y / (2.6 * pitch) + xr / (2.4 * W))
        rel = np.where(diag > 0.72, -0.9, 0.18).astype(np.float32)
    elif name == "ribs":
        rel = np.full_like(xr, 0.14)
        for cx in (-0.62 * W, -0.21 * W, 0.21 * W, 0.62 * W):
            rel = rel - 1.1 * np.clip(1.0 - np.abs((xr - cx) / 26.0) ** 4, 0.0, 1.0)
        rel = np.clip(rel, -1.0, 0.2)
    elif name == "perseverance":
        # 48 gently wave-curved grousers per wheel: ~34 mm pitch (26 px), thin
        # crisp bars with a shallow S-curve across the tread, smooth band between
        pitch_p = 26.0
        wave = 12.0 * np.sin(2 * np.pi * xr / (2.6 * W))
        bars = (_tri((y + wave) / pitch_p) > 0.70).astype(np.float32)
        rel = -0.9 * bars + 0.10 * (1.0 - bars)
        trough = trough * 1.1
    elif name == "curiosity":
        # MSL wheel: ~24 shallow-chevron grousers per 50 cm wheel revolution,
        # plus the JPL Morse odometry cutouts (raised tabs) once per revolution.
        period = H / 7.0              # ~1.56 m — one revolution, tiles exactly
        pitch_c = period / 24.0
        yv = y + 0.12 * np.abs(xr)    # shallow chevron (real MSL bars are near-straight)
        bars = (_tri(yv / pitch_c) > 0.72).astype(np.float32)
        rel = -0.95 * bars + 0.15 * (1.0 - bars)
        u = 0.38 * pitch_c            # morse unit; dot=1u, dash=3u
        seq = [(1, 1), (3, 1), (3, 1), (3, 3),      # J  .---
               (1, 1), (3, 1), (3, 1), (1, 3),      # P  .--.
               (1, 1), (3, 1), (1, 1), (1, 3)]      # L  .-..
        ym = np.mod(y, period)
        morse = np.zeros_like(xr)
        pos = 0.0
        for ln, gp in seq:
            morse = morse + ((ym >= pos) & (ym < pos + ln * u)).astype(np.float32)
            pos += (ln + gp) * u
        band = (np.abs(xr) < 26).astype(np.float32)
        # cutout tabs sit BETWEEN grousers (holes are in the wheel skin)
        rel = np.where(morse * band * (1.0 - bars) > 0, 0.8, rel)
    elif name == "hakkapeliitta":
        # studded winter tyre imprint (stylised from general knowledge — no
        # manufacturer tread geometry): directional V-blocks, dense siping,
        # zigzag center groove, and a tiling stud-dent scatter
        W = 0.55 * W                  # passenger-tyre width on the same canvas
        inside = np.clip(1.0 - (np.abs(xr) / W) ** 6, 0.0, 1.0)
        trough = -0.30 * np.clip(1.0 - (xr / (0.95 * W)) ** 4, 0.0, 1.0)
        P = 24.0
        sgn = np.sign(xr)
        diag = _tri((y + 1.15 * sgn * xr) / P)          # mirrored diagonals -> V
        blocks = np.where(diag > 0.68, -0.95, 0.22).astype(np.float32)
        sipes = (_tri((y + 1.15 * sgn * xr) / (P / 3.0)) > 0.90).astype(np.float32)
        zig = 0.06 * W * np.sign(_tri(y / (3.2 * P)) - 0.5)
        centergroove = (np.abs(xr - zig) < 6.0).astype(np.float32)
        rel = blocks - 0.30 * sipes * (blocks > 0) - 0.9 * centergroove
        period = H / 16.0                               # stud layout tiles
        ymp = np.mod(y, period)
        stud = np.zeros_like(xr)
        for _ in range(9):
            sx = rng.uniform(-0.85, 0.85) * W
            sy = rng.uniform(0, period)
            dy = np.minimum(np.abs(ymp - sy), period - np.abs(ymp - sy))
            d2 = ((xr - sx) / 7.0) ** 2 + (dy / 7.0) ** 2
            stud = np.minimum(stud, -1.8 * np.exp(-d2 * d2))
        rel = rel + stud
    elif name == "worn":
        faint = (_tri(y / (5.5 * pitch)) > 0.90).astype(np.float32)
        rel = -0.28 * faint
        amp = 0.55 + 0.45 * np.sin(2 * np.pi * (3 * y / H) + rng.uniform(0, 6.28))
        rel = rel * amp
        trough = trough * 1.35
    else:
        raise ValueError(name)
    return (rel * inside + trough).astype(np.float32)


GAUGE_PX = 1126  # twin variants: wheel-center distance (0.55 of canvas width)


def _shift_cols(p, s):
    """Shift a (1, W) profile by s columns, zero-filled."""
    q = np.zeros_like(p)
    if s >= 0:
        q[:, s:] = p[:, : p.shape[1] - s]
    else:
        q[:, : p.shape[1] + s] = p[:, -s:]
    return q


# ---------------------------------------------------------------- core
def generate_variant(prefix, pattern, seed, src=SRC_DEFAULT, dst_root=DST_DEFAULT, twin=False):
    rng = np.random.default_rng(seed)
    dst = os.path.join(dst_root, prefix)
    os.makedirs(dst, exist_ok=True)

    grey = _load(src, "GREY_color.jpg")
    red = _load(src, "RED_color.jpg")
    alpha = _load(src, "alpha.jpg", "L")
    mask = _load(src, "mask.jpg", "L")
    rough = _load(src, "rough.jpg", "L")
    normal = _load(src, "normal.jpg")
    hexr = _read_exr(os.path.join(src, f"{ORIG}_height.exr"))
    hjpg = _load(src, "height.jpg", "L")
    H, Wc = hjpg.shape

    # jpg = a*exr + b  (to convert relief between the two height encodings)
    s = slice(None, None, 37)
    A = np.vstack([hexr[s, s].ravel(), np.ones(hexr[s, s].size, np.float32)]).T
    coef, *_ = np.linalg.lstsq(A, hjpg[s, s].ravel(), rcond=None)
    a_fit = max(float(coef[0]), 1e-3)

    ys = np.arange(H, dtype=np.float32)[:, None]
    xs = np.arange(Wc, dtype=np.float32)[None, :]

    # -- old tread path (dark lugs in the grey color map), periodic-smoothed
    band = (grey.mean(axis=2) < 0.24) & (xs > 700) & (xs < 1500)
    w_row = band.sum(axis=1).astype(np.float32)
    cent = np.where(w_row > 0, (band * xs).sum(axis=1) / np.maximum(w_row, 1), np.nan)
    idx = np.arange(H)
    good = ~np.isnan(cent)
    cent = np.interp(idx, idx[good], cent[good], period=H).astype(np.float32)
    k = np.ones(801, np.float32) / 801.0
    cent = np.convolve(np.tile(cent, 3), k, "same")[H:2 * H]
    old_xr = xs - cent[:, None]
    fill = np.clip((FILL_HALF + FILL_FEATHER - np.abs(old_xr)) / FILL_FEATHER, 0, 1).astype(np.float32)

    # -- patch fill: texture detail from +-ROLL columns, large-scale profile kept
    lam = _blur((rng.random((H // 64 + 1, Wc // 64 + 1)).astype(np.float32)), 1.5)
    lam = np.asarray(Image.fromarray(lam, "F").resize((Wc, H), Image.BILINEAR))
    lam = (lam > np.median(lam)).astype(np.float32)
    lam = _blur(lam, 9)

    def patch(img):
        lm = lam if img.ndim == 2 else lam[..., None]
        fl = lm * np.roll(img, -ROLL, axis=1) + (1 - lm) * np.roll(img, ROLL, axis=1)
        if img.ndim == 2:
            fl = fl - fl.mean(axis=0, keepdims=True) + img.mean(axis=0, keepdims=True)
            return img * (1 - fill) + fl * fill
        f3 = fill[..., None]
        return img * (1 - f3) + fl * f3

    grey_b, red_b, rough_b, normal_b = patch(grey), patch(red), patch(rough), patch(normal)
    hexr_b, hjpg_b = patch(hexr), patch(hjpg)
    prof = _blur1d(alpha.mean(axis=0, keepdims=True), 40, 1)
    if twin:
        g2i = int(round(GAUGE_PX / 2))
        prof = np.maximum(_shift_cols(prof, -g2i), _shift_cols(prof, g2i))
        alpha_b = np.broadcast_to(prof, alpha.shape)
    else:
        alpha_b = alpha * (1 - fill) + np.broadcast_to(prof, alpha.shape) * fill

    # -- new meander (exactly periodic along the tiling axis; twins share it — one vehicle)
    amp = 0.7 if twin else 1.0
    path = np.full(H, Wc / 2.0, np.float32)
    for kk in (1, 2, 3):
        path += amp * rng.uniform(20, 55) * np.sin(2 * np.pi * (kk * ys[:, 0] / H) + rng.uniform(0, 6.28))
    xr = xs - path[:, None]

    yb = np.broadcast_to(ys, (H, Wc))
    if twin:
        # identical pattern layout on both wheels (same per-side rng seed)
        rel = (_pattern(pattern, xr - GAUGE_PX / 2.0, yb, np.random.default_rng(seed + 500), float(H))
               + _pattern(pattern, xr + GAUGE_PX / 2.0, yb, np.random.default_rng(seed + 500), float(H)))
    else:
        rel = _pattern(pattern, xr, yb, rng, float(H))
    rel = _blur(rel, 2.5)
    wear = 0.75 + 0.5 * _blur1d(rng.random((H, 1)).astype(np.float32), 300, 0)
    delta = (DEPTH * rel * wear).astype(np.float32)
    cov = np.clip(np.abs(rel) * 3.0, 0, 1)

    # -- derive the map set
    hjpg_n = np.clip(hjpg_b + delta, 0, 1)
    hexr_n = hexr_b + delta / a_fit
    shade = np.clip(1.0 + 2.6 * delta, 0.55, 1.35)  # grooves dark, crushed rims/tabs bright
    grey_n = np.clip(grey_b * shade[..., None], 0, 1)
    red_n = np.clip(red_b * shade[..., None], 0, 1)
    rough_n = np.clip(rough_b - 1.2 * delta, 0, 1)  # compacted floor smoother, grooves dustier
    gy, gx = np.gradient(_blur(delta, 1.5))
    n = normal_b * 2.0 - 1.0
    n[..., 0] = n[..., 0] - 140.0 * gx
    n[..., 1] = n[..., 1] + 140.0 * gy  # +Y convention (OpenGL, matches Blender)
    ln = np.sqrt((n * n).sum(axis=2, keepdims=True))
    normal_n = (n / np.maximum(ln, 1e-6) + 1.0) * 0.5
    alpha_n = np.maximum(alpha_b, np.clip(cov, 0, 1) * 0.97)

    _save_jpg(dst, prefix, "GREY_color", grey_n, "RGB")
    _save_jpg(dst, prefix, "RED_color", red_n, "RGB")
    _save_jpg(dst, prefix, "alpha", alpha_n)
    _save_jpg(dst, prefix, "mask", mask)
    _save_jpg(dst, prefix, "height", hjpg_n)
    _save_jpg(dst, prefix, "rough", rough_n, "RGB") if rough_n.ndim == 3 else _save_jpg(dst, prefix, "rough", np.repeat(rough_n[..., None], 3, 2), "RGB")
    _save_jpg(dst, prefix, "normal", normal_n, "RGB")
    _write_exr(os.path.join(dst, f"{prefix}_height.exr"), hexr_n)
    return dst


def generate_twin_original(seed=10, src=SRC_DEFAULT, dst_root=DST_DEFAULT, strip=260):
    """Twin-track version of Kari's ORIGINAL chevron decal: the real tread band
    is extracted along its detected meander, the center is patched with ground,
    and the band is re-composited twice at +-GAUGE_PX/2 on a shared new path."""
    rng = np.random.default_rng(seed)
    prefix = f"{ORIG}_2x"
    dst = os.path.join(dst_root, prefix)
    os.makedirs(dst, exist_ok=True)

    grey = _load(src, "GREY_color.jpg")
    red = _load(src, "RED_color.jpg")
    alpha = _load(src, "alpha.jpg", "L")
    mask = _load(src, "mask.jpg", "L")
    rough = _load(src, "rough.jpg", "L")
    normal = _load(src, "normal.jpg")
    hexr = _read_exr(os.path.join(src, f"{ORIG}_height.exr"))
    hjpg = _load(src, "height.jpg", "L")
    H, Wc = hjpg.shape
    ys = np.arange(H, dtype=np.float32)[:, None]
    xs = np.arange(Wc, dtype=np.float32)[None, :]

    # old tread path (same detection as the variants)
    band = (grey.mean(axis=2) < 0.24) & (xs > 700) & (xs < 1500)
    w_row = band.sum(axis=1).astype(np.float32)
    cent = np.where(w_row > 0, (band * xs).sum(axis=1) / np.maximum(w_row, 1), np.nan)
    idx = np.arange(H)
    good = ~np.isnan(cent)
    cent = np.interp(idx, idx[good], cent[good], period=H).astype(np.float32)
    k = np.ones(801, np.float32) / 801.0
    cent = np.convolve(np.tile(cent, 3), k, "same")[H:2 * H]
    old_xr = xs - cent[:, None]
    fill = np.clip((FILL_HALF + FILL_FEATHER - np.abs(old_xr)) / FILL_FEATHER, 0, 1).astype(np.float32)

    lam = _blur((rng.random((H // 64 + 1, Wc // 64 + 1)).astype(np.float32)), 1.5)
    lam = np.asarray(Image.fromarray(lam, "F").resize((Wc, H), Image.BILINEAR))
    lam = (lam > np.median(lam)).astype(np.float32)
    lam = _blur(lam, 9)

    def patch(img):
        lm = lam if img.ndim == 2 else lam[..., None]
        fl = lm * np.roll(img, -ROLL, axis=1) + (1 - lm) * np.roll(img, ROLL, axis=1)
        if img.ndim == 2:
            fl = fl - fl.mean(axis=0, keepdims=True) + img.mean(axis=0, keepdims=True)
            return img * (1 - fill) + fl * fill
        f3 = fill[..., None]
        return img * (1 - f3) + fl * f3

    # strip extraction (tread straightened around its meander)
    xr_off = np.arange(-strip, strip + 1, dtype=np.int32)[None, :]
    src_idx = np.clip(np.round(cent[:, None]).astype(np.int32) + xr_off, 0, Wc - 1)
    w = np.clip((FILL_HALF + FILL_FEATHER - np.abs(xr_off.astype(np.float32))) / FILL_FEATHER, 0, 1)

    path2 = np.full(H, Wc / 2.0, np.float32)
    for kk in (1, 2, 3):
        path2 += 0.7 * rng.uniform(20, 55) * np.sin(2 * np.pi * (kk * ys[:, 0] / H) + rng.uniform(0, 6.28))

    def gather(img):
        if img.ndim == 2:
            return np.take_along_axis(img, src_idx, axis=1)
        return np.stack([np.take_along_axis(img[..., c], src_idx, axis=1)
                         for c in range(img.shape[2])], axis=-1)

    def composite(bg, sp):
        out = bg.copy()
        for sgn in (-1.0, 1.0):
            dest = np.clip(np.round(path2[:, None] + sgn * GAUGE_PX / 2.0).astype(np.int32) + xr_off, 0, Wc - 1)
            if bg.ndim == 2:
                cur = np.take_along_axis(out, dest, axis=1)
                np.put_along_axis(out, dest, cur * (1 - w) + sp * w, axis=1)
            else:
                for c in range(bg.shape[2]):
                    cur = np.take_along_axis(out[..., c], dest, axis=1)
                    np.put_along_axis(out[..., c], dest, cur * (1 - w) + sp[..., c] * w, axis=1)
        return out

    grey_n = composite(patch(grey), gather(grey))
    red_n = composite(patch(red), gather(red))
    rough_n = composite(patch(rough), gather(rough))
    hjpg_n = composite(patch(hjpg), gather(hjpg))
    hexr_n = composite(patch(hexr), gather(hexr))
    normal_n = composite(patch(normal), gather(normal))
    nrm = normal_n * 2.0 - 1.0
    ln = np.sqrt((nrm * nrm).sum(axis=2, keepdims=True))
    normal_n = (nrm / np.maximum(ln, 1e-6) + 1.0) * 0.5

    prof = _blur1d(alpha.mean(axis=0, keepdims=True), 40, 1)
    g2i = int(round(GAUGE_PX / 2))
    prof_t = np.maximum(_shift_cols(prof, -g2i), _shift_cols(prof, g2i))
    alpha_n = composite(np.broadcast_to(prof_t, alpha.shape).copy(), gather(alpha))

    _save_jpg(dst, prefix, "GREY_color", grey_n, "RGB")
    _save_jpg(dst, prefix, "RED_color", red_n, "RGB")
    _save_jpg(dst, prefix, "alpha", alpha_n)
    _save_jpg(dst, prefix, "mask", mask)
    _save_jpg(dst, prefix, "height", hjpg_n)
    _save_jpg(dst, prefix, "rough", np.repeat(rough_n[..., None], 3, 2) if rough_n.ndim == 2 else rough_n, "RGB")
    _save_jpg(dst, prefix, "normal", normal_n, "RGB")
    _write_exr(os.path.join(dst, f"{prefix}_height.exr"), hexr_n)
    return dst


VARIANTS = [
    ("Rover_trace_decal_02_ladder", "ladder", 20),
    ("Rover_trace_decal_03_blocks", "blocks", 30),
    ("Rover_trace_decal_04_zigzag", "zigzag", 40),
    ("Rover_trace_decal_05_ribs", "ribs", 50),
    ("Rover_trace_decal_06_worn", "worn", 60),
    ("Rover_trace_decal_07_perseverance", "perseverance", 70),
    ("Rover_trace_decal_08_curiosity", "curiosity", 80),
    ("Rover_trace_decal_09_hakkapeliitta", "hakkapeliitta", 90),
]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", default=SRC_DEFAULT)
    ap.add_argument("--dst", default=DST_DEFAULT)
    ap.add_argument("--only", default=None, help="generate a single variant by pattern name")
    ap.add_argument("--twins", action="store_true",
                    help="generate the two-track (_2x) versions incl. the original chevron")
    args = ap.parse_args()
    if args.twins:
        if not args.only or args.only == "original":
            print("generating", f"{ORIG}_2x (original chevron, twin)", "...", flush=True)
            print("  ->", generate_twin_original(10, args.src, args.dst))
        for prefix, pattern, seed in VARIANTS:
            if args.only and pattern != args.only:
                continue
            print("generating", f"{prefix}_2x", "...", flush=True)
            print("  ->", generate_variant(f"{prefix}_2x", pattern, seed, args.src, args.dst, twin=True))
        return
    for prefix, pattern, seed in VARIANTS:
        if args.only and pattern != args.only:
            continue
        print("generating", prefix, "...", flush=True)
        print("  ->", generate_variant(prefix, pattern, seed, args.src, args.dst))


if __name__ == "__main__":
    main()
